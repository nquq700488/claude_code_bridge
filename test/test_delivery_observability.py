from types import SimpleNamespace

import message_bureau.control_queue_runtime.common as queue_common
from ccbd.services.dispatcher_runtime.facade import _recorded_delivery_phase
from ccbd.services.dispatcher_runtime.lifecycle_start_runtime.start import (
    _submission_delivery_payload,
)
from message_bureau.control_queue_runtime.common import (
    delivery_stage_for_inbound,
    delivery_stage_for_inbound_status,
    recorded_delivery_stage,
)


def test_submission_delivery_payload_exposes_safe_stage_and_target() -> None:
    submission = SimpleNamespace(
        provider='codex',
        diagnostics={},
        runtime_state={
            'delivery_stage': 'pane_send_succeeded',
            'delivery_mechanism': 'tmux_backend',
            'delivery_state': 'pending_anchor',
            'delivery_target_pane_id': '%2',
            'prompt_sent': True,
        },
    )

    payload = _submission_delivery_payload(submission)

    assert payload == {
        'delivery_stage': 'pane_send_succeeded',
        'provider': 'codex',
        'delivery_state': 'pending_anchor',
        'delivery_mechanism': 'tmux_backend',
        'target_pane_id': '%2',
        'prompt_sent': True,
    }


def test_submission_delivery_payload_marks_runtime_not_ready() -> None:
    submission = SimpleNamespace(
        provider='codex',
        diagnostics={'reason': 'runtime_unavailable', 'error': 'codex_runtime_not_ready'},
        runtime_state={'mode': 'error'},
    )

    payload = _submission_delivery_payload(submission)

    assert payload['delivery_stage'] == 'provider_runtime_not_ready'
    assert payload['delivery_reason'] == 'runtime_unavailable'
    assert payload['delivery_error'] == 'codex_runtime_not_ready'


def test_inbound_queue_stage_distinguishes_unclaimed_and_claimed() -> None:
    assert delivery_stage_for_inbound_status('queued') == (
        'queued_waiting_for_dispatch',
        'dispatcher_claim_pending',
    )
    assert delivery_stage_for_inbound_status('delivering') == (
        'claim_started',
        'provider_start_pending',
    )


def _delivery_event(
    job_id: str,
    stage: str,
    reason: str | None = None,
    event_type: str = 'provider_submission_created',
) -> SimpleNamespace:
    payload: dict[str, object] = {'delivery_stage': stage}
    if reason is not None:
        payload['delivery_reason'] = reason
    return SimpleNamespace(job_id=job_id, type=event_type, payload=payload)


def test_recorded_delivery_stage_keeps_latest_event_for_the_job() -> None:
    events = (
        _delivery_event('job_a', 'claim_started'),
        _delivery_event('job_other', 'provider_submission_created'),
        _delivery_event('job_a', 'provider_submission_created'),
        _delivery_event('job_a', 'awaiting_input_guard'),
    )

    assert recorded_delivery_stage(events, 'job_a') == ('awaiting_input_guard', '')


def test_claimed_inbound_reports_recorded_delivery_progress(monkeypatch) -> None:
    class _Store:
        def __init__(self, _layout) -> None:
            pass

        def read_since_target(self, _kind, _name, _cursor):
            return 0, (_delivery_event('job_a', 'awaiting_input_guard'),)

    monkeypatch.setattr(queue_common, 'JobEventStore', _Store)
    record = SimpleNamespace(status='delivering', agent_name='codex')

    assert delivery_stage_for_inbound(SimpleNamespace(_layout=object()), record, 'job_a') == (
        'awaiting_input_guard',
        '',
    )


def test_claimed_inbound_falls_back_to_pending_without_delivery_events(monkeypatch) -> None:
    class _Store:
        def __init__(self, _layout) -> None:
            pass

        def read_since_target(self, _kind, _name, _cursor):
            return 0, ()

    monkeypatch.setattr(queue_common, 'JobEventStore', _Store)
    record = SimpleNamespace(status='delivering', agent_name='codex')

    assert delivery_stage_for_inbound(SimpleNamespace(_layout=object()), record, 'job_a') == (
        'claim_started',
        'provider_start_pending',
    )


def test_recorded_delivery_phase_marks_created_submission_as_executing() -> None:
    dispatcher = SimpleNamespace(
        _event_store=SimpleNamespace(
            read_since_target=lambda *_args: (0, (_delivery_event('job_a', 'provider_submission_created'),))
        )
    )
    job = SimpleNamespace(target_kind='agent', target_name='codex', job_id='job_a')

    assert _recorded_delivery_phase(dispatcher, job) == {
        'execution_phase': 'executing',
        'execution_phase_reason': 'provider_submission_recorded',
    }


def test_recorded_delivery_phase_accepts_created_submission_at_any_stage() -> None:
    dispatcher = SimpleNamespace(
        _event_store=SimpleNamespace(
            read_since_target=lambda *_args: (0, (_delivery_event('job_a', 'awaiting_input_guard'),))
        )
    )
    job = SimpleNamespace(target_kind='agent', target_name='codex', job_id='job_a')

    assert _recorded_delivery_phase(dispatcher, job) == {
        'execution_phase': 'executing',
        'execution_phase_reason': 'provider_submission_recorded',
    }


def test_recorded_delivery_phase_ignores_unknown_stage_outside_a_created_submission() -> None:
    dispatcher = SimpleNamespace(
        _event_store=SimpleNamespace(
            read_since_target=lambda *_args: (
                0,
                (_delivery_event('job_a', 'some_future_stage', event_type='provider_start_attempt'),),
            )
        )
    )
    job = SimpleNamespace(target_kind='agent', target_name='codex', job_id='job_a')

    assert _recorded_delivery_phase(dispatcher, job) is None


def test_recorded_delivery_phase_ignores_failed_or_unstarted_delivery() -> None:
    job = SimpleNamespace(target_kind='agent', target_name='codex', job_id='job_a')
    for stage in (
        'provider_start_failed',
        'provider_runtime_not_ready',
        'claim_started',
        'pane_send_failed',
        'preclaim_provider_unavailable',
        'provider_start_attempt',
    ):
        dispatcher = SimpleNamespace(
            _event_store=SimpleNamespace(
                read_since_target=lambda *_args, _stage=stage: (0, (_delivery_event('job_a', _stage),))
            )
        )
        assert _recorded_delivery_phase(dispatcher, job) is None
