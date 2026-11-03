from types import MethodType

import pytest

from ccbd.api_models import JobStatus, TargetKind
from provider_execution import draft_guard
from provider_execution.service import ExecutionService
from test_input_draft_guard import Target
from test_unified_message_fifo import (
    HoldingExecutionService, _build_dispatcher, _ask, _active_delivery_job,
    _turn_end_decision, _empty_turn_end_decision,
)


def _guarded_dispatcher(tmp_path, monkeypatch):
    now = [0.0]
    target = Target()
    cls = draft_guard.DraftGuard
    monkeypatch.setattr(draft_guard, 'DraftGuard', lambda: cls(clock=lambda: now[0]))
    monkeypatch.setattr(draft_guard, 'resolve_job_target', lambda job, context: target if job.agent_name=='codex' else None)
    execution = HoldingExecutionService()
    execution._draft_guards = {}
    execution.draft_preclaim = MethodType(ExecutionService.draft_preclaim, execution)
    execution.draft_allows_start = MethodType(ExecutionService.draft_allows_start, execution)
    execution.draft_wait_snapshot = MethodType(ExecutionService.draft_wait_snapshot, execution)
    ctx, dispatcher = _build_dispatcher(tmp_path/'fifo', execution=execution, clock=lambda:'2026-09-20T00:00:00Z')
    observe = target.observe
    def outside_lock():
        assert not dispatcher._chain_transition_lock._is_owned()
        return observe()
    target.observe = outside_lock
    return ctx, dispatcher, execution, target, now


def test_queue_explains_unknown_and_recovers_same_job_without_timeout_clear(tmp_path, monkeypatch):
    from cli.render_runtime.mailbox_views_runtime.queue import render_queue
    ctx, dispatcher, execution, target, now = _guarded_dispatcher(tmp_path, monkeypatch)
    target.state = 'unknown'
    first = dispatcher.submit(_ask('codex', 'claude', 'first', project_id=ctx.project_id, task_id='1')).jobs[0]
    second = dispatcher.submit(_ask('codex', 'claude', 'second', project_id=ctx.project_id, task_id='2')).jobs[0]
    dispatcher.tick()
    now[0] = 3600
    dispatcher.tick()
    payload = dispatcher.queue('codex', detail=True)
    assert payload['agent']['delivery_wait']['job_id'] == first.job_id
    assert payload['agent']['delivery_wait']['reason'] == 'unknown'
    assert payload['agent']['delivery_wait']['elapsed_seconds'] is None
    assert 'reason=unknown' in '\n'.join(render_queue(payload))
    assert not execution.started and target.clear_count == 0
    target.state = 'empty'
    dispatcher.tick()
    assert execution.started == [first.job_id]
    assert not execution.draft_wait_snapshot('codex', second.job_id)
    assert 'delivery_wait' not in dispatcher.queue('codex')['agent']


def test_terminal_provider_failure_fails_queued_head_without_dispatching(tmp_path, monkeypatch):
    ctx, dispatcher, execution, target, now = _guarded_dispatcher(tmp_path, monkeypatch)
    target.state = 'terminal_failure'
    target.reason = 'provider_reconnect_failed'
    job = dispatcher.submit(
        _ask('codex', 'claude', 'first', project_id=ctx.project_id, task_id='1')
    ).jobs[0]

    dispatcher.tick()

    terminal = dispatcher.get(job.job_id)
    decision = terminal.terminal_decision
    assert terminal.status is JobStatus.FAILED
    assert decision['reason'] == 'provider_reconnect_failed'
    assert decision['diagnostics']['automatic_retry'] is False
    assert job.job_id not in execution.started
    assert target.clear_count == 0
    assert 'delivery_wait' not in dispatcher.queue('codex')['agent']
    assert dispatcher._state.queued_items_for('agent', 'codex') == ()
    assert dispatcher._state.active_job_for('agent', 'codex') is None
    # The failed task request must not remain the mailbox head.
    head = dispatcher.mailbox_head('codex').get('head') or {}
    assert head.get('job_id') != job.job_id


def test_terminal_provider_failure_after_persisted_completion_still_leaves_the_queue(
    tmp_path, monkeypatch
):
    ctx, dispatcher, execution, target, now = _guarded_dispatcher(tmp_path, monkeypatch)
    target.state = 'terminal_failure'
    target.reason = 'provider_reconnect_failed'
    failed = dispatcher.submit(
        _ask('codex', 'claude', 'first', project_id=ctx.project_id, task_id='1')
    ).jobs[0]
    queued = dispatcher.submit(
        _ask('codex', 'claude', 'second', project_id=ctx.project_id, task_id='2')
    ).jobs[0]
    original_complete = dispatcher.complete

    def complete_then_fail(job_id, decision):
        original_complete(job_id, decision)
        raise RuntimeError('notification transport failed')

    monkeypatch.setattr(dispatcher, 'complete', complete_then_fail)

    dispatcher.tick()

    assert dispatcher.get(failed.job_id).status is JobStatus.FAILED
    assert dispatcher._state.queued_items_for('agent', 'codex') == (queued.job_id,)
    monkeypatch.setattr(dispatcher, 'complete', original_complete)
    target.state = 'empty'
    target.reason = None
    dispatcher.tick()
    assert execution.started[-1] == queued.job_id
    assert failed.job_id not in execution.started


