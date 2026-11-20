from __future__ import annotations

from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.models import AgentRuntime, AgentState
from agents.store import AgentRuntimeStore
from ccbd.socket_client import CcbdClientError
from cli.phase2_runtime import handlers_start
from cli.phase2_runtime.start_failure_report import StartOutcome
from cli.render_runtime.ops_views_basic import render_start
from cli.services import start_availability
from storage.paths import PathLayout

NOW = '2026-01-01T00:00:00Z'


def _context(tmp_path: Path, *, project_id: str = 'project-1'):
    return SimpleNamespace(
        project=SimpleNamespace(project_id=project_id),
        paths=PathLayout(tmp_path),
    )


def _save_runtime(
    context,
    name: str,
    *,
    pane_state: str = 'alive',
    health: str = 'healthy',
    state: AgentState = AgentState.IDLE,
    failure_reason: str | None = None,
    restart_count: int = 0,
    recovery_failure_count: int = 0,
) -> None:
    layout = context.paths
    runtime = AgentRuntime(
        agent_name=name,
        state=state,
        pid=100,
        started_at=NOW,
        last_seen_at=NOW,
        runtime_ref=f'tmux:%{name}',
        session_ref=f'{name}-session',
        workspace_path=str(layout.workspace_path(name)),
        project_id=context.project.project_id,
        backend_type='tmux',
        queue_depth=0,
        socket_path=None,
        health=health,
        pane_id=f'%{name}',
        pane_state=pane_state,
        restart_count=restart_count,
        recovery_failure_count=recovery_failure_count,
        last_failure_reason=failure_reason,
    )
    AgentRuntimeStore(layout).save(runtime)


def _summary(context, *, started=('planner', 'developer')):
    return SimpleNamespace(
        project_root=str(context.paths.project_root),
        project_id=context.project.project_id,
        daemon_started=True,
        socket_path=str(context.paths.ccbd_socket_path),
        started=tuple(started),
        startup_run_id=None,
    )


def test_read_agent_availability_returns_saved_fields(tmp_path: Path) -> None:
    context = _context(tmp_path)
    _save_runtime(
        context,
        'planner',
        pane_state='dead',
        health='failed',
        failure_reason='provider exited',
        restart_count=2,
    )

    rows = start_availability.read_agent_availability(context, ('planner',))

    assert len(rows) == 1
    row = rows[0]
    assert row.agent_name == 'planner'
    assert row.pane_state == 'dead'
    assert row.health == 'failed'
    assert row.failure_reason == 'provider exited'
    assert row.restart_count == 2


def test_alive_pane_with_healthy_state_is_available(tmp_path: Path) -> None:
    context = _context(tmp_path)
    _save_runtime(context, 'developer')

    assert start_availability.unavailable_agents(
        start_availability.read_agent_availability(context, ('developer',))
    ) == ()


@pytest.mark.parametrize(
    'kwargs',
    [
        {'pane_state': 'dead'},
        {'pane_state': 'missing'},
        {'health': 'failed'},
        {'health': 'start-failed'},
        {'health': 'session-missing'},
    ],
)
def test_dead_pane_or_failed_health_is_unavailable(tmp_path: Path, kwargs) -> None:
    context = _context(tmp_path)
    _save_runtime(context, 'planner', **kwargs)

    rows = start_availability.unavailable_agents(
        start_availability.read_agent_availability(context, ('planner',))
    )

    assert [row.agent_name for row in rows] == ['planner']


def test_missing_runtime_record_is_not_flagged(tmp_path: Path) -> None:
    context = _context(tmp_path)

    rows = start_availability.read_agent_availability(context, ('ghost',))

    assert rows == ()


def test_describe_unavailable_lists_only_whitelisted_fields(tmp_path: Path) -> None:
    context = _context(tmp_path)
    _save_runtime(
        context,
        'planner',
        pane_state='dead',
        health='failed',
        failure_reason='ERR_UNSUPPORTED_ESM_URL_SCHEME',
        restart_count=2,
    )

    text = start_availability.describe_unavailable(
        start_availability.unavailable_agents(
            start_availability.read_agent_availability(context, ('planner',))
        )
    )

    assert 'planner(' in text
    assert 'pane=dead' in text
    assert 'restarts=2' in text
    assert 'ERR_UNSUPPORTED_ESM_URL_SCHEME' in text


