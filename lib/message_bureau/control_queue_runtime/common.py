from __future__ import annotations

from ccbd.api_models import TargetKind
from jobs.store import JobEventStore
from mailbox_kernel import MailboxState
from mailbox_runtime.targets import normalize_mailbox_target


def derive_mailbox_state(has_active: bool, queue_depth: int) -> str:
    if has_active:
        return MailboxState.DELIVERING.value
    if queue_depth > 0:
        return MailboxState.BLOCKED.value
    return MailboxState.IDLE.value


def delivery_stage_for_inbound_status(status: object) -> tuple[str, str]:
    token = str(getattr(status, 'value', status) or '').strip().lower()
    if token == 'queued':
        return 'queued_waiting_for_dispatch', 'dispatcher_claim_pending'
    if token == 'delivering':
        return 'claim_started', 'provider_start_pending'
    if token == 'consumed':
        return 'delivery_complete', 'inbound_consumed'
    if token in {'abandoned', 'superseded'}:
        return 'delivery_terminal', token
    return 'delivery_unknown', token or 'unknown'


def delivery_stage_for_inbound(
    service,
    record,
    job_id: str | None = None,
    *,
    events=None,
) -> tuple[str, str]:
    """Report recorded delivery progress for a claimed event.

    A claimed inbound stays ``delivering`` until the reply lands, so the status
    alone cannot tell a pending start from an active provider turn.
    """
    stage, reason = delivery_stage_for_inbound_status(record.status)
    if stage != 'claim_started' or not job_id:
        return stage, reason
    if events is None:
        events = delivery_events_for(service, getattr(record, 'agent_name', ''))
    recorded = recorded_delivery_stage(events, job_id)
    return recorded or (stage, reason)


def recorded_delivery_stage(events, job_id: str) -> tuple[str, str] | None:
    latest: tuple[str, str] | None = None
    for event in events or ():
        if str(getattr(event, 'job_id', '') or '') != job_id:
            continue
        payload = dict(getattr(event, 'payload', None) or {})
        stage = str(payload.get('delivery_stage') or '').strip()
        if stage:
            latest = (stage, str(payload.get('delivery_reason') or '').strip())
    return latest


_NOT_STARTED_DELIVERY_STAGES = frozenset(
    {
        'claim_started',
        'preclaim_provider_unavailable',
        'provider_runtime_not_ready',
        'provider_start_attempt',
        'provider_start_failed',
        'provider_start_skipped',
        'provider_submission_missing',
        'pane_send_failed',
    }
)


def recorded_delivery_is_executing(events, job_id: str) -> bool:
    """True only when the stream records an accepted provider submission.

    Keyword gates the answer instead of a stage blacklist: an unfamiliar stage
    on anything but a created submission must not be read as "started".
    """
    executing = False
    for event in events or ():
        if str(getattr(event, 'job_id', '') or '') != job_id:
            continue
        payload = dict(getattr(event, 'payload', None) or {})
        stage = str(payload.get('delivery_stage') or '').strip()
        if not stage:
            continue
        if stage in _NOT_STARTED_DELIVERY_STAGES:
            executing = False
        elif str(getattr(event, 'type', '') or '') == 'provider_submission_created':
            executing = True
    return executing


def delivery_events_for(service, agent_name: str):
    layout = getattr(service, '_layout', None)
    agent = str(agent_name or '').strip()
    if not agent or layout is None:
        return ()
    try:
        _cursor, events = JobEventStore(layout).read_since_target(TargetKind.AGENT, agent, 0)
    except Exception:
        return ()
    return tuple(events)


def require_mailbox_target(service, agent_name: str) -> str:
    normalized = normalize_mailbox_target(agent_name, known_targets=service._known_mailboxes)
    if normalized is None:
        raise ValueError(f'unknown mailbox target: {str(agent_name or "").strip().lower()}')
    return normalized


def summary_targets(service) -> tuple[str, ...]:
    return tuple(sorted(set(getattr(service._config, 'agents', {}).keys())))


def mailbox_has_activity(service, agent_name: str, *, mailbox=None) -> bool:
    record = mailbox if mailbox is not None else service._mailbox_store.load(agent_name)
    if record is None:
        return False
    if getattr(record, 'active_inbound_event_id', None):
        return True
    if int(getattr(record, 'queue_depth', 0) or 0) > 0:
        return True
    return int(getattr(record, 'pending_reply_count', 0) or 0) > 0


def preview_text(value: str, *, limit: int = 120) -> str:
    text = str(value or '').replace('\r', '').replace('\n', '\\n').strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + '...'


__all__ = [
    'delivery_events_for',
    'delivery_stage_for_inbound',
    'delivery_stage_for_inbound_status',
    'derive_mailbox_state',
    'mailbox_has_activity',
    'preview_text',
    'recorded_delivery_is_executing',
    'recorded_delivery_stage',
    'require_mailbox_target',
    'summary_targets',
]
