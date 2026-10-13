from __future__ import annotations

from collections.abc import Callable
from typing import TextIO

from cli.services.agent_health import classify_agent_health
from cli.services.watch import WatchEventBatch
from cli.services.watch_fallback import load_persisted_terminal_watch_payload


_HEALTH_CHECK_INTERVAL = 5.0
_MAX_HEALTH_CHECK_ERRORS = 3
_PANE_DEAD_CONFIRM_COUNT = 2
# Bound auto-start to the whole watch call; see watch_runtime for the rationale.
_MAX_AUTO_START_ATTEMPTS = 2
_AUTO_START_RETRY_INTERVAL = 30.0
_AUTO_START_GRACE = 90.0


def watch_ask_job(
    context,
    job_id: str,
    out: TextIO,
    *,
    timeout: float | None,
    emit_output: bool,
    connect_mounted_daemon_fn: Callable,
    reconnect_error_classes: tuple[type[BaseException], ...],
    monotonic_fn: Callable[[], float],
    sleep_fn: Callable[[float], None],
    poll_interval_seconds_fn: Callable[[], float],
    timeout_seconds_fn: Callable[[], float],
    render_watch_batch_fn: Callable[[WatchEventBatch], tuple[str, ...]],
    write_lines_fn: Callable[[TextIO, tuple[str, ...]], None],
    ensure_agent_running_fn: Callable | None = None,
    notice_fn: Callable[[str], None] | None = None,
    auto_start_enabled: bool = True,
) -> WatchEventBatch:
    cursor = 0
    # A finished job must not connect at all: with auto-start on, that connect
    # can mount a daemon the user deliberately stopped.
    initial_fallback = _persisted_terminal_batch(context, job_id, cursor=cursor)
    if initial_fallback is not None:
        if emit_output:
            write_lines_fn(out, render_watch_batch_fn(initial_fallback))
        return initial_fallback

    deadline = _watch_deadline(timeout, timeout_seconds_fn=timeout_seconds_fn, monotonic_fn=monotonic_fn)
    poll_interval = poll_interval_seconds_fn()
    try:
        handle = connect_mounted_daemon_fn(context, allow_restart_stale=auto_start_enabled)
    except reconnect_error_classes:
        fallback = _persisted_terminal_batch(context, job_id, cursor=cursor)
        if fallback is not None:
            if emit_output:
                write_lines_fn(out, render_watch_batch_fn(fallback))
            return fallback
        raise
    assert handle.client is not None
    client = handle.client

    last_health_check = 0.0
    health_check_errors = 0
    pane_dead_count = 0
    auto_start_attempts = 0
    auto_start_first_at: float | None = None
    auto_start_last_at: float | None = None

    while True:
        try:
            payload = client.watch(job_id, cursor=cursor)
        except reconnect_error_classes:
            fallback = _persisted_terminal_batch(context, job_id, cursor=cursor)
            if fallback is not None:
                if emit_output:
                    write_lines_fn(out, render_watch_batch_fn(fallback))
                return fallback
            client = _connect_client(
                context,
                job_id=job_id,
                cursor=cursor,
                connect_mounted_daemon_fn=connect_mounted_daemon_fn,
                reconnect_error_classes=reconnect_error_classes,
                monotonic_fn=monotonic_fn,
                sleep_fn=sleep_fn,
                deadline=deadline,
                poll_interval=poll_interval,
                auto_start_enabled=auto_start_enabled,
            )
            if client is None:
                fallback = _persisted_terminal_batch(context, job_id, cursor=cursor)
                if fallback is not None:
                    if emit_output:
                        write_lines_fn(out, render_watch_batch_fn(fallback))
                    return fallback
                raise RuntimeError(f'watch timed out for {job_id}')
            sleep_fn(poll_interval)
            continue

        batch = _watch_batch_from_payload(job_id, payload)
        if emit_output and batch.events:
            write_lines_fn(out, render_watch_batch_fn(batch))
        cursor = batch.cursor
        if batch.terminal:
            if emit_output and not batch.events:
                write_lines_fn(out, render_watch_batch_fn(batch))
            return batch
        if _deadline_exceeded(deadline, monotonic_fn=monotonic_fn):
            # Final attempt: give the daemon one last chance to sync terminal
            # state before we bail out.
            final_fallback = _persisted_terminal_batch(context, job_id, cursor=cursor)
            if final_fallback is not None:
                if emit_output:
                    write_lines_fn(out, render_watch_batch_fn(final_fallback))
                return final_fallback

            # Try an explicit fresh watch call as a last-ditch probe.
            try:
                fresh_payload = client.watch(job_id, cursor=cursor)
                fresh_batch = _watch_batch_from_payload(job_id, fresh_payload)
                if fresh_batch.terminal:
                    if emit_output:
                        write_lines_fn(out, render_watch_batch_fn(fresh_batch))
                    return fresh_batch
            except Exception:
                pass

            raise RuntimeError(f'watch timed out for {job_id}')

        # Periodic health check: detect pane death or a not-running agent early
        agent_name = batch.agent_name
        if agent_name:
            now = monotonic_fn()
            if now - last_health_check >= _HEALTH_CHECK_INTERVAL:
                last_health_check = now
                try:
                    health_payload = client.queue(agent_name)
                    agent = health_payload.get('agent', {})
                    pane_state = agent.get('pane_state')
                    verdict = classify_agent_health(
                        runtime_health=agent.get('runtime_health'),
                        runtime_state=agent.get('runtime_state'),
                        auto_start_enabled=auto_start_enabled,
                    )

                    if verdict.action == 'fatal':
                        fallback = _persisted_terminal_batch(context, job_id, cursor=cursor)
                        if fallback is not None:
                            if emit_output:
                                write_lines_fn(out, render_watch_batch_fn(fallback))
                            return fallback
                        raise RuntimeError(
                            f'Agent {agent_name} health is {verdict.observed}. '
                            f'Job {job_id} cannot proceed. '
                            f'Check the pane: tmux -S {context.paths.ccbd_tmux_socket} attach'
                        )

                    if verdict.action != 'ok':
                        # The pane is expected to be down while the agent is
                        # being started or healed, so the verdict governs here
                        # rather than the pane probe.
                        pane_dead_count = 0
                        if verdict.action == 'auto_start':
                            if auto_start_first_at is None:
                                auto_start_first_at = now
                            if _auto_start_due(
                                attempts=auto_start_attempts,
                                last_attempt_at=auto_start_last_at,
                                now=now,
                            ):
                                auto_start_attempts += 1
                                auto_start_last_at = now
                                if callable(ensure_agent_running_fn):
                                    ensure_agent_running_fn(client, agent_name, notice_fn=notice_fn)
                            elif now - auto_start_first_at >= _AUTO_START_GRACE:
                                fallback = _persisted_terminal_batch(context, job_id, cursor=cursor)
                                if fallback is not None:
                                    if emit_output:
                                        write_lines_fn(out, render_watch_batch_fn(fallback))
                                    return fallback
                                raise RuntimeError(
                                    f'Agent {agent_name} is {verdict.observed} and could not be '
                                    f'auto-started after {auto_start_attempts} attempt(s). '
                                    f'Job {job_id} cannot proceed. '
                                    f'Run `ccb start {agent_name}` and retry.'
                                )
                    else:
                        # Pane state is a secondary signal. Require two consecutive
                        # non-alive readings before aborting to avoid false positives
                        # during brief tmux hiccups.
                        if pane_state is not None and pane_state != 'alive':
                            pane_dead_count += 1
                            if pane_dead_count >= _PANE_DEAD_CONFIRM_COUNT:
                                raise RuntimeError(
                                    f'Agent {agent_name} pane is {pane_state} '
                                    f'(confirmed {pane_dead_count} times). '
                                    f'Job {job_id} is stuck. '
                                    f'Check the pane: tmux -S {context.paths.ccbd_tmux_socket} attach'
                                )
                        else:
                            pane_dead_count = 0

                    health_check_errors = 0
                except reconnect_error_classes + (AttributeError,) as exc:
                    health_check_errors += 1
                    if health_check_errors >= _MAX_HEALTH_CHECK_ERRORS:
                        raise RuntimeError(
                            f'Health check failed {health_check_errors} consecutive times '
                            f'for agent {agent_name}: {exc}'
                        )
        sleep_fn(poll_interval)