def test_terminal_provider_failure_is_not_automatically_retried(tmp_path, monkeypatch):
    from dataclasses import replace

    from message_bureau import MessageStore
    from storage.paths import PathLayout

    ctx, dispatcher, execution, target, now = _guarded_dispatcher(tmp_path, monkeypatch)
    target.state = 'terminal_failure'
    target.reason = 'provider_reconnect_failed'
    job = dispatcher.submit(
        _ask('codex', 'claude', 'first', project_id=ctx.project_id, task_id='1')
    ).jobs[0]
    store = MessageStore(PathLayout(tmp_path / 'fifo'))
    message = store.list_all()[-1]
    store.append(
        replace(
            message,
            retry_policy={
                'mode': 'auto',
                'max_attempts': 3,
                'retryable_reasons': ['provider_reconnect_failed'],
            },
        )
    )

    dispatcher.tick()
    dispatcher.tick()

    assert dispatcher.get(job.job_id).status is JobStatus.FAILED
    assert job.job_id not in execution.started
    _line, events = dispatcher._event_store.read_since_target(TargetKind.AGENT, 'codex', 0)
    event_types = [record.type for record in events]
    assert 'job_retry_scheduled' not in event_types
    assert 'job_retry_exhausted' not in event_types
    assert event_types.count('job_accepted') == 1


def test_terminal_provider_failure_cleanup_survives_diagnostic_append_failure(
    tmp_path, monkeypatch
):
    from ccbd.services.dispatcher_runtime.lifecycle_start_runtime import queue as queue_runtime

    ctx, dispatcher, execution, target, now = _guarded_dispatcher(tmp_path, monkeypatch)
    target.state = 'terminal_failure'
    target.reason = 'provider_reconnect_failed'
    failed = dispatcher.submit(
        _ask('codex', 'claude', 'first', project_id=ctx.project_id, task_id='1')
    ).jobs[0]
    queued = dispatcher.submit(
        _ask('codex', 'claude', 'second', project_id=ctx.project_id, task_id='2')
    ).jobs[0]
    original_complete = dispatcher.complete

    def complete_then_fail(job_id, decision):
        original_complete(job_id, decision)
        raise RuntimeError('notification transport failed')

    def failing_append(*args, **kwargs):
        raise OSError('event store unavailable')

    original_append = queue_runtime.append_event
    monkeypatch.setattr(dispatcher, 'complete', complete_then_fail)
    monkeypatch.setattr(queue_runtime, 'append_event', failing_append)

    dispatcher.tick()

    assert dispatcher.get(failed.job_id).status is JobStatus.FAILED
    assert dispatcher._state.queued_items_for('agent', 'codex') == (queued.job_id,)
    monkeypatch.setattr(dispatcher, 'complete', original_complete)
    monkeypatch.setattr(queue_runtime, 'append_event', original_append)
    target.state = 'empty'
    target.reason = None
    dispatcher.tick()
    dispatcher.tick()
    assert queued.job_id in execution.started
    assert failed.job_id not in execution.started


def test_generic_provider_failure_state_keeps_the_job_queued(tmp_path, monkeypatch):
    ctx, dispatcher, execution, target, now = _guarded_dispatcher(tmp_path, monkeypatch)
    target.state = 'failed'
    target.reason = 'provider_api_error'
    job = dispatcher.submit(
        _ask('codex', 'claude', 'first', project_id=ctx.project_id, task_id='1')
    ).jobs[0]

    dispatcher.tick()

    assert dispatcher.get(job.job_id).status in {JobStatus.ACCEPTED, JobStatus.QUEUED}
    assert dispatcher.queue('codex')['agent']['delivery_wait']['reason'] == 'provider_api_error'
    assert job.job_id not in execution.started
    assert target.clear_count == 0
    target.state = 'empty'
    target.reason = None
    dispatcher.tick()
    assert execution.started == [job.job_id]


