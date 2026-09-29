from __future__ import annotations

from dataclasses import dataclass

from .watch_fallback import load_persisted_terminal_watch_payload


_DEFAULT_POLL_INTERVAL_S = 0.1
_DEFAULT_TIMEOUT_S: float | None = 600.0
_HEALTH_CHECK_INTERVAL_S = 5.0
_MAX_HEALTH_CHECK_ERRORS = 3
_PANE_DEAD_CONFIRM_COUNT = 2
_FATAL_RUNTIME_HEALTHS = frozenset({
    'daemon-unavailable',
    'degraded',
    'failed',
    'namespace-crashed',
    'orphaned',
    'pane-dead',
    'pane-missing',
    'process-dead',
    'start-failed',
    'stopped',
})
_FATAL_RUNTIME_STATES = frozenset({'failed', 'stopped'})


@dataclass(frozen=True)
class WatchEventBatch:
    target: str
    job_id: str
    agent_name: str
    target_kind: str | None
    target_name: str
    provider: str | None
    provider_instance: str | None
    cursor: int
    generation: int | None
    terminal: bool
    status: str | None
    reply: str
    events: tuple[dict, ...]


def default_watch_timeout_seconds() -> float | None:
    return _DEFAULT_TIMEOUT_S


def default_watch_poll_interval_seconds() -> float:
    return _DEFAULT_POLL_INTERVAL_S


def watch_target(
    context,
    command,
    *,
    connect_mounted_daemon_fn,
    reconnect_error_classes: tuple[type[BaseException], ...],
    time_fn,
    sleep_fn,
    timeout_seconds_fn,
    poll_interval_seconds_fn,
):
    cursor = 0
    deadline = _watch_deadline(timeout_seconds_fn(), time_fn=time_fn)
    try:
        handle = connect_mounted_daemon_fn(context, allow_restart_stale=False)
    except reconnect_error_classes:
        fallback = _persisted_terminal_batch(context, command.target, cursor=cursor)
        if fallback is not None:
            yield fallback
            return
        raise
    assert handle.client is not None
    poll_interval = poll_interval_seconds_fn()
    last_health_check = -_HEALTH_CHECK_INTERVAL_S
    health_check_errors = 0
    pane_dead_count = 0

    while True:
        try:
            payload = handle.client.watch(command.target, cursor=cursor)
        except reconnect_error_classes:
            fallback = _persisted_terminal_batch(context, command.target, cursor=cursor)
            if fallback is not None:
                yield fallback
                return
            handle = _connect_handle(
                context,
                target=command.target,
                cursor=cursor,
                connect_mounted_daemon_fn=connect_mounted_daemon_fn,
                reconnect_error_classes=reconnect_error_classes,
                time_fn=time_fn,
                sleep_fn=sleep_fn,
                deadline=deadline,
                poll_interval_seconds_fn=poll_interval_seconds_fn,
            )
            if handle is None:
                fallback = _persisted_terminal_batch(context, command.target, cursor=cursor)
                if fallback is not None:
                    yield fallback
                    return
                raise RuntimeError(f"watch timed out for target {command.target}")
            sleep_fn(poll_interval)
            continue

        batch = _watch_batch_from_payload(command.target, payload)
        if batch.events:
            yield batch
        cursor = batch.cursor
        if batch.terminal:
            if not batch.events:
                yield batch
            return
        if _deadline_exceeded(deadline, time_fn=time_fn):
            # Final attempt: give the daemon one last chance to sync terminal
            # state before we bail out. This avoids false timeouts when the
            # agent finished just before the deadline but observer state hasn't
            # caught up yet.
            final_fallback = _persisted_terminal_batch(context, command.target, cursor=cursor)
            if final_fallback is not None:
                yield final_fallback
                return

            # Try an explicit fresh watch call with current cursor as a last-ditch
            # probe (some daemon implementations flush terminal state on fresh
            # watch requests that are not long-polling).
            try:
                fresh_payload = handle.client.watch(command.target, cursor=cursor)
                fresh_batch = _watch_batch_from_payload(command.target, fresh_payload)
                if fresh_batch.terminal:
                    yield fresh_batch
                    return
            except Exception:
                pass

            raise RuntimeError(f"watch timed out for target {command.target}")

        last_health_check, health_check_errors, pane_dead_count = _check_agent_health(
            handle.client,
            batch,
            reconnect_error_classes=reconnect_error_classes,
            last_health_check=last_health_check,
            health_check_errors=health_check_errors,
            pane_dead_count=pane_dead_count,
            now=time_fn(),
        )
        sleep_fn(poll_interval)


