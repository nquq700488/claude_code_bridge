from types import SimpleNamespace

from ccbd.services.dispatcher_runtime.lifecycle_start_runtime.start import (
    _submission_delivery_payload,
)
from message_bureau.control_queue_runtime.common import delivery_stage_for_inbound_status


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