def test_terminal_provider_failure_keeps_reply_delivery_queued(tmp_path, monkeypatch):
    ctx, dispatcher, execution, target, now = _guarded_dispatcher(tmp_path, monkeypatch)
    target.state = 'empty'
    source = dispatcher.submit(
        _ask('claude', 'codex', 'result producer', project_id=ctx.project_id, task_id='source')
    ).jobs[0]
    dispatcher.tick()
    dispatcher.complete(source.job_id, _turn_end_decision(reply='BACK'))
    target.state = 'unknown'
    dispatcher.tick()
    queued = dispatcher._state.queued_items_for('agent', 'codex')
    assert queued, 'the reply delivery should be admitted to the codex slot'
    delivery_id = queued[0]

    target.state = 'terminal_failure'
    target.reason = 'provider_reconnect_failed'
    dispatcher.tick()

    # A reply is durable and must stay redeliverable after the provider is
    # repaired; it is never failed into a requeue loop by a dead pane.
    delivery = dispatcher.get(delivery_id)
    assert delivery.status in {JobStatus.ACCEPTED, JobStatus.QUEUED}
    assert delivery.terminal_decision is None
    assert dispatcher._state.queued_items_for('agent', 'codex') == (delivery_id,)
    assert dispatcher.queue('codex')['agent']['delivery_wait']['reason'] == 'provider_reconnect_failed'
    assert delivery_id not in execution.started


def test_binding_failure_is_visible_without_prior_successful_inspection(tmp_path, monkeypatch):
    ctx, dispatcher, execution, target, now = _guarded_dispatcher(tmp_path, monkeypatch)
    def missing(*args):
        raise ValueError('missing managed binding')
    monkeypatch.setattr(draft_guard, 'resolve_job_target', missing)
    job = dispatcher.submit(_ask('codex', 'claude', 'first', project_id=ctx.project_id, task_id='1')).jobs[0]
    dispatcher.tick()
    assert dispatcher.queue('codex')['agent']['delivery_wait']['reason'] == 'binding_unavailable'
    dispatcher.cancel(job.job_id)
    assert 'delivery_wait' not in dispatcher.queue('codex')['agent']


@pytest.mark.parametrize('reply_first', [False, True])
def test_guard_holds_fifo_head_before_running_and_keeps_ask_back_order(tmp_path, monkeypatch, reply_first):
    ctx, dispatcher, execution, target, now = _guarded_dispatcher(tmp_path, monkeypatch)
    source = dispatcher.submit(_ask('claude', 'codex', 'result producer', project_id=ctx.project_id, task_id='source')).jobs[0]
    dispatcher.tick()
    if reply_first:
        dispatcher.complete(source.job_id, _turn_end_decision(reply='BACK'))
        dispatcher.tick()
    request = dispatcher.submit(_ask('codex', 'gemini', 'ASK', project_id=ctx.project_id, task_id='ask')).jobs[0]
    if not reply_first:
        dispatcher.complete(source.job_id, _turn_end_decision(reply='BACK'))
    dispatcher.tick()
    assert execution.started == [source.job_id]
    assert dispatcher.get(request.job_id).status in {JobStatus.ACCEPTED, JobStatus.QUEUED}
    assert _active_delivery_job(dispatcher, 'codex') is None
    now[0] = 179.999
    dispatcher.tick()
    assert target.clear_count == 0
    now[0] = 180
    dispatcher.tick()
    first = _active_delivery_job(dispatcher, 'codex')
    assert first is not None
    assert (first.request.message_type == 'reply_delivery') == reply_first
    assert target.clear_count == 1
    for _ in range(3):
        dispatcher.tick()
    assert execution.started == [source.job_id, first.job_id]
    execution.arm_turn_end(first.job_id, _empty_turn_end_decision() if reply_first else _turn_end_decision())
    dispatcher.poll_completions()
    dispatcher.tick()
    second = _active_delivery_job(dispatcher, 'codex')
    assert second.job_id != first.job_id
    assert (second.request.message_type == 'reply_delivery') != reply_first


def test_cancel_waiting_head_does_not_clear_and_next_head_gets_new_timer(tmp_path, monkeypatch):
    ctx, dispatcher, execution, target, now = _guarded_dispatcher(tmp_path, monkeypatch)
    first = dispatcher.submit(_ask('codex', 'claude', 'first', project_id=ctx.project_id, task_id='1')).jobs[0]
    second = dispatcher.submit(_ask('codex', 'claude', 'second', project_id=ctx.project_id, task_id='2')).jobs[0]
    dispatcher.tick()
    now[0] = 179
    dispatcher.cancel(first.job_id)
    dispatcher.tick()
    now[0] = 180
    dispatcher.tick()
    assert not execution.started and target.clear_count == 0
    assert dispatcher.get(second.job_id).status is JobStatus.QUEUED
    now[0] = 359
    dispatcher.tick()
    assert execution.started[0] == second.job_id
    assert target.clear_count == 1
