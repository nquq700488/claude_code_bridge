from __future__ import annotations

from completion.models import CompletionDecision
from message_bureau import ReplyTerminalStatus

from ..records import get_job
from ..reply_delivery import prepare_reply_deliveries, resolve_reply_delivery_terminal
from ..frontdesk_handoff import enforce_frontdesk_boundary
from .message_bureau import record_message_bureau_completion
from .persistence import finish_terminal_runtime, persist_terminal_completion


def complete_job(dispatcher, job_id: str, decision: CompletionDecision):
    if not decision.terminal:
        raise dispatcher._dispatch_error('complete requires a terminal completion decision')
    with dispatcher._chain_transition_lock:
        current = get_job(dispatcher, job_id)
        if current is None:
            raise dispatcher._dispatch_error(f'unknown job: {job_id}')
        if current.status in dispatcher._terminal_event_by_status:
            return current

        finished_at = decision.finished_at or dispatcher._clock()
        decision = enforce_frontdesk_boundary(dispatcher, current, decision, finished_at=finished_at)
        terminal, decision, prior_snapshot = persist_terminal_completion(
            dispatcher,
            current,
            decision,
            finished_at=finished_at,
        )
        terminal, _reply_decision, retry_scheduled = record_message_bureau_completion(
            dispatcher,
            current,
            terminal,
            decision,
            finished_at=finished_at,
            prior_snapshot=prior_snapshot,
        )
    finish_terminal_runtime(dispatcher, current)
    resolve_reply_delivery_terminal(dispatcher, terminal, finished_at=finished_at)
    if retry_scheduled:
        return terminal
    _notify_webhook(dispatcher, terminal)
    _maybe_notify_sender(dispatcher, terminal)
    if bool(getattr(dispatcher, '_auto_reply_delivery_on_complete', False)):
        prepare_reply_deliveries(dispatcher)
    return terminal


def _maybe_notify_sender(dispatcher, job):
    if dispatcher._message_bureau is None:
        return
    route_options = dict(getattr(job.request, 'route_options', None) or {})
    if not bool(route_options.get('notify_sender')):
        return
    sender = str(job.request.from_actor or '').strip()
    if not sender:
        return
    status = str(job.status.value or '') if hasattr(job.status, 'value') else str(job.status)
    notice_body = (
        f'CCB job {job.job_id} for agent `{job.agent_name}` has finished with status: {status}.\n'
        f'Use `ccb trace {job.job_id}` to view the full result.'
    )
    dispatcher._message_bureau.record_notice(
        job,
        reply=notice_body,
        diagnostics={
            'notice': True,
            'notify_sender': True,
            'job_id': job.job_id,
            'agent_name': job.agent_name,
            'status': status,
        },
        finished_at=getattr(job, 'updated_at', '') or '',
        terminal_status=ReplyTerminalStatus.COMPLETED if status == 'completed' else ReplyTerminalStatus.FAILED,
        deliver_to_actor=sender,
    )


def _notify_webhook(dispatcher, job):
    webhook = getattr(dispatcher, '_webhook', None)
    if webhook is None:
        return
    status = str(job.status.value or '') if hasattr(job.status, 'value') else str(job.status)
    event_map = {
        'completed': 'job.completed',
        'failed': 'job.failed',
        'cancelled': 'job.cancelled',
    }
    event_type = event_map.get(status)
    if event_type is None:
        return
    webhook.send(
        event_type,
        {
            'job_id': job.job_id,
            'agent_name': job.agent_name,
            'status': status,
            'message': getattr(job, 'message', None),
            'finished_at': getattr(job, 'finished_at', None),
        },
    )


__all__ = ['complete_job']
