from __future__ import annotations

from dataclasses import replace

from agents.models import normalize_agent_name

from .models import AttemptRecord, AttemptState, MessageState, ReplyTerminalStatus


_TERMINAL_ATTEMPT_STATES = frozenset(
    {
        AttemptState.COMPLETED,
        AttemptState.INCOMPLETE,
        AttemptState.FAILED,
        AttemptState.CANCELLED,
        AttemptState.SUPERSEDED,
        AttemptState.DEAD_LETTER,
    }
)


def resolve_origin_message_id(service, reply_to: str | None) -> str | None:
    key = str(reply_to or '').strip()
    if not key:
        return None
    attempt = service._attempt_store.get_latest(key)
    if attempt is not None:
        return attempt.message_id
    attempt = service._attempt_store.get_latest_by_job_id(key)
    if attempt is not None:
        return attempt.message_id
    message = service._message_store.get_latest(key)
    if message is not None:
        return message.message_id
    return None


def refresh_message_state(service, message_id: str, *, updated_at: str) -> None:
    message = service._message_store.get_latest(message_id)
    if message is None:
        return
    attempts = latest_attempts_for_message(service, message_id)
    if not attempts:
        return
    active = _active_attempts(attempts)
    replies = service._reply_store.list_message(message_id)
    next_state = _next_message_state(active=active, attempts=attempts, replies=replies)
    set_message_state(service, message_id, next_state, updated_at=updated_at)


def set_message_state(service, message_id: str, next_state: MessageState, *, updated_at: str) -> None:
    current = service._message_store.get_latest(message_id)
    if current is None or current.message_state is next_state:
        return
    service._message_store.append(replace(current, updated_at=updated_at, message_state=next_state))


def latest_attempts_for_message(service, message_id: str) -> list[AttemptRecord]:
    latest: dict[str, AttemptRecord] = {}
    for record in service._attempt_store.list_message(message_id):
        latest[record.attempt_id] = record
    return list(latest.values())


def _terminal_replies(replies):
    terminal = [reply for reply in replies if not bool(reply.diagnostics.get('notice'))]
    if terminal:
        return terminal
    return list(replies)


def next_retry_index(service, message_id: str, agent_name: str) -> int:
    normalized = normalize_agent_name(agent_name)
    latest = -1
    for record in service._attempt_store.list_message(message_id):
        if record.agent_name != normalized:
            continue
        latest = max(latest, int(record.retry_index))
    return latest + 1


def rebuild_mailbox_summary(service, agent_name: str, *, updated_at: str) -> None:
    service._mailbox_kernel.rebuild_mailbox_summary(agent_name, updated_at=updated_at)


def _active_attempts(attempts: list[AttemptRecord]) -> list[AttemptRecord]:
    return [
        attempt
        for attempt in attempts
        if attempt.attempt_state not in _TERMINAL_ATTEMPT_STATES
    ]


def _next_message_state(*, active: list[AttemptRecord], attempts: list[AttemptRecord], replies) -> MessageState:
    if active:
        return MessageState.PARTIALLY_REPLIED if replies else MessageState.RUNNING

    reply_statuses = {reply.terminal_status for reply in _terminal_replies(replies)}
    if reply_statuses:
        return _reply_terminal_state(reply_statuses)
    return _attempt_terminal_state({attempt.attempt_state for attempt in attempts})


def _reply_terminal_state(statuses: set[ReplyTerminalStatus]) -> MessageState:
    """Map a set of reply terminal statuses to the canonical message state.

    When all replies share the same status the mapping is straightforward.
    For mixed statuses (e.g. broadcast where some agents completed and others
    were cancelled) the priority is: FAILED > INCOMPLETE > CANCELLED >
    COMPLETED.  A message that has any COMPLETED reply mixed with only
    CANCELLED replies is still COMPLETED overall.
    """
    if not statuses:
        return MessageState.INCOMPLETE
    # Homogeneous: fast-path for the common case
    if len(statuses) == 1:
        (single,) = statuses
        return _SINGLE_REPLY_STATE.get(single, MessageState.INCOMPLETE)
    # Heterogeneous: priority-based resolution
    if ReplyTerminalStatus.FAILED in statuses:
        return MessageState.FAILED
    if ReplyTerminalStatus.INCOMPLETE in statuses:
        return MessageState.INCOMPLETE
    # Mixed COMPLETED + CANCELLED → completed
    return MessageState.COMPLETED


_SINGLE_REPLY_STATE: dict[ReplyTerminalStatus, MessageState] = {
    ReplyTerminalStatus.COMPLETED: MessageState.COMPLETED,
    ReplyTerminalStatus.CANCELLED: MessageState.CANCELLED,
    ReplyTerminalStatus.FAILED: MessageState.FAILED,
    ReplyTerminalStatus.INCOMPLETE: MessageState.INCOMPLETE,
}


def _attempt_terminal_state(statuses: set[AttemptState]) -> MessageState:
    """Map a set of attempt terminal states to the canonical message state.

    Uses the same priority as _reply_terminal_state for heterogeneous sets.
    """
    if not statuses:
        return MessageState.INCOMPLETE
    if len(statuses) == 1:
        (single,) = statuses
        return _SINGLE_ATTEMPT_STATE.get(single, MessageState.INCOMPLETE)
    # Heterogeneous: priority-based resolution
    if AttemptState.FAILED in statuses:
        return MessageState.FAILED
    if AttemptState.INCOMPLETE in statuses:
        return MessageState.INCOMPLETE
    # Mixed COMPLETED + CANCELLED → completed
    return MessageState.COMPLETED


_SINGLE_ATTEMPT_STATE: dict[AttemptState, MessageState] = {
    AttemptState.COMPLETED: MessageState.COMPLETED,
    AttemptState.CANCELLED: MessageState.CANCELLED,
    AttemptState.FAILED: MessageState.FAILED,
    AttemptState.INCOMPLETE: MessageState.INCOMPLETE,
}


__all__ = [
    'latest_attempts_for_message',
    'next_retry_index',
    'rebuild_mailbox_summary',
    'refresh_message_state',
    'resolve_origin_message_id',
    'set_message_state',
]