def _auto_start_due(*, attempts: int, last_attempt_at: float | None, now: float) -> bool:
    if attempts >= _MAX_AUTO_START_ATTEMPTS:
        return False
    if last_attempt_at is None:
        return True
    return now - last_attempt_at >= _AUTO_START_RETRY_INTERVAL


def _watch_deadline(
    timeout: float | None,
    *,
    timeout_seconds_fn: Callable[[], float],
    monotonic_fn: Callable[[], float],
) -> float | None:
    timeout_s = timeout_seconds_fn() if timeout is None else float(timeout)
    if timeout_s <= 0:
        return None
    return monotonic_fn() + timeout_s


def _deadline_exceeded(deadline: float | None, *, monotonic_fn: Callable[[], float]) -> bool:
    return deadline is not None and monotonic_fn() > deadline


def _watch_batch_from_payload(job_id: str, payload: dict) -> WatchEventBatch:
    return WatchEventBatch(
        target=job_id,
        job_id=payload['job_id'],
        agent_name=payload.get('agent_name') or '',
        target_kind=payload.get('target_kind'),
        target_name=payload.get('target_name') or payload.get('agent_name') or '',
        provider=payload.get('provider'),
        provider_instance=payload.get('provider_instance'),
        cursor=int(payload['cursor']),
        generation=int(payload['generation']) if payload.get('generation') is not None else None,
        terminal=bool(payload['terminal']),
        status=payload.get('status'),
        reply=payload.get('reply') or '',
        events=tuple(payload.get('events', ())),
    )


def _connect_client(
    context,
    *,
    job_id: str,
    cursor: int,
    connect_mounted_daemon_fn: Callable,
    reconnect_error_classes: tuple[type[BaseException], ...],
    monotonic_fn: Callable[[], float],
    sleep_fn: Callable[[float], None],
    deadline: float | None,
    poll_interval: float,
    auto_start_enabled: bool = True,
):
    while True:
        if _deadline_exceeded(deadline, monotonic_fn=monotonic_fn):
            return None
        try:
            handle = connect_mounted_daemon_fn(context, allow_restart_stale=auto_start_enabled)
        except reconnect_error_classes:
            fallback = _persisted_terminal_batch(context, job_id, cursor=cursor)
            if fallback is not None:
                return None
            sleep_fn(poll_interval)
            continue
        assert handle.client is not None
        return handle.client


def _persisted_terminal_batch(context, job_id: str, *, cursor: int) -> WatchEventBatch | None:
    payload = load_persisted_terminal_watch_payload(context, job_id, cursor=cursor)
    if payload is None:
        return None
    return _watch_batch_from_payload(job_id, payload)


__all__ = ['watch_ask_job']
