from __future__ import annotations

from ccbd.api_models import JobStatus, TargetKind
from completion.models import CompletionConfidence, CompletionDecision, CompletionStatus
from mailbox_kernel import InboundEventType

from ..records import append_event, get_job
from ..context import build_job_runtime_context
from ..reply_delivery import claim_reply_delivery_start, claimable_reply_delivery_job_ids
from .models import QueuedTargetSlot
from .recovery import refresh_slot_runtime_for_start
from .start import start_running_job

_PENDING_STATUSES = frozenset({JobStatus.ACCEPTED, JobStatus.QUEUED})
_TERMINAL_PROVIDER_FAILURE_REPLY = (
    'CCB could not start this job: the Codex session reported that automatic '
    'reconnect could not restore it. Copy any text still visible in the pane, '
    'then relaunch or repair Codex and retry the job.'
)


def start_next_queued_job(dispatcher, slot: QueuedTargetSlot):
    slot = refresh_slot_runtime_for_start(dispatcher, slot)
    if slot is None:
        return None
    if dispatcher._message_bureau is not None and slot.target_kind is TargetKind.AGENT:
        return _start_agent_mailbox_job(dispatcher, slot)
    queued = dispatcher._state.queued_items_for(slot.target_kind, slot.target_name)
    job_id = next(iter(queued), None)
    if job_id is None:
        return None
    current = get_job(dispatcher, job_id)
    if current is None:
        return None
    if not _preclaim_gate(dispatcher, current, slot):
        return None
    dispatcher._state.remove_queued_for(slot.target_kind, slot.target_name, job_id)
    return start_running_job(dispatcher, current, slot=slot)


def _start_agent_mailbox_job(dispatcher, slot: QueuedTargetSlot):
    queued_ids = set(dispatcher._state.queued_items_for(slot.target_kind, slot.target_name))
    head = _mailbox_head_event(dispatcher, slot.target_name)
    if head is None:
        return None
    if head.event_type is InboundEventType.TASK_REPLY:
        return _claim_reply_delivery(dispatcher, slot, queued_ids)
    if head.event_type is InboundEventType.TASK_REQUEST:
        return _claim_request_job(dispatcher, slot, queued_ids)
    return None


def _mailbox_head_event(dispatcher, agent_name: str):
    control = getattr(dispatcher, '_message_bureau_control', None)
    kernel = getattr(control, '_mailbox_kernel', None)
    if kernel is None:
        return None
    return kernel.head_pending_event(agent_name)


def _claim_reply_delivery(dispatcher, slot: QueuedTargetSlot, queued_ids: set[str]):
    for candidate in claimable_reply_delivery_job_ids(dispatcher, slot.target_name):
        if candidate not in queued_ids:
            continue
        current = get_job(dispatcher, candidate)
        if current is None:
            dispatcher._state.remove_queued_for(slot.target_kind, slot.target_name, candidate)
            continue
        started_at = dispatcher._clock()
        # A reply delivery is durably queued and must stay redeliverable once
        # the provider is repaired; failing it here would either requeue it in a
        # tight loop or consume a reply that was never delivered.
        if not _preclaim_gate(dispatcher, current, slot, terminalizable=False):
            return None
        if not claim_reply_delivery_start(dispatcher, current, started_at=started_at):
            continue
        dispatcher._state.remove_queued_for(slot.target_kind, slot.target_name, candidate)
        return start_running_job(dispatcher, current, slot=slot, started_at=started_at)
    return None


def _claim_request_job(dispatcher, slot: QueuedTargetSlot, queued_ids: set[str]):
    for candidate in dispatcher._message_bureau.claimable_request_job_ids(slot.target_name):
        if candidate not in queued_ids:
            continue
        current = get_job(dispatcher, candidate)
        if current is None:
            dispatcher._state.remove_queued_for(slot.target_kind, slot.target_name, candidate)
            continue
        if not _preclaim_gate(dispatcher, current, slot):
            return None
        dispatcher._state.remove_queued_for(slot.target_kind, slot.target_name, candidate)
        return start_running_job(dispatcher, current, slot=slot)
    return None


