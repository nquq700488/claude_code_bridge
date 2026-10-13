"""Agent health classification and best-effort auto-start for watch loops.

The daemon reports a missing runtime and a deliberately stopped agent with the
same sentinel value (``runtime_state``/``runtime_health`` == ``'stopped'``), and
nothing in ccbd's supervision brings a STOPPED agent back: background recovery
requires ``state is DEGRADED``.  Watch loops therefore have to decide for
themselves whether to keep waiting, to start the agent, or to give up.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from typing import Callable, Literal

from ccbd.services.runtime_recovery_policy import (
    RECOVERABLE_RUNTIME_HEALTHS,
    RECOVERY_BLOCKED_RUNTIME_HEALTHS,
)
from ccbd.services.start_policy import CcbdStartPolicyStore
from ccbd.startup_policy import STARTUP_TRANSACTION_TIMEOUT_S


HealthAction = Literal["ok", "wait", "auto_start", "fatal"]
NoticeFn = Callable[[str], None]

# Healths a `start` cannot fix; retrying would only hide the real cause.
_UNFIXABLE_HEALTHS = RECOVERY_BLOCKED_RUNTIME_HEALTHS | frozenset({"session-missing"})

# Healths ccbd heals on its own, but only while the agent is DEGRADED.  The
# wider herdr-only set is deliberately excluded: the queue payload does not say
# which backend is in play, so waiting on `process-dead` / `namespace-crashed`
# could stall a non-herdr project until the watch timeout instead of failing
# fast the way it does today.
_DAEMON_RECOVERABLE_HEALTHS = RECOVERABLE_RUNTIME_HEALTHS

# Healths where the agent is simply not up and a `start` is the right move.
# `daemon-unavailable` is deliberately absent: it describes the daemon, not the
# agent, and restarting the agent cannot fix it.
_STARTABLE_HEALTHS = frozenset(
    {
        "failed",
        "orphaned",
        "pane-dead",
        "pane-missing",
        "process-dead",
        "namespace-crashed",
        "start-failed",
    }
)

# Unhealthy but not startable, and not already covered above.
_UNHEALTHY_HEALTHS = frozenset({"daemon-unavailable", "degraded"})

_RUNNING_STATES = frozenset({"busy", "idle", "starting", "stopping"})

# The pre-auto-start fatal sets.  `CCB_WATCH_AUTO_START=0` must reproduce these
# verbatim, so they are kept separate from the classification above rather than
# derived from it.
_LEGACY_FATAL_HEALTHS = frozenset(
    {
        "daemon-unavailable",
        "degraded",
        "failed",
        "namespace-crashed",
        "orphaned",
        "pane-dead",
        "pane-missing",
        "process-dead",
        "start-failed",
        "stopped",
    }
)
_LEGACY_FATAL_STATES = frozenset({"failed", "stopped"})


@dataclass(frozen=True)
class HealthVerdict:
    action: HealthAction
    observed: str
    reason: str


@dataclass(frozen=True)
class AgentStartOutcome:
    agent_name: str
    attempted: bool
    ok: bool
    detail: str = ""


def classify_agent_health(
    *,
    runtime_health: object,
    runtime_state: object,
    auto_start_enabled: bool = True,
) -> HealthVerdict:
    """Decide what a watch loop should do about an agent's reported health."""
    health = _normalize(runtime_health)
    state = _normalize(runtime_state)
    observed = health or state or "unknown"

    # Step 0: with auto-start off, reproduce the legacy sets exactly and return.
    # `session-missing` and the recovery-blocked healths are *not* in those
    # sets, so running the stage below unconditionally would make the disabled
    # path stricter than the behavior it is supposed to preserve.
    if not auto_start_enabled:
        if health in _LEGACY_FATAL_HEALTHS or state in _LEGACY_FATAL_STATES:
            return HealthVerdict("fatal", observed, "legacy_fatal")
        return HealthVerdict("ok", observed, "legacy_ok")

    # Stage A: unfixable regardless of state.
    if health in _UNFIXABLE_HEALTHS:
        return HealthVerdict("fatal", observed, "hard_blocked")

    # Stage B: ccbd is already driving recovery for a degraded agent.  Do not
    # race it; do not fail fast while it is working.
    if state == "degraded":
        if health in _DAEMON_RECOVERABLE_HEALTHS:
            return HealthVerdict("wait", observed, "daemon_recovering")
        return HealthVerdict("fatal", observed, "degraded")

    # Stage C: state wins over health.  A stopped agent reports `health=healthy`
    # in practice, so keying on health alone would wait forever.
    if state == "stopped" or health == "stopped":
        return HealthVerdict("auto_start", observed, "stopped")
    if not health and not state:
        return HealthVerdict("auto_start", observed, "runtime_missing")
    if state == "failed" or health in {"failed", "start-failed"}:
        return HealthVerdict("auto_start", observed, "start_failed")
    if health in _STARTABLE_HEALTHS:
        return HealthVerdict("auto_start", observed, "not_running")
    if health == "recovering":
        return HealthVerdict("wait", observed, "recovering")
    if health in _UNHEALTHY_HEALTHS:
        return HealthVerdict("fatal", observed, "unhealthy")
    if state in _RUNNING_STATES:
        return HealthVerdict("ok", observed, "running")
    return HealthVerdict("ok", observed, "unknown")


