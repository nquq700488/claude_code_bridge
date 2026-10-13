from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from ccbd.services.start_policy import CcbdStartPolicy, CcbdStartPolicyStore
from ccbd.socket_client import CcbdClientError
from cli.services.agent_health import (
    AgentStartOutcome,
    classify_agent_health,
    ensure_agent_running,
)
from storage.paths import PathLayout


@pytest.mark.parametrize(
    ('runtime_health', 'runtime_state', 'expected'),
    [
        # Hard-blocked healths cannot be fixed by a `start`.
        ('provider-auth-revoked', 'idle', 'fatal'),
        ('provider-recovery-blocked', 'idle', 'fatal'),
        ('recovery-circuit-open', 'idle', 'fatal'),
        ('session-missing', 'idle', 'fatal'),
        # DEGRADED is ccbd's own recovery domain.
        ('pane-dead', 'degraded', 'wait'),
        ('pane-missing', 'degraded', 'wait'),
        ('degraded', 'degraded', 'fatal'),
        ('', 'degraded', 'fatal'),
        # herdr-only recoverable healths: the queue payload does not reveal the
        # backend, so these must keep failing fast rather than wait.
        ('process-dead', 'degraded', 'fatal'),
        ('namespace-crashed', 'degraded', 'fatal'),
        ('daemon-unavailable', 'degraded', 'fatal'),
        # The regression under repair: a never-started agent reads as stopped.
        ('stopped', 'stopped', 'auto_start'),
        ('healthy', 'stopped', 'auto_start'),
        ('', '', 'auto_start'),
        # Other not-running shapes.
        ('pane-dead', 'idle', 'auto_start'),
        ('pane-missing', 'idle', 'auto_start'),
        ('process-dead', 'idle', 'auto_start'),
        ('namespace-crashed', 'idle', 'auto_start'),
        ('failed', 'idle', 'auto_start'),
        ('start-failed', 'idle', 'auto_start'),
        ('orphaned', 'idle', 'auto_start'),
        ('healthy', 'failed', 'auto_start'),
        ('', 'failed', 'auto_start'),
        # Benign / in-flight.
        ('recovering', 'idle', 'wait'),
        ('healthy', 'idle', 'ok'),
        ('healthy', 'busy', 'ok'),
        ('healthy', 'starting', 'ok'),
        ('', 'idle', 'ok'),
        ('daemon-unavailable', 'idle', 'fatal'),
    ],
)
def test_classify_agent_health_table(runtime_health: str, runtime_state: str, expected: str) -> None:
    verdict = classify_agent_health(runtime_health=runtime_health, runtime_state=runtime_state)

    assert verdict.action == expected


@pytest.mark.parametrize(
    ('runtime_health', 'runtime_state', 'expected'),
    [
        # Legacy sets only.  `session-missing` and the recovery-blocked healths
        # were never fatal, so disabling auto-start must not make them fatal.
        ('session-missing', 'idle', 'ok'),
        ('provider-auth-revoked', 'idle', 'ok'),
        ('recovery-circuit-open', 'idle', 'ok'),
        ('recovering', 'idle', 'ok'),
        ('healthy', 'busy', 'ok'),
        ('stopped', 'stopped', 'fatal'),
        ('stopped', 'idle', 'fatal'),
        ('healthy', 'stopped', 'fatal'),
        ('healthy', 'failed', 'fatal'),
        ('degraded', 'idle', 'fatal'),
        ('pane-dead', 'idle', 'fatal'),
    ],
)
def test_classify_agent_health_disabled_matches_legacy_sets(
    runtime_health: str, runtime_state: str, expected: str
) -> None:
    verdict = classify_agent_health(
        runtime_health=runtime_health,
        runtime_state=runtime_state,
        auto_start_enabled=False,
    )

    assert verdict.action == expected


def test_classify_agent_health_observed_prefers_health_then_state() -> None:
    assert classify_agent_health(runtime_health='healthy', runtime_state='stopped').observed == 'healthy'
    assert classify_agent_health(runtime_health='', runtime_state='stopped').observed == 'stopped'
    assert classify_agent_health(runtime_health=None, runtime_state=None).observed == 'unknown'


class _FakeStartClient:
    def __init__(
        self,
        *,
        ping_payload: dict | None = None,
        ping_error: Exception | None = None,
        start_error: Exception | None = None,
    ) -> None:
        self._ping_payload = ping_payload or {}
        self._ping_error = ping_error
        self._start_error = start_error
        self.ping_targets: list[str] = []
        self.start_calls: list[dict] = []
        self.timeouts: list[float] = []

    def ping(self, target: str) -> dict:
        self.ping_targets.append(target)
        if self._ping_error is not None:
            raise self._ping_error
        return dict(self._ping_payload)

    def start(self, **kwargs) -> dict:
        self.start_calls.append(kwargs)
        if self._start_error is not None:
            raise self._start_error
        return {'started': list(kwargs.get('agent_names') or ())}

    def with_timeout(self, timeout_s: float):
        self.timeouts.append(timeout_s)
        return self


