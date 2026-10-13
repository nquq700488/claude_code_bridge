from __future__ import annotations

from dataclasses import dataclass

from .agent_health import HealthVerdict, classify_agent_health
from .watch_fallback import load_persisted_terminal_watch_payload


_DEFAULT_POLL_INTERVAL_S = 0.1
_DEFAULT_TIMEOUT_S: float | None = 600.0
_HEALTH_CHECK_INTERVAL_S = 5.0
_MAX_HEALTH_CHECK_ERRORS = 3
_PANE_DEAD_CONFIRM_COUNT = 2
# Auto-start is bound to the whole watch invocation and never resets: a flapping
# agent that alternates stopped/starting would otherwise be restarted forever.
_MAX_AUTO_START_ATTEMPTS = 2
_AUTO_START_RETRY_INTERVAL_S = 30.0
# A cold start can take a while; give it this long to show up before giving up.
_AUTO_START_GRACE_S = 90.0

_UNCHANGED_VERDICT = HealthVerdict("ok", "", "unchanged")


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


@dataclass(frozen=True)
class HealthCheckResult:
    last_health_check: float
    health_check_errors: int
    pane_dead_count: int
    verdict: HealthVerdict
    fatal_message: str = ""


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
    ensure_agent_running_fn=None,
    notice_fn=None,
    auto_start_enabled: bool = True,
):
    cursor = 0
    # A job that already finished must never trigger the side effects of
    # connecting: with auto-start enabled the initial connect can mount a
    # daemon the user deliberately stopped.  Consult the persisted snapshot
    # before touching the daemon at all.
    initial_fallback = _persisted_terminal_batch(context, command.target, cursor=cursor)
    if initial_fallback is not None:
        yield initial_fallback
        return

    deadline = _watch_deadline(timeout_seconds_fn(), time_fn=time_fn)
    try:
        handle = connect_mounted_daemon_fn(context, allow_restart_stale=auto_start_enabled)
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
    auto_start_attempts = 0
    auto_start_first_at: float | None = None
    auto_start_last_at: float | None = None

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
                auto_start_enabled=auto_start_enabled,
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

        now = time_fn()
        result = _check_agent_health(
            handle.client,
            batch,
            reconnect_error_classes=reconnect_error_classes,
            last_health_check=last_health_check,
            health_check_errors=health_check_errors,
            pane_dead_count=pane_dead_count,
            auto_start_enabled=auto_start_enabled,
            now=now,
        )
        last_health_check = result.last_health_check
        health_check_errors = result.health_check_errors
        pane_dead_count = result.pane_dead_count

        if result.fatal_message:
            # Every other failure path in this loop consults the persisted
            # terminal snapshot first; a job that finished while we were
            # looking at health must not surface as an error.
            fallback = _persisted_terminal_batch(context, command.target, cursor=cursor)
            if fallback is not None:
                yield fallback
                return
            raise RuntimeError(result.fatal_message)

        if result.verdict.action == "auto_start":
            if auto_start_first_at is None:
                auto_start_first_at = now
            if _auto_start_due(
                attempts=auto_start_attempts,
                last_attempt_at=auto_start_last_at,
                now=now,
            ):
                auto_start_attempts += 1
                auto_start_last_at = now
                # The pane is about to be recreated; a count accumulated before
                # this point would fire the pane-dead fatal mid-start.
                pane_dead_count = 0
                if callable(ensure_agent_running_fn):
                    ensure_agent_running_fn(
                        handle.client,
                        batch.agent_name,
                        notice_fn=notice_fn,
                    )
            elif now - auto_start_first_at >= _AUTO_START_GRACE_S:
                fallback = _persisted_terminal_batch(context, command.target, cursor=cursor)
                if fallback is not None:
                    yield fallback
                    return
                raise RuntimeError(
                    f"Agent {batch.agent_name} is {result.verdict.observed} and could not be "
                    f"auto-started after {auto_start_attempts} attempt(s). "
                    f"Job {batch.job_id} cannot proceed. "
                    f"Run `ccb start {batch.agent_name}` and retry."
                )

        sleep_fn(poll_interval)


def _auto_start_due(*, attempts: int, last_attempt_at: float | None, now: float) -> bool:
    if attempts >= _MAX_AUTO_START_ATTEMPTS:
        return False
    if last_attempt_at is None:
        return True
    return now - last_attempt_at >= _AUTO_START_RETRY_INTERVAL_S


def _check_agent_health(
    client,
    batch: WatchEventBatch,
    *,
    reconnect_error_classes: tuple[type[BaseException], ...],
    last_health_check: float,
    health_check_errors: int,
    pane_dead_count: int,
    auto_start_enabled: bool = True,
    now: float,
) -> HealthCheckResult:
    queue_fn = getattr(client, "queue", None)
    if not batch.agent_name or not callable(queue_fn):
        return HealthCheckResult(last_health_check, health_check_errors, pane_dead_count, _UNCHANGED_VERDICT)
    if now - last_health_check < _HEALTH_CHECK_INTERVAL_S:
        return HealthCheckResult(last_health_check, health_check_errors, pane_dead_count, _UNCHANGED_VERDICT)

    try:
        health_payload = queue_fn(batch.agent_name)
        agent = health_payload.get("agent") or {}
        verdict = classify_agent_health(
            runtime_health=agent.get("runtime_health"),
            runtime_state=agent.get("runtime_state"),
            auto_start_enabled=auto_start_enabled,
        )
        if verdict.action == "fatal":
            return HealthCheckResult(
                now,
                0,
                pane_dead_count,
                verdict,
                fatal_message=(
                    f"Agent {batch.agent_name} health is {verdict.observed}. "
                    f"Job {batch.job_id} cannot proceed."
                ),
            )
        if verdict.action != "ok":
            # The pane is expected to be missing or dead while it is being
            # started or healed by ccbd, so the verdict governs here rather
            # than the pane probe.  Without this, a 2-confirm pane-dead fatal
            # would fire ~10s in, long before the auto-start grace elapses.
            return HealthCheckResult(now, 0, 0, verdict)

        pane_state = agent.get("pane_state")
        if pane_state is not None and pane_state != "alive":
            pane_dead_count += 1
            if pane_dead_count >= _PANE_DEAD_CONFIRM_COUNT:
                return HealthCheckResult(
                    now,
                    0,
                    pane_dead_count,
                    verdict,
                    fatal_message=(
                        f"Agent {batch.agent_name} pane is {pane_state} "
                        f"(confirmed {pane_dead_count} times). "
                        f"Job {batch.job_id} is stuck."
                    ),
                )
        else:
            pane_dead_count = 0
        return HealthCheckResult(now, 0, pane_dead_count, verdict)
    except reconnect_error_classes + (AttributeError,) as exc:
        health_check_errors += 1
        if health_check_errors >= _MAX_HEALTH_CHECK_ERRORS:
            return HealthCheckResult(
                now,
                health_check_errors,
                pane_dead_count,
                _UNCHANGED_VERDICT,
                fatal_message=(
                    f"Health check failed {health_check_errors} consecutive times "
                    f"for agent {batch.agent_name}: {exc}"
                ),
            )
        return HealthCheckResult(now, health_check_errors, pane_dead_count, _UNCHANGED_VERDICT)


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
    auto_start_enabled: bool = True,
):
    poll_interval = poll_interval_seconds_fn()
    while True:
        if deadline is not None and _deadline_exceeded(deadline, time_fn=time_fn):
            return None
        try:
            handle = connect_mounted_daemon_fn(context, allow_restart_stale=auto_start_enabled)
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