def _check_agent_health(
    client,
    batch: WatchEventBatch,
    *,
    reconnect_error_classes: tuple[type[BaseException], ...],
    last_health_check: float,
    health_check_errors: int,
    pane_dead_count: int,
    now: float,
) -> tuple[float, int, int]:
    queue_fn = getattr(client, 'queue', None)
    if not batch.agent_name or not callable(queue_fn):
        return last_health_check, health_check_errors, pane_dead_count
    if now - last_health_check < _HEALTH_CHECK_INTERVAL_S:
        return last_health_check, health_check_errors, pane_dead_count

    try:
        health_payload = queue_fn(batch.agent_name)
        agent = health_payload.get('agent') or {}
        runtime_health = str(agent.get('runtime_health') or '').strip().lower()
        runtime_state = str(agent.get('runtime_state') or '').strip().lower()
        if runtime_health in _FATAL_RUNTIME_HEALTHS or runtime_state in _FATAL_RUNTIME_STATES:
            observed = runtime_health or runtime_state or 'unknown'
            raise RuntimeError(
                f'Agent {batch.agent_name} health is {observed}. '
                f'Job {batch.job_id} cannot proceed.'
            )

        pane_state = agent.get('pane_state')
        if pane_state is not None and pane_state != 'alive':
            pane_dead_count += 1
            if pane_dead_count >= _PANE_DEAD_CONFIRM_COUNT:
                raise RuntimeError(
                    f'Agent {batch.agent_name} pane is {pane_state} '
                    f'(confirmed {pane_dead_count} times). '
                    f'Job {batch.job_id} is stuck.'
                )
        else:
            pane_dead_count = 0
        return now, 0, pane_dead_count
    except reconnect_error_classes + (AttributeError,) as exc:
        health_check_errors += 1
        if health_check_errors >= _MAX_HEALTH_CHECK_ERRORS:
            raise RuntimeError(
                f'Health check failed {health_check_errors} consecutive times '
                f'for agent {batch.agent_name}: {exc}'
            ) from exc
        return now, health_check_errors, pane_dead_count


def _watch_deadline(timeout_s: float | None, *, time_fn) -> float | None:
    if timeout_s is None:
        return None
    timeout = float(timeout_s)
    if timeout <= 0:
        return None
    return time_fn() + timeout


def _deadline_exceeded(deadline: float | None, *, time_fn) -> bool:
    return deadline is not None and time_fn() > deadline


def _watch_batch_from_payload(target: str, payload: dict) -> WatchEventBatch:
    return WatchEventBatch(
        target=target,
        job_id=payload["job_id"],
        agent_name=payload["agent_name"],
        target_kind=payload.get("target_kind"),
        target_name=payload.get("target_name") or payload.get("agent_name") or "",
        provider=payload.get("provider"),
        provider_instance=payload.get("provider_instance"),
        cursor=int(payload["cursor"]),
        generation=int(payload["generation"]) if payload.get("generation") is not None else None,
        terminal=bool(payload["terminal"]),
        status=payload.get("status"),
        reply=payload.get("reply") or "",
        events=tuple(payload.get("events", [])),
    )


def _connect_handle(
    context,
    *,
    target: str,
    cursor: int,
    connect_mounted_daemon_fn,
    reconnect_error_classes: tuple[type[BaseException], ...],
    time_fn,
    sleep_fn,
    deadline: float | None,
    poll_interval_seconds_fn,
):
    poll_interval = poll_interval_seconds_fn()
    while True:
        if deadline is not None and _deadline_exceeded(deadline, time_fn=time_fn):
            return None
        try:
            handle = connect_mounted_daemon_fn(context, allow_restart_stale=False)
        except reconnect_error_classes:
            fallback = _persisted_terminal_batch(context, target, cursor=cursor)
            if fallback is not None:
                return None
            sleep_fn(poll_interval)
            continue
        assert handle.client is not None
        return handle


def _persisted_terminal_batch(context, target: str, *, cursor: int) -> WatchEventBatch | None:
    payload = load_persisted_terminal_watch_payload(context, target, cursor=cursor)
    if payload is None:
        return None
    return _watch_batch_from_payload(target, payload)


__all__ = [
    "WatchEventBatch",
    "default_watch_poll_interval_seconds",
    "default_watch_timeout_seconds",
    "watch_target",
]
