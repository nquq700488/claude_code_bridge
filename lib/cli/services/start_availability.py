from __future__ import annotations

from dataclasses import dataclass
import os
import time

from agents.store import AgentRuntimeStore

# A start transaction finishing only proves that every provider was *launched*.
# A provider that exits straight after its launch (a wrong Node runtime, a
# rejected credential, a crashing CLI) leaves `startup-report.json` at
# `status: ok` while the pane is already dead, so the client has to look at the
# runtime records itself before telling the user the start succeeded.
_UNAVAILABLE_PANE_STATES = frozenset({'dead', 'missing'})
_UNAVAILABLE_HEALTHS = frozenset({'failed', 'start-failed', 'session-missing'})
_REASON_LIMIT = 120
_POLL_INTERVAL_S = 0.25
_DEFAULT_SETTLE_S = 2.0


@dataclass(frozen=True)
class AgentAvailability:
    agent_name: str
    pane_state: str | None
    health: str | None
    failure_reason: str | None
    restart_count: int
    recovery_failure_count: int

    @property
    def available(self) -> bool:
        if (self.pane_state or '') in _UNAVAILABLE_PANE_STATES:
            return False
        return (self.health or '') not in _UNAVAILABLE_HEALTHS


def read_agent_availability(context, agent_names) -> tuple[AgentAvailability, ...]:
    """Read the current runtime record of every named agent.

    Read-only and best effort: an absent or unreadable record yields no row at
    all, so an unreadable state can never be reported as a failure.
    """
    store = AgentRuntimeStore(context.paths)
    rows: list[AgentAvailability] = []
    for raw_name in agent_names or ():
        name = str(raw_name or '').strip()
        if not name:
            continue
        runtime = store.load_best_effort(name)
        if runtime is None:
            continue
        rows.append(
            AgentAvailability(
                agent_name=name,
                pane_state=_clean(runtime.pane_state),
                health=_clean(runtime.health),
                failure_reason=_clean(runtime.last_failure_reason),
                restart_count=_as_int(runtime.restart_count),
                recovery_failure_count=_as_int(runtime.recovery_failure_count),
            )
        )
    return tuple(rows)


def unavailable_agents(rows) -> tuple[AgentAvailability, ...]:
    return tuple(row for row in rows or () if not row.available)


def describe_unavailable(rows) -> str:
    return ', '.join(describe_agents(rows))


def describe_agents(rows) -> tuple[str, ...]:
    return tuple(_describe_one(row) for row in rows or ())


def format_unavailable_notice(rows) -> str:
    return (
        f'ccb: {describe_unavailable(rows)} - the provider is not usable; '
        'the daemon keeps retrying with backoff. Run `ccb ps` for details.'
    )


def wait_for_settled_availability(
    context,
    agent_names,
    *,
    settle_s: float | None = None,
    poll_interval_s: float = _POLL_INTERVAL_S,
    sleep_fn=time.sleep,
    monotonic_fn=time.monotonic,
) -> tuple[AgentAvailability, ...]:
    """Check availability once the launch result can be trusted.

    Providers die a moment *after* their pane was created, so a single read at
    start-return time misses them.  A dead pane is reported immediately, while
    an apparently healthy one is re-checked until the settle window closes.
    """
    names = tuple(dict.fromkeys(str(name or '').strip() for name in agent_names or ()))
    names = tuple(name for name in names if name)
    if not names:
        return ()
    window = _settle_seconds() if settle_s is None else max(0.0, float(settle_s))
    deadline = monotonic_fn() + window
    while True:
        rows = read_agent_availability(context, names)
        bad = unavailable_agents(rows)
        if bad:
            return bad
        if not rows:
            # No readable runtime record is not evidence of a problem, and
            # waiting cannot turn it into one, so the window buys nothing.
            return ()
        remaining = deadline - monotonic_fn()
        if remaining <= 0:
            return ()
        sleep_fn(min(poll_interval_s, remaining))


def _describe_one(row: AgentAvailability) -> str:
    details: list[str] = []
    if row.pane_state:
        details.append(f'pane={row.pane_state}')
    if row.restart_count:
        details.append(f'restarts={row.restart_count}')
    if row.recovery_failure_count:
        details.append(f'recovery_failures={row.recovery_failure_count}')
    reason = _single_line(row.failure_reason)
    if reason:
        details.append(reason)
    return f'{row.agent_name}({", ".join(details)})' if details else f'{row.agent_name}(unavailable)'


def _settle_seconds() -> float:
    raw = str(os.environ.get('CCB_START_AVAILABILITY_SETTLE_S') or '').strip()
    if not raw:
        return _DEFAULT_SETTLE_S
    try:
        return max(0.0, float(raw))
    except Exception:
        return _DEFAULT_SETTLE_S


def _single_line(value: str | None) -> str:
    text = ' '.join(str(value or '').split())
    return text if len(text) <= _REASON_LIMIT else text[: _REASON_LIMIT - 1].rstrip() + '…'


def _clean(value: object) -> str | None:
    text = str(value or '').strip()
    return text or None


def _as_int(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


__all__ = [
    'AgentAvailability',
    'describe_agents',
    'describe_unavailable',
    'format_unavailable_notice',
    'read_agent_availability',
    'unavailable_agents',
    'wait_for_settled_availability',
]