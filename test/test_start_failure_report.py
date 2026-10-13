from __future__ import annotations

from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from ccbd.models import CcbdStartupReport
from ccbd import socket_client
from ccbd.socket_client import CcbdClientError
from ccbd.system import utc_now
from cli.phase2_runtime import handlers_start
from cli.phase2_runtime.handlers_start import handle_start
from cli.phase2_runtime.start_failure_report import StartOutcome, resolve_start_outcome
from storage.paths import PathLayout


def _context(tmp_path: Path, *, project_id: str = 'project-1'):
    return SimpleNamespace(
        project=SimpleNamespace(project_id=project_id),
        paths=PathLayout(tmp_path),
    )


def _report(
    context,
    *,
    status: str = 'failed',
    reason: str | None = 'provider failed',
    run_id: str | None = 'start_a',
    trigger: str = 'start_command',
    generated_at: str | None = None,
    project_id: str | None = None,
) -> CcbdStartupReport:
    return CcbdStartupReport(
        project_id=project_id or context.project.project_id,
        generated_at=generated_at or utc_now(),
        trigger=trigger,
        status=status,
        requested_agents=(),
        desired_agents=(),
        restore_requested=False,
        auto_permission=False,
        startup_run_id=run_id,
        failure_reason=reason,
    )


def test_resolve_start_outcome_matches_failed_report_by_run_id(tmp_path, monkeypatch) -> None:
    context = _context(tmp_path)
    report = _report(context, reason='kimi executable not found in PATH')
    monkeypatch.setattr(
        'cli.phase2_runtime.start_failure_report._load_report',
        lambda _context: report,
    )
    exc = CcbdClientError('timed out')
    exc.startup_run_id = 'start_a'

    outcome = resolve_start_outcome(
        context,
        exc,
        attempt_started_at='2026-01-01T00:00:00Z',
    )

    assert outcome == StartOutcome(
        'failed', 'kimi executable not found in PATH', str(context.paths.ccbd_startup_report_path)
    )


def test_resolve_start_outcome_rejects_unrelated_report(tmp_path, monkeypatch) -> None:
    context = _context(tmp_path)
    report = _report(context, reason='stale failure', run_id='start_other')
    monkeypatch.setattr(
        'cli.phase2_runtime.start_failure_report._load_report',
        lambda _context: report,
    )
    exc = CcbdClientError('timed out')
    exc.startup_run_id = 'start_current'

    outcome = resolve_start_outcome(context, exc, attempt_started_at=utc_now())

    assert outcome.status == 'unknown'


def test_resolve_start_outcome_limits_timestamp_fallback_to_daemon_boot(tmp_path, monkeypatch) -> None:
    context = _context(tmp_path)
    report = _report(
        context,
        run_id=None,
        trigger='start_command',
        generated_at='2026-09-30T08:00:01Z',
    )
    monkeypatch.setattr(
        'cli.phase2_runtime.start_failure_report._load_report',
        lambda _context: report,
    )

    outcome = resolve_start_outcome(
        context,
        CcbdClientError('timed out'),
        attempt_started_at='2026-09-30T08:00:00Z',
    )

    assert outcome.status == 'unknown'


def test_resolve_start_outcome_accepts_same_project_daemon_boot_failure(tmp_path, monkeypatch) -> None:
    context = _context(tmp_path)
    report = _report(
        context,
        reason='listen_socket_failed',
        run_id=None,
        trigger='daemon_boot',
        generated_at='2026-09-30T08:00:01Z',
    )
    monkeypatch.setattr(
        'cli.phase2_runtime.start_failure_report._load_report',
        lambda _context: report,
    )

    outcome = resolve_start_outcome(
        context,
        CcbdClientError('timed out'),
        attempt_started_at='2026-09-30T08:00:00Z',
    )

    assert outcome.status == 'failed'
    assert outcome.reason == 'listen_socket_failed'


def test_resolve_start_outcome_rejects_foreign_project_daemon_boot(tmp_path, monkeypatch) -> None:
    context = _context(tmp_path, project_id='project-current')
    report = _report(
        context,
        project_id='project-other',
        run_id=None,
        trigger='daemon_boot',
        generated_at='2026-09-30T08:00:01Z',
    )
    monkeypatch.setattr(
        'cli.phase2_runtime.start_failure_report._load_report',
        lambda _context: report,
    )

    outcome = resolve_start_outcome(
        context,
        CcbdClientError('timed out'),
        attempt_started_at='2026-09-30T08:00:00Z',
    )

    assert outcome.status == 'unknown'