def ensure_agent_running(
    client,
    agent_name: str,
    *,
    context=None,
    notice_fn: NoticeFn | None = None,
    start_rpc_timeout_s: float | None = None,
) -> AgentStartOutcome:
    """Best-effort `start` for a single agent.

    A cold start routinely outlives the control-plane RPC budget, so a timeout
    here is not a failure: the caller's health poll decides the real outcome.
    """
    name = str(agent_name or "").strip()
    if not name:
        return AgentStartOutcome("", attempted=False, ok=False, detail="missing agent name")

    start_fn = getattr(client, "start", None)
    if not callable(start_fn):
        return AgentStartOutcome(name, attempted=False, ok=False, detail="client has no start endpoint")

    restore, auto_permission, policy_ok = _start_policy_options(client, context)
    if not policy_ok:
        _notify(
            notice_fn,
            f"ccb: cannot read the project start policy for {name}; refusing to "
            f"auto-start it so its permission mode is not changed. "
            f"Run `ccb start {name}` explicitly if that is intended.",
        )
        return AgentStartOutcome(name, attempted=False, ok=False, detail="start policy unreadable")

    _notify(
        notice_fn,
        f"ccb: agent {name} is not running; starting it "
        f"(restore={restore}, auto_permission={auto_permission})...",
    )
    timeout_s = (
        STARTUP_TRANSACTION_TIMEOUT_S if start_rpc_timeout_s is None else float(start_rpc_timeout_s)
    )
    try:
        _with_timeout(client, timeout_s).start(
            agent_names=(name,),
            restore=restore,
            auto_permission=auto_permission,
        )
    except Exception as exc:  # noqa: BLE001 - deliberately best-effort
        return AgentStartOutcome(name, attempted=True, ok=False, detail=str(exc) or type(exc).__name__)
    return AgentStartOutcome(name, attempted=True, ok=True)


def _start_policy_options(client, context) -> tuple[bool, bool, bool]:
    """Resolve (restore, auto_permission, trustworthy) for the auto-start.

    The daemon's copy is authoritative, but `start` persists whatever we send,
    so falling back to a permissive default when the ping is unavailable would
    silently rewrite a `ccb -s` (safe mode) project's policy.  Read the same
    record from disk first.  A record that exists but cannot be read is not the
    same as no record at all: we refuse rather than guess, because guessing
    permissively is exactly the escalation this guards against.
    """
    payload = _ccbd_ping_payload(client)
    restore = _as_optional_bool(payload.get("start_policy_recovery_restore"))
    auto_permission = _as_optional_bool(payload.get("start_policy_auto_permission"))
    if restore is not None and auto_permission is not None:
        return restore, auto_permission, True

    local, unreadable = _local_start_policy(context)
    if unreadable:
        return True, True, False
    if restore is None:
        restore = _as_optional_bool(local.get("recovery_restore"))
    if auto_permission is None:
        auto_permission = _as_optional_bool(local.get("auto_permission"))
    # No record anywhere: a project that never ran `ccb start`, where the
    # bare-`ccb` defaults are the faithful choice.
    return (
        True if restore is None else restore,
        True if auto_permission is None else auto_permission,
        True,
    )


def _local_start_policy(context) -> tuple[Mapping, bool]:
    """Return (policy_fields, unreadable)."""
    paths = getattr(context, "paths", None)
    if paths is None:
        return {}, False
    # `Path.exists()` reports False for EACCES too, which would let an
    # unreadable policy masquerade as "no policy". Only a definite ENOENT
    # means the project never ran `ccb start`.
    try:
        os.stat(paths.ccbd_start_policy_path)
    except FileNotFoundError:
        return {}, False
    except OSError:  # noqa: BLE001 - present but not statable
        return {}, True
    try:
        policy = CcbdStartPolicyStore(paths).load()
    except Exception:  # noqa: BLE001 - a corrupt record must not read as absent
        return {}, True
    if policy is None:
        return {}, False
    return {"recovery_restore": policy.recovery_restore, "auto_permission": policy.auto_permission}, False


def _ccbd_ping_payload(client) -> Mapping:
    ping_fn = getattr(client, "ping", None)
    if not callable(ping_fn):
        return {}
    try:
        payload = ping_fn("ccbd")
    except Exception:  # noqa: BLE001 - policy lookup is optional context
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _with_timeout(client, timeout_s: float):
    if timeout_s is None or timeout_s <= 0:
        return client
    with_timeout = getattr(client, "with_timeout", None)
    if not callable(with_timeout):
        return client
    return with_timeout(timeout_s)


def _notify(notice_fn: NoticeFn | None, message: str) -> None:
    if notice_fn is None:
        return
    try:
        notice_fn(message)
    except Exception:  # noqa: BLE001 - notices must never break the watch
        pass


def _normalize(value: object) -> str:
    return str(value or "").strip().lower()


def _as_optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


__all__ = [
    "AgentStartOutcome",
    "HealthAction",
    "HealthVerdict",
    "classify_agent_health",
    "ensure_agent_running",
]
