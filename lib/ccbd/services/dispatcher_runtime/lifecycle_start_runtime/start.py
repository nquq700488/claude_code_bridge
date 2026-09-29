from __future__ import annotations

from dataclasses import replace

from agents.models import AgentState
from completion.models import CompletionConfidence, CompletionDecision, CompletionStatus
from provider_core.registry import TEST_DOUBLE_PROVIDER_NAMES

from ccbd.api_models import JobRecord, JobStatus, TargetKind

from ..context import build_job_runtime_context
from ..records import append_event, append_job
from ..reply_delivery import is_reply_delivery_job
from ..reply_delivery_runtime.start_completion import (
    complete_reply_delivery_after_start,
)
from ..runtime_state import sync_runtime
from .models import QueuedTargetSlot

def write_running_snapshot(dispatcher, running: JobRecord, *, started_at: str) -> None:
    if dispatcher._completion_tracker is not None:
        tracked = dispatcher._completion_tracker.start(running, started_at=started_at)
        dispatcher._snapshot_writer.write_completion(
            job_id=running.job_id,
            agent_name=running.agent_name,
            profile_family=dispatcher._profile_family_for_job(running),
            state=tracked.state,
            decision=tracked.decision,
            updated_at=started_at,
        )
        return
    dispatcher._snapshot_writer.write_pending(
        job_id=running.job_id,
        agent_name=running.agent_name,
        profile_family=dispatcher._profile_family_for_job(running),
    )


def start_running_job(
    dispatcher,
    current: JobRecord,
    *,
    slot: QueuedTargetSlot,
    started_at: str | None = None,
) -> JobRecord:
    started_at = started_at or dispatcher._clock()
    running = replace(current, status=JobStatus.RUNNING, updated_at=started_at)
    if dispatcher._message_bureau is not None:
        dispatcher._message_bureau.mark_attempt_started(running, started_at=started_at)
    append_job(dispatcher, running)
    append_event(
        dispatcher,
        running,
        'job_started',
        {
            'status': JobStatus.RUNNING.value,
            'delivery_stage': 'claim_started',
            'delivery_mechanism': 'dispatcher',
        },
        timestamp=started_at,
    )
    write_running_snapshot(dispatcher, running, started_at=started_at)
    runtime_context = build_job_runtime_context(running, slot.runtime)
    dispatcher._state.mark_active_for(running.target_kind, running.target_name, running.job_id)
    if slot.requires_runtime_sync:
        sync_runtime(dispatcher, running.agent_name, state=AgentState.BUSY)
    submission = None
    should_start = dispatcher._execution_service is not None and should_start_execution(
        dispatcher,
        running,
        runtime_context,
    )
    if should_start:
        append_event(
            dispatcher,
            running,
            'provider_start_attempt',
            {
                'delivery_stage': 'provider_start_attempt',
                'provider': running.provider,
            },
            timestamp=dispatcher._clock(),
        )
        try:
            submission = dispatcher._execution_service.start(
                running,
                runtime_context=runtime_context,
            )
        except Exception as exc:
            return fail_provider_start(dispatcher, running, exc, failed_at=dispatcher._clock())
        if submission is None:
            append_event(
                dispatcher,
                running,
                'provider_submission_missing',
                {
                    'delivery_stage': 'provider_submission_missing',
                    'provider': running.provider,
                    'delivery_reason': 'execution_service_returned_none',
                },
                timestamp=dispatcher._clock(),
            )
        else:
            append_event(
                dispatcher,
                running,
                'provider_submission_created',
                _submission_delivery_payload(submission),
                timestamp=dispatcher._clock(),
            )
    else:
        append_event(
            dispatcher,
            running,
            'provider_start_skipped',
            {
                'delivery_stage': 'provider_start_skipped',
                'provider': running.provider,
                'delivery_reason': (
                    'execution_service_missing'
                    if dispatcher._execution_service is None
                    else 'runtime_binding_not_actionable'
                ),
            },
            timestamp=dispatcher._clock(),
        )
    if is_reply_delivery_job(running) and dispatcher._execution_service is not None:
        return complete_reply_delivery_after_start(
            dispatcher,
            running,
            started_at=started_at,
            submission=submission,
        )
    return running


def _submission_delivery_payload(submission) -> dict[str, object]:
    state = dict(getattr(submission, 'runtime_state', {}) or {})
    diagnostics = dict(getattr(submission, 'diagnostics', {}) or {})
    fallback_stage = (
        'provider_runtime_not_ready'
        if diagnostics.get('reason') == 'runtime_unavailable'
        else 'provider_submission_created'
    )
    stage = str(
        state.get('delivery_stage')
        or diagnostics.get('delivery_stage')
        or fallback_stage
    )
    payload: dict[str, object] = {
        'delivery_stage': stage,
        'provider': str(getattr(submission, 'provider', '') or ''),
        'delivery_state': state.get('delivery_state'),
        'delivery_mechanism': state.get('delivery_mechanism') or diagnostics.get('mechanism'),
        'target_pane_id': state.get('delivery_target_pane_id') or state.get('pane_id'),
        'prompt_sent': state.get('prompt_sent'),
    }
    reason = diagnostics.get('reason') or state.get('delivery_reason')
    error = diagnostics.get('error') or state.get('delivery_error')
    if reason:
        payload['delivery_reason'] = reason
    if error:
        payload['delivery_error'] = error
    return {key: value for key, value in payload.items() if value is not None and value != ''}


def fail_provider_start(dispatcher, running: JobRecord, exc: Exception, *, failed_at: str) -> JobRecord:
    diagnostics = {
        'delivery_stage': 'provider_start_failed',
        'delivery_reason': 'provider_start_exception',
        'error_type': type(exc).__name__,
        'provider': running.provider,
        'provider_start_error': str(exc),
    }

    append_event(
        dispatcher,
        running,
        'provider_start_failed',
        diagnostics,
        timestamp=failed_at,
    )
    decision = CompletionDecision(
        terminal=True,
        status=CompletionStatus.FAILED,
        reason='provider_start_failed',
        confidence=CompletionConfidence.EXACT,
        reply='',
        anchor_seen=False,
        reply_started=False,
        reply_stable=False,
        provider_turn_ref=None,
        source_cursor=None,
        finished_at=failed_at,
        diagnostics=diagnostics,
    )
    return dispatcher.complete(running.job_id, decision)


def should_start_execution(dispatcher, current: JobRecord, runtime_context) -> bool:
    if runtime_context is None:
        return False
    if not bool(getattr(dispatcher, '_require_actionable_runtime_binding_for_execution', False)):
        return True
    if str(current.provider or '').strip().lower() in TEST_DOUBLE_PROVIDER_NAMES:
        return True
    if current.target_kind is not TargetKind.AGENT:
        return True

    runtime_ref = str(runtime_context.runtime_ref or '').strip()
    backend_type = str(runtime_context.backend_type or '').strip().lower()
    if backend_type in {'headless', 'pty-backed'}:
        return True
    return ':' in runtime_ref


__all__ = ['fail_provider_start', 'should_start_execution', 'start_running_job', 'write_running_snapshot']