def test_resolve_start_outcome_polls_until_report_lands(tmp_path, monkeypatch) -> None:
    context = _context(tmp_path)
    run_id = 'start_late'
    exc = CcbdClientError('timed out')
    exc.startup_run_id = run_id
    report = _report(context, reason='late provider failure', run_id=run_id)
    reports = iter((None, report))
    now = iter((0.0, 0.0, 0.1, 0.2))

    monkeypatch.setattr(
        'cli.phase2_runtime.start_failure_report._load_report',
        lambda _context: next(reports, report),
    )

    outcome = resolve_start_outcome(
        context,
        exc,
        attempt_started_at='2026-09-30T08:00:00Z',
        grace_s=1.0,
        sleep_fn=lambda _seconds: None,
        monotonic_fn=lambda: next(now, 0.2),
    )

    assert outcome.status == 'failed'
    assert outcome.reason == 'late provider failure'


def test_ccbd_client_marks_wrapped_connect_timeout(monkeypatch, tmp_path) -> None:
    def _connect(*args, **kwargs):
        del args, kwargs
        try:
            raise TimeoutError('timed out')
        except TimeoutError as cause:
            raise CcbdClientError('timed out') from cause

    monkeypatch.setattr(socket_client, 'connect_socket', _connect)

    with pytest.raises(CcbdClientError) as caught:
        socket_client.CcbdClient(tmp_path / 'ccbd.sock', timeout_s=0.1).request('ping')

    assert caught.value.ccb_rpc_phase == 'connect'
    assert isinstance(caught.value.__cause__, TimeoutError)


def test_failed_server_response_does_not_enter_grace_wait(monkeypatch, tmp_path) -> None:
    context = _context(tmp_path)
    calls: list[float] = []
    unknown = StartOutcome('unknown', None, '')
    monkeypatch.setattr(handlers_start, 'START_REPORT_GRACE_S', 90.0)
    monkeypatch.setattr(
        handlers_start,
        'resolve_start_outcome',
        lambda *args, **kwargs: calls.append(kwargs['grace_s']) or unknown,
    )

    outcome = handlers_start._resolve_failed_start(
        context,
        CcbdClientError('kimi executable not found in PATH'),
        attempt_started_at=utc_now(),
    )

    assert outcome.status == 'unknown'
    assert calls == []


def test_connection_timeout_does_not_enter_grace_wait(monkeypatch, tmp_path) -> None:
    context = _context(tmp_path)
    calls: list[float] = []
    unknown = StartOutcome('unknown', None, '')
    monkeypatch.setattr(handlers_start, 'START_REPORT_GRACE_S', 90.0)
    monkeypatch.setattr(
        handlers_start,
        'resolve_start_outcome',
        lambda *args, **kwargs: calls.append(kwargs['grace_s']) or unknown,
    )
    try:
        raise TimeoutError('timed out')
    except TimeoutError as cause:
        error = CcbdClientError('timed out')
        error.ccb_rpc_phase = 'connect'
        error.__cause__ = cause

    outcome = handlers_start._resolve_failed_start(
        context,
        error,
        attempt_started_at=utc_now(),
    )

    assert outcome is not None
    assert calls == []


def test_late_ok_report_does_not_return_success(monkeypatch, tmp_path) -> None:
    context = _context(tmp_path)
    command = SimpleNamespace()
    services = SimpleNamespace()
    exc = CcbdClientError('timed out')
    exc.startup_run_id = 'start_ok'
    outcome = StartOutcome('ok', None, str(context.paths.ccbd_startup_report_path))

    monkeypatch.setattr(handlers_start, '_ensure_project_commands_approved', lambda *args: None)
    monkeypatch.setattr(handlers_start, '_ensure_herdr_runtime_evidence', lambda *args: None)
    monkeypatch.setattr(handlers_start, '_start_agents', lambda *args, **kwargs: (_ for _ in ()).throw(exc))
    monkeypatch.setattr(handlers_start, '_resolve_failed_start', lambda *args, **kwargs: outcome)
    monkeypatch.setattr(handlers_start, 'START_REPORT_GRACE_S', 0.0)

    with pytest.raises(RuntimeError, match='final start response was not received'):
        handle_start(context, command, StringIO(), services)
