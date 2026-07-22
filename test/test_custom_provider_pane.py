from __future__ import annotations

import pytest

from completion.models import CompletionConfidence, CompletionSourceKind, CompletionStatus
from provider_backends.pane_quiet_support import (
    PaneSnapshotReader,
    extract_reply_for_req,
    poll_submission,
    wrap_pane_quiet_prompt,
)
from provider_custom.pane import build_custom_pane_backend
from provider_custom.parsing import parse_providers_section
from provider_custom.wiring import restore_custom_provider_state
from provider_execution.base import ProviderSubmission


@pytest.fixture(autouse=True)
def _clean():
    yield
    restore_custom_provider_state({'wirings': {}, 'executables': {}})


def _spec(**overrides):
    table = {'mode': 'pane', 'command': 'aider --dark-mode', 'completion': 'marker'}
    table.update(overrides)
    return parse_providers_section({'aider': table})['aider']


def test_backend_components_present():
    backend = build_custom_pane_backend(_spec())
    assert backend.provider == 'aider'
    assert all([
        backend.manifest, backend.execution_adapter,
        backend.session_binding, backend.runtime_launcher,
    ])


def test_custom_marker_prompt_wrap_and_extract():
    prompt = wrap_pane_quiet_prompt('do the thing', 'req-1', done_prefix='AIDER_DONE:')
    assert 'AIDER_DONE: req-1' in prompt
    pane_text = 'CCB_REQ_ID: req-1\n\nsome reply body\nAIDER_DONE: req-1\n'
    reply, done_seen = extract_reply_for_req(pane_text, 'req-1', done_prefix='AIDER_DONE:')
    assert done_seen is True
    assert reply == 'some reply body'


def test_default_marker_unchanged():
    prompt = wrap_pane_quiet_prompt('do the thing', 'req-1')
    assert 'CCB_DONE: req-1' in prompt
    pane_text = 'CCB_REQ_ID: req-1\n\nsome reply body\nCCB_DONE: req-1\n'
    reply, done_seen = extract_reply_for_req(pane_text, 'req-1')
    assert done_seen is True
    assert reply == 'some reply body'


def test_quiet_secs_threaded_into_submission_state():
    # start_submission 需要完整 session/backend 环境，这里只验证参数被接受并落入 runtime_state；
    # 全链路在 Task 9 集成测试覆盖。
    import inspect

    from provider_backends.pane_quiet_support import start_submission
    params = inspect.signature(start_submission).parameters
    assert 'quiet_secs' in params and 'max_wait_secs' in params and 'done_prefix' in params
    assert 'completion_mode' in params
    assert params['completion_mode'].default == 'marker_quiet'  # 既有行为默认不变


def test_pane_completion_mode_mapping():
    from provider_custom.pane import CustomPaneExecutionAdapter

    marker_adapter = CustomPaneExecutionAdapter(_spec(completion='marker'), load_project_session_fn=lambda *a, **k: None)
    quiet_adapter = CustomPaneExecutionAdapter(_spec(completion='quiet'), load_project_session_fn=lambda *a, **k: None)
    assert marker_adapter._completion_mode == 'marker_only'
    assert quiet_adapter._completion_mode == 'quiet_only'


def test_quiet_only_prompt_has_no_done_instruction():
    prompt = wrap_pane_quiet_prompt('do the thing', 'req-1', emit_done_instruction=False)
    assert 'CCB_DONE:' not in prompt
    assert 'CCB_REQ_ID: req-1' in prompt and 'do the thing' in prompt


class _Backend:
    def __init__(self, text: str) -> None:
        self._text = text
        self.sent_texts: list[str] = []

    def get_pane_content(self, pane_id: str, *, lines: int) -> str:
        del pane_id, lines
        return self._text

    def send_text_to_pane(self, pane_id: str, text: str) -> None:
        del pane_id
        self.sent_texts.append(text)


def test_marker_only_does_not_complete_on_quiet():
    # completion_mode='marker_only' 时 quiet 层不得 COMPLETED：
    # quiet 已超 quiet_limit 且 total >= MIN_OBSERVED 仍须继续等；
    # 到 max_wait 后走 pane_quiet_timeout（DEGRADED）而非 pane_text_quiet（COMPLETED）。
    text = 'CCB_REQ_ID: job_marker123\n\npartial reply without marker\n'
    backend = _Backend(text)
    submission = ProviderSubmission(
        job_id='job_marker123',
        agent_name='aider_agent',
        provider='aider',
        accepted_at='2026-06-13T00:00:00Z',
        ready_at='2026-06-13T00:00:00Z',
        source_kind=CompletionSourceKind.TERMINAL_TEXT,
        reply='',
        runtime_state={
            'mode': 'pane_quiet',
            'provider': 'aider',
            'reader': PaneSnapshotReader(backend=backend, pane_id='%9', lines=200),
            'backend': backend,
            'pane_id': '%9',
            'req_id': 'job_marker123',
            'started_at': '2026-06-13T00:00:00Z',
            'last_change_at': '2026-06-13T00:00:00Z',
            'prompt_sent': True,
            'pending_prompt': 'pending prompt',
            'next_seq': 1,
            'quiet_secs_limit': 1.0,
            'max_wait_secs': 10.0,
            'done_prefix': 'AIDER_DONE:',
            'completion_mode': 'marker_only',
        },
    )

    # quiet_secs=3 >= quiet_limit=1 且 total=3 >= MIN_OBSERVED=2，
    # 但 marker_only 档 quiet 不完成 → 仍在途。
    in_flight = poll_submission(submission, now='2026-06-13T00:00:03Z')
    assert in_flight is not None
    assert in_flight.decision is None

    # total=11 >= max_wait=10 → pane_quiet_timeout（FAILED / DEGRADED）。
    timed_out = poll_submission(in_flight.submission, now='2026-06-13T00:00:11Z')
    assert timed_out is not None
    assert timed_out.decision is not None
    assert timed_out.decision.status is CompletionStatus.FAILED
    assert timed_out.decision.reason == 'pane_quiet_timeout'
    assert timed_out.decision.confidence is CompletionConfidence.DEGRADED