def test_describe_unavailable_flattens_and_truncates_reason(tmp_path: Path) -> None:
    context = _context(tmp_path)
    _save_runtime(
        context,
        'planner',
        pane_state='dead',
        failure_reason='line one\nline two' + 'x' * 500,
    )

    text = start_availability.describe_unavailable(
        start_availability.unavailable_agents(
            start_availability.read_agent_availability(context, ('planner',))
        )
    )

    assert '\n' not in text
    assert len(text) < 300


def test_settle_returns_empty_when_every_agent_is_available(tmp_path: Path) -> None:
    context = _context(tmp_path)
    _save_runtime(context, 'planner')
    clock = iter([0.0, 0.5, 1.0, 1.5, 2.5])
    slept: list[float] = []

    rows = start_availability.wait_for_settled_availability(
        context,
        ('planner',),
        settle_s=2.0,
        sleep_fn=slept.append,
        monotonic_fn=lambda: next(clock),
    )

    assert rows == ()
    assert slept


def test_settle_skips_the_window_when_no_runtime_record_is_readable(tmp_path: Path) -> None:
    context = _context(tmp_path)
    slept: list[float] = []

    rows = start_availability.wait_for_settled_availability(
        context,
        ('planner',),
        settle_s=2.0,
        sleep_fn=slept.append,
        monotonic_fn=lambda: 0.0,
    )

    assert rows == ()
    assert slept == []


def test_settle_reports_dead_agent_without_waiting_the_full_window(tmp_path: Path) -> None:
    context = _context(tmp_path)
    _save_runtime(context, 'planner', pane_state='dead')
    slept: list[float] = []

    rows = start_availability.wait_for_settled_availability(
        context,
        ('planner',),
        settle_s=2.0,
        sleep_fn=slept.append,
        monotonic_fn=lambda: 0.0,
    )

    assert [row.agent_name for row in rows] == ['planner']
    assert slept == []


def test_settle_catches_a_pane_that_dies_inside_the_window(tmp_path: Path) -> None:
    context = _context(tmp_path)
    _save_runtime(context, 'planner')
    slept: list[float] = []
    clock = iter([0.0, 1.0, 2.5])
    ticks = {'count': 0}

    def _monotonic() -> float:
        return next(clock, 2.5)

    def _sleep(_seconds: float) -> None:
        slept.append(_seconds)
        ticks['count'] += 1
        if ticks['count'] == 1:
            # The provider exits right after the launch reported success.
            _save_runtime(context, 'planner', pane_state='dead', health='failed')

    rows = start_availability.wait_for_settled_availability(
        context,
        ('planner',),
        settle_s=2.0,
        sleep_fn=_sleep,
        monotonic_fn=_monotonic,
    )

    assert [row.agent_name for row in rows] == ['planner']


def test_render_start_reports_unavailable_agent() -> None:
    summary = SimpleNamespace(
        project_root='/repo',
        project_id='project-1',
        daemon_started=True,
        socket_path='/repo/.ccb/ccbd.sock',
        started=('planner', 'developer'),
        agent_unavailable=('planner(pane=dead, restarts=2)',),
    )

    lines = render_start(summary)

    assert any(line.startswith('agent_unavailable: planner(') for line in lines)


def test_render_start_omits_unavailable_line_when_everything_is_up() -> None:
    summary = SimpleNamespace(
        project_root='/repo',
        project_id='project-1',
        daemon_started=True,
        socket_path='/repo/.ccb/ccbd.sock',
        started=('planner', 'developer'),
        agent_unavailable=(),
    )

    lines = render_start(summary)

    assert not any(line.startswith('agent_unavailable:') for line in lines)


def _patch_start_plumbing(monkeypatch) -> None:
    monkeypatch.setattr(handlers_start, '_ensure_project_commands_approved', lambda *args: None)
    monkeypatch.setattr(handlers_start, '_ensure_herdr_runtime_evidence', lambda *args: None)
    monkeypatch.setenv('CCB_NO_ATTACH', '1')


