from __future__ import annotations

from completion.models import CompletionItemKind
from provider_execution.active import prepare_active_poll
from provider_execution.base import ProviderPollResult, ProviderSubmission
from provider_execution.common import build_item

from .accelerator import poll_with_accelerator
from .event_reading import read_entries
from .readiness import looks_codex_interrupted
from .start import state_session_path
from .state_machine import (
    apply_session_rotation,
    build_poll_state,
    entry_matches_bound_turn,
    finalize_poll_result,
    handle_assistant_entry,
    handle_terminal_entry,
    handle_user_entry,
    update_binding_refs,
)


def poll_submission(submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
    prepared = prepare_active_poll(submission, now=now)
    if prepared is None or isinstance(prepared, ProviderPollResult):
        return prepared

    accelerated = poll_with_accelerator(submission, now=now)
    if accelerated is not None:
        return accelerated.result

    state = submission.runtime_state.get("state") or {}
    poll = build_poll_state(submission)
    state = poll_entry_batches(submission, poll, prepared.reader, state, now=now)

    # If the session JSONL produced no terminal event, scan the tmux pane
    # for a Codex content-safety interruption.  This interruption is NOT
    # reflected in the JSONL — it only shows as pane text — so without this
    # check CCB would wait for the reliability timeout (900 s) before
    # giving up.
    # The runtime_state flag prevents re-emitting TURN_ABORTED every poll
    # cycle while the interruption text remains in the pane buffer.
    if not poll.reached_terminal and poll.anchor_seen and not submission.runtime_state.get('codex_interruption_detected'):
        _check_codex_pane_interruption(submission, poll, backend=prepared.backend, pane_id=prepared.pane_id, now=now)

    return finalize_poll_result(submission, poll, state=state, now=now)


def _check_codex_pane_interruption(
    submission: ProviderSubmission,
    poll,
    *,
    backend: object,
    pane_id: str,
    now: str,
) -> None:
    get_pane_content = getattr(backend, 'get_pane_content', None)
    if not callable(get_pane_content) or not pane_id:
        return
    try:
        text = str(get_pane_content(pane_id, lines=80) or '')
    except Exception:
        return
    if not looks_codex_interrupted(text):
        return

    # The session was interrupted by Codex's internal safety guard.
    # Emit a TURN_ABORTED item so CCB can immediately retry instead of
    # waiting for the no-terminal timeout.
    poll.items.append(
        build_item(
            submission,
            kind=CompletionItemKind.TURN_ABORTED,
            timestamp=now,
            seq=poll.next_seq,
            payload={
                'reason': 'conversation_interrupted',
                'status': 'cancelled',
                'error_message': 'Codex content-safety guard interrupted the conversation.',
                'last_agent_message': poll.reply_buffer or poll.last_assistant_message or '',
            },
        )
    )
    poll.next_seq += 1
    poll.reached_terminal = True
    # Prevent re-detection on subsequent poll cycles while the
    # interruption text stays in the pane buffer.
    submission.runtime_state['codex_interruption_detected'] = True


def poll_entry_batches(submission, poll, reader, state, *, now: str):
    current_state = state
    while True:
        entries, current_state = read_entries(reader, current_state)
        apply_session_state(submission, poll, current_state, now=now)
        if not entries:
            break
        process_entry_batch(submission, poll, entries, now=now)
        if poll.reached_terminal:
            break
    return current_state


def apply_session_state(submission, poll, state, *, now: str) -> None:
    apply_session_rotation(
        submission,
        poll,
        new_session_path=state_session_path(state),
        now=now,
    )


def process_entry_batch(submission, poll, entries, *, now: str) -> None:
    for entry in entries:
        process_entry(submission, poll, entry, now=now)
        if poll.reached_terminal:
            break


def process_entry(submission, poll, entry, *, now: str) -> None:
    update_binding_refs(poll, entry)
    if not entry_matches_bound_turn(poll, entry):
        return
    role = str(entry.get("role") or "").strip().lower()
    if role == "user":
        handle_user_entry(submission, poll, text=str(entry.get("text") or ""), now=now)
        return
    if not poll.anchor_seen:
        return
    if role == "assistant":
        handle_assistant_entry(submission, poll, entry, now=now)
        return
    handle_terminal_entry(submission, poll, entry, now=now)


__all__ = ["poll_submission"]