def _preclaim_outcome(dispatcher, job, slot):
    """Passive pre-claim verdict; never clears, types, or starts the provider."""
    from provider_execution.draft_guard import PRECLAIM_ALLOWED, PRECLAIM_BLOCKED, PreclaimOutcome
    check = getattr(dispatcher._execution_service, 'draft_preclaim', None)
    legacy = getattr(dispatcher._execution_service, 'draft_allows_start', None)
    if not callable(check) and not callable(legacy):
        return PreclaimOutcome(PRECLAIM_ALLOWED, '')
    runtime_context = build_job_runtime_context(job, slot.runtime)
    if callable(check):
        return check(job, runtime_context=runtime_context)
    if not legacy(job, runtime_context=runtime_context):
        return PreclaimOutcome(PRECLAIM_BLOCKED, 'draft_blocked')
    return PreclaimOutcome(PRECLAIM_ALLOWED, '')


def _still_claimable(dispatcher, job, slot) -> bool:
    # Terminal inspection runs outside the dispatcher lock. Recheck cancellation
    # and ownership after I/O, before taking the queue head.
    current = get_job(dispatcher, job.job_id)
    return (current is not None and current.status == job.status
            and job.job_id in dispatcher._state.queued_items_for(slot.target_kind, slot.target_name)
            and dispatcher._state.active_job_for(slot.target_kind, slot.target_name) is None)


def _preclaim_gate(dispatcher, job, slot, *, terminalizable: bool = True) -> bool:
    """Return True when the job may start; fail the queue head on explicit
    provider death when the caller's path can safely terminalize it."""
    outcome = _preclaim_outcome(dispatcher, job, slot)
    if outcome.allows_start:
        return _still_claimable(dispatcher, job, slot)
    if terminalizable and outcome.is_terminal_failure:
        _fail_unstartable_job(dispatcher, job, slot, reason=outcome.reason)
    return False


def _owns_mailbox_head(dispatcher, job) -> bool:
    """A mailbox task request may only be failed while it still owns the head.

    Terminalizing a superseded or already-claimed entry would consume an
    unrelated inbound event.
    """
    if dispatcher._message_bureau is None or job.target_kind is not TargetKind.AGENT:
        return True
    try:
        claimable = dispatcher._message_bureau.claimable_request_job_ids(job.target_name)
    except Exception:
        return False
    return job.job_id in claimable


def _fail_unstartable_job(dispatcher, job, slot, *, reason: str):
    """Terminalize a queued head the provider cannot accept, under the lock.

    The queued entry is removed only after the terminal status is durable, so a
    crash between the two leaves the job recoverable rather than orphaned.
    """
    finished_at = dispatcher._clock()
    with dispatcher._chain_transition_lock:
        current = get_job(dispatcher, job.job_id)
        if current is None or current.status not in _PENDING_STATUSES:
            return None
        if current.cancel_requested_at:
            return None
        if job.job_id not in dispatcher._state.queued_items_for(slot.target_kind, slot.target_name):
            return None
        if dispatcher._state.active_job_for(slot.target_kind, slot.target_name) is not None:
            return None
        if not _owns_mailbox_head(dispatcher, current):
            return None
        decision = CompletionDecision(
            terminal=True,
            status=CompletionStatus.FAILED,
            reason=reason,
            confidence=CompletionConfidence.EXACT,
            reply=_TERMINAL_PROVIDER_FAILURE_REPLY,
            anchor_seen=False,
            reply_started=False,
            reply_stable=False,
            provider_turn_ref=None,
            source_cursor=None,
            finished_at=finished_at,
            diagnostics={
                'delivery_stage': 'preclaim_provider_unavailable',
                'delivery_reason': reason,
                'provider': current.provider,
                'pane_failure_reason': reason,
                'automatic_retry': False,
            },
        )
        try:
            terminal = dispatcher.complete(current.job_id, decision)
        except Exception as exc:
            # Diagnostics are best effort: queue cleanup below must never depend
            # on being able to record this event.
            try:
                append_event(
                    dispatcher,
                    current,
                    'preclaim_provider_failure_deferred',
                    {
                        'delivery_stage': 'preclaim_provider_unavailable',
                        'delivery_reason': reason,
                        'error_type': type(exc).__name__,
                        'error': str(exc),
                    },
                    timestamp=finished_at,
                )
            except Exception:
                pass
            # Completion can persist the terminal status and only then raise
            # from notification work. A persisted terminal job must never stay
            # at the queue head, where it would block every later job.
            terminal = get_job(dispatcher, current.job_id)
        if terminal is None or terminal.status not in dispatcher._terminal_event_by_status:
            return None
        dispatcher._state.remove_queued_for(slot.target_kind, slot.target_name, job.job_id)
        return terminal


__all__ = ['start_next_queued_job']