def test_start_warns_about_a_provider_that_died_after_launch(monkeypatch, tmp_path, capsys) -> None:
    context = _context(tmp_path)
    _save_runtime(context, 'planner', pane_state='dead', health='failed', restart_count=2)
    _save_runtime(context, 'developer')
    summary = _summary(context)
    services = SimpleNamespace(
        start_agents=lambda *args, **kwargs: summary,
        render_start=render_start,
        write_lines=lambda out, lines: [print(line, file=out) for line in lines],
    )
    _patch_start_plumbing(monkeypatch)
    monkeypatch.setattr(
        handlers_start,
        'wait_for_settled_availability',
        lambda *args, **kwargs: start_availability.unavailable_agents(
            start_availability.read_agent_availability(context, ('planner', 'developer'))
        ),
    )

    assert handlers_start.handle_start(context, SimpleNamespace(), StringIO(), services) == 0

    err = capsys.readouterr().err
    assert 'planner' in err
    assert 'ccb ps' in err


def test_start_is_quiet_when_every_agent_is_running(monkeypatch, tmp_path, capsys) -> None:
    context = _context(tmp_path)
    _save_runtime(context, 'planner')
    _save_runtime(context, 'developer')
    summary = _summary(context)
    services = SimpleNamespace(
        start_agents=lambda *args, **kwargs: summary,
        render_start=render_start,
        write_lines=lambda out, lines: [print(line, file=out) for line in lines],
    )
    _patch_start_plumbing(monkeypatch)
    monkeypatch.setattr(handlers_start, 'wait_for_settled_availability', lambda *args, **kwargs: ())

    assert handlers_start.handle_start(context, SimpleNamespace(), StringIO(), services) == 0

    assert capsys.readouterr().err == ''


def test_timeout_message_names_the_unavailable_agent(monkeypatch, tmp_path) -> None:
    context = _context(tmp_path)
    _save_runtime(context, 'planner', pane_state='dead', health='failed', restart_count=2)
    exc = CcbdClientError('timed out')
    _patch_start_plumbing(monkeypatch)
    monkeypatch.setattr(
        handlers_start, '_start_agents', lambda *args, **kwargs: (_ for _ in ()).throw(exc)
    )
    monkeypatch.setattr(
        handlers_start,
        '_resolve_failed_start',
        lambda *args, **kwargs: StartOutcome('unknown', None, ''),
    )
    monkeypatch.setattr(handlers_start, '_requested_agent_names', lambda *args: ('planner',))

    with pytest.raises(RuntimeError, match='agents unavailable: planner'):
        handlers_start.handle_start(context, SimpleNamespace(), StringIO(), SimpleNamespace())


def test_late_ok_report_names_the_unavailable_agent(monkeypatch, tmp_path) -> None:
    context = _context(tmp_path)
    _save_runtime(context, 'planner', pane_state='dead', health='failed', restart_count=2)
    exc = CcbdClientError('timed out')
    _patch_start_plumbing(monkeypatch)
    monkeypatch.setattr(
        handlers_start, '_start_agents', lambda *args, **kwargs: (_ for _ in ()).throw(exc)
    )
    monkeypatch.setattr(
        handlers_start,
        '_resolve_failed_start',
        lambda *args, **kwargs: StartOutcome('ok', None, '/tmp/report.json'),
    )
    monkeypatch.setattr(handlers_start, '_requested_agent_names', lambda *args: ('planner',))

    with pytest.raises(RuntimeError) as raised:
        handlers_start.handle_start(context, SimpleNamespace(), StringIO(), SimpleNamespace())

    message = str(raised.value)
    assert 'final start response was not received' in message
    assert 'agents unavailable: planner' in message


def test_timeout_message_is_unchanged_when_nothing_is_unavailable(monkeypatch, tmp_path) -> None:
    context = _context(tmp_path)
    _save_runtime(context, 'planner')
    exc = CcbdClientError('timed out')
    _patch_start_plumbing(monkeypatch)
    monkeypatch.setattr(
        handlers_start, '_start_agents', lambda *args, **kwargs: (_ for _ in ()).throw(exc)
    )
    monkeypatch.setattr(
        handlers_start,
        '_resolve_failed_start',
        lambda *args, **kwargs: StartOutcome('unknown', None, ''),
    )
    monkeypatch.setattr(handlers_start, '_requested_agent_names', lambda *args: ('planner',))

    with pytest.raises(CcbdClientError, match='timed out'):
        handlers_start.handle_start(context, SimpleNamespace(), StringIO(), SimpleNamespace())