def test_ensure_agent_running_inherits_persisted_start_policy() -> None:
    client = _FakeStartClient(
        ping_payload={
            'start_policy_auto_permission': False,
            'start_policy_recovery_restore': False,
        }
    )
    notices: list[str] = []

    outcome = ensure_agent_running(client, 'reviewer', notice_fn=notices.append)

    assert outcome == AgentStartOutcome('reviewer', attempted=True, ok=True)
    assert client.ping_targets == ['ccbd']
    assert client.start_calls == [
        {'agent_names': ('reviewer',), 'restore': False, 'auto_permission': False}
    ]
    assert len(notices) == 1


def test_ensure_agent_running_defaults_to_bare_ccb_when_policy_is_unavailable() -> None:
    client = _FakeStartClient(ping_error=CcbdClientError('no policy'))

    outcome = ensure_agent_running(client, 'reviewer', notice_fn=None)

    assert outcome.ok is True
    assert client.start_calls == [
        {'agent_names': ('reviewer',), 'restore': True, 'auto_permission': True}
    ]


def test_ensure_agent_running_falls_back_to_local_policy_when_ping_fails(tmp_path: Path) -> None:
    # `start` persists whatever we send, so a ping failure must not silently
    # rewrite a `ccb -s` project's safe-mode policy into auto-permission.
    layout = PathLayout(tmp_path)
    CcbdStartPolicyStore(layout).save(
        CcbdStartPolicy(project_id='proj_demo', auto_permission=False, recovery_restore=False)
    )
    client = _FakeStartClient(ping_error=CcbdClientError('ping failed'))
    context = SimpleNamespace(paths=layout)

    outcome = ensure_agent_running(client, 'reviewer', context=context, notice_fn=None)

    assert outcome.ok is True
    assert client.start_calls == [
        {'agent_names': ('reviewer',), 'restore': False, 'auto_permission': False}
    ]


def test_ensure_agent_running_prefers_daemon_policy_over_local_record(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path)
    CcbdStartPolicyStore(layout).save(
        CcbdStartPolicy(project_id='proj_demo', auto_permission=False, recovery_restore=False)
    )
    client = _FakeStartClient(
        ping_payload={
            'start_policy_auto_permission': True,
            'start_policy_recovery_restore': True,
        }
    )
    context = SimpleNamespace(paths=layout)

    ensure_agent_running(client, 'reviewer', context=context, notice_fn=None)

    assert client.start_calls == [
        {'agent_names': ('reviewer',), 'restore': True, 'auto_permission': True}
    ]


def test_ensure_agent_running_refuses_when_policy_record_is_unreadable(tmp_path: Path) -> None:
    # A record that exists but cannot be parsed is not "no record": `start`
    # would persist whatever we send, so we must not guess permissively.
    layout = PathLayout(tmp_path)
    layout.ccbd_start_policy_path.parent.mkdir(parents=True, exist_ok=True)
    layout.ccbd_start_policy_path.write_text('{ not json', encoding='utf-8')
    client = _FakeStartClient(ping_error=CcbdClientError('ping failed'))
    context = SimpleNamespace(paths=layout)
    notices: list[str] = []

    outcome = ensure_agent_running(client, 'reviewer', context=context, notice_fn=notices.append)

    assert outcome.attempted is False
    assert outcome.ok is False
    assert client.start_calls == []
    assert len(notices) == 1
    assert 'start policy' in notices[0]


def test_ensure_agent_running_treats_unstattable_policy_as_unreadable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Path.exists() returns False on EACCES, which would let an unreadable
    # policy masquerade as "no policy" and fall back to permissive defaults.
    layout = PathLayout(tmp_path)
    layout.ccbd_start_policy_path.parent.mkdir(parents=True, exist_ok=True)
    layout.ccbd_start_policy_path.write_text('{}', encoding='utf-8')

    real_stat = os.stat

    def _stat(path, *args, **kwargs):
        if str(path) == str(layout.ccbd_start_policy_path):
            raise PermissionError(13, 'Permission denied')
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, 'stat', _stat)
    client = _FakeStartClient(ping_error=CcbdClientError('ping failed'))
    context = SimpleNamespace(paths=layout)

    outcome = ensure_agent_running(client, 'reviewer', context=context, notice_fn=None)

    assert outcome.attempted is False
    assert client.start_calls == []


def test_ensure_agent_running_is_best_effort_when_start_times_out() -> None:
    # A cold start routinely outlives the RPC budget; the health poll decides
    # the real outcome, so a timeout must not propagate.
    client = _FakeStartClient(start_error=CcbdClientError('timed out'))
    notices: list[str] = []

    outcome = ensure_agent_running(client, 'reviewer', notice_fn=notices.append)

    assert outcome.attempted is True
    assert outcome.ok is False
    assert outcome.detail == 'timed out'
    assert len(notices) == 1


def test_ensure_agent_running_skips_clients_without_start_endpoint() -> None:
    class _NoStartClient:
        pass

    outcome = ensure_agent_running(_NoStartClient(), 'reviewer', notice_fn=None)

    assert outcome.attempted is False
    assert outcome.ok is False


def test_ensure_agent_running_rejects_empty_agent_name() -> None:
    outcome = ensure_agent_running(_FakeStartClient(), '  ', notice_fn=None)

    assert outcome.attempted is False


def test_ensure_agent_running_swallows_notice_failures() -> None:
    client = _FakeStartClient()

    def _explode(_message: str) -> None:
        raise RuntimeError('stderr closed')

    outcome = ensure_agent_running(client, 'reviewer', notice_fn=_explode)

    assert outcome.ok is True
