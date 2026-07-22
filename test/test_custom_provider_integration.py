from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path

import pytest

from ccbd.api_models import DeliveryScope, JobRecord, JobStatus, MessageEnvelope
from completion.models import CompletionConfidence, CompletionSourceKind, CompletionStatus
from provider_backends.pane_quiet_support import PaneSnapshotReader
from provider_core.registry import build_default_backend_registry
from provider_custom.factory import build_custom_backends
from provider_custom.pane import CustomPaneExecutionAdapter
from provider_custom.parsing import parse_providers_section
from provider_custom.wiring import restore_custom_provider_state
from provider_execution.base import ProviderSubmission


@pytest.fixture(autouse=True)
def _clean():
    yield
    restore_custom_provider_state({'wirings': {}, 'executables': {}})


# ── helpers ──────────────────────────────────────────────────────────


def _spec(**overrides):
    """Convenience: parse a single provider and return the CustomProviderSpec."""
    table = {'mode': 'pane', 'command': 'aider --dark-mode'}
    table.update(overrides)
    return parse_providers_section({'test': table})['test']


def _write_stub_cli(tmp_path, name: str, body: str):
    stub = tmp_path / 'bin' / name
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text(body, encoding='utf-8')
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return stub


def _write_session(work_dir: Path, provider: str, runtime_dir: Path, instance: str | None = None) -> None:
    session_filename = f'.{provider}-session'
    if instance:
        # session_filename_for_instance 命名规则：.test-session → .test-{instance}-session
        session_filename = f'.{provider}-{instance}-session'
    session = work_dir / session_filename
    session.write_text(json.dumps({
        'runtime_dir': str(runtime_dir),
        'completion_artifact_dir': str(runtime_dir / 'completion'),
        'ccb_session_id': 'sess-1',
        f'{provider}_session_id': 'sess-1',
    }), encoding='utf-8')


def _make_job(
    job_id: str = 'job-px-1',
    agent_name: str = 'helper',
    provider: str = 'test',
    body: str = 'say hello',
    workspace_path: str | None = None,
) -> JobRecord:
    return JobRecord(
        job_id=job_id,
        submission_id=None,
        agent_name=agent_name,
        provider=provider,
        request=MessageEnvelope(
            project_id='test-project',
            to_agent=agent_name,
            from_actor='user',
            body=body,
            task_id=None,
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        ),
        status=JobStatus.QUEUED,
        terminal_decision=None,
        cancel_requested_at=None,
        created_at='2026-07-22T00:00:00Z',
        updated_at='2026-07-22T00:00:00Z',
        workspace_path=workspace_path,
    )


def _poll_until_terminal(adapter, submission, timeout_s=10):
    """Poll the adapter until a terminal decision is returned."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        result = adapter.poll(submission, now='2026-07-22T00:00:01Z')
        if result is not None and result.decision is not None:
            return result
        time.sleep(0.1)
    pytest.fail(f'adapter did not reach terminal state within {timeout_s}s')


# ── oneshot integration ──────────────────────────────────────────────


class TestOneshotIntegration:
    """全链路：配置 → 解析 → registry → adapter.start/poll → 完成。"""

    def test_oneshot_marker_full_chain(self, tmp_path, monkeypatch):
        """completion=marker：stub 打印答案+marker → COMPLETED，reply 含答案不含 marker。"""
        _write_stub_cli(tmp_path, 'px-cli', (
            '#!/bin/sh\n'
            'echo "answer to: $4"\n'
            'echo "CCB_DONE: done"\n'
        ))
        monkeypatch.setenv('PATH', f"{tmp_path / 'bin'}:{os.environ.get('PATH', '')}")

        spec = _spec(mode='oneshot', command='px-cli run --format text',
                     prompt_mode='arg', completion='marker', timeout_secs=30)
        provider_name = spec.name  # 'test'

        backends, errors = build_custom_backends({provider_name: spec})
        assert errors == {}
        registry = build_default_backend_registry(extra_backends=backends)
        backend = registry.get(provider_name)
        assert backend is not None

        work_dir = tmp_path / 'work'
        runtime_dir = tmp_path / 'runtime'
        (runtime_dir / 'completion').mkdir(parents=True)
        work_dir.mkdir()
        _write_session(work_dir, provider_name, runtime_dir, instance=provider_name)

        job = _make_job(provider=provider_name, agent_name=provider_name, workspace_path=str(work_dir))
        submission = backend.execution_adapter.start(job, context=None, now='2026-07-22T00:00:00Z')
        assert submission.status is CompletionStatus.INCOMPLETE

        result = _poll_until_terminal(backend.execution_adapter, submission)
        assert result.decision.status is CompletionStatus.COMPLETED
        assert 'answer to:' in result.decision.reply
        assert 'CCB_DONE:' not in result.decision.reply

    def test_oneshot_exit_full_chain(self, tmp_path, monkeypatch):
        """completion=exit：进程退出即完成，reply=stdout 全文。"""
        _write_stub_cli(tmp_path, 'px-cli', (
            '#!/bin/sh\n'
            'echo "hello from px"\n'
            'echo "second line"\n'
        ))
        monkeypatch.setenv('PATH', f"{tmp_path / 'bin'}:{os.environ.get('PATH', '')}")

        spec = _spec(mode='oneshot', command='px-cli run',
                     prompt_mode='arg', completion='exit', timeout_secs=30)
        provider_name = spec.name

        backends, errors = build_custom_backends({provider_name: spec})
        assert errors == {}
        registry = build_default_backend_registry(extra_backends=backends)
        backend = registry.get(provider_name)
        assert backend is not None

        work_dir = tmp_path / 'work'
        runtime_dir = tmp_path / 'runtime'
        (runtime_dir / 'completion').mkdir(parents=True)
        work_dir.mkdir()
        _write_session(work_dir, provider_name, runtime_dir, instance=provider_name)

        job = _make_job(provider=provider_name, agent_name=provider_name, workspace_path=str(work_dir))
        submission = backend.execution_adapter.start(job, context=None, now='2026-07-22T00:00:00Z')

        result = _poll_until_terminal(backend.execution_adapter, submission)
        assert result.decision.status is CompletionStatus.COMPLETED
        assert 'hello from px' in result.decision.reply

    def test_oneshot_marker_early_termination(self, tmp_path, monkeypatch):
        """marker 提前完成：stub 打印 marker 后 sleep 100 → poll 到 COMPLETED 时进程已终止。"""
        _write_stub_cli(tmp_path, 'px-cli', (
            '#!/bin/sh\n'
            'echo "partial answer"\n'
            'echo "CCB_DONE: done"\n'
            'sleep 100\n'
        ))
        monkeypatch.setenv('PATH', f"{tmp_path / 'bin'}:{os.environ.get('PATH', '')}")

        spec = _spec(mode='oneshot', command='px-cli run',
                     prompt_mode='arg', completion='marker', timeout_secs=5)
        provider_name = spec.name

        backends, errors = build_custom_backends({provider_name: spec})
        assert errors == {}
        registry = build_default_backend_registry(extra_backends=backends)
        backend = registry.get(provider_name)
        assert backend is not None

        work_dir = tmp_path / 'work'
        runtime_dir = tmp_path / 'runtime'
        (runtime_dir / 'completion').mkdir(parents=True)
        work_dir.mkdir()
        _write_session(work_dir, provider_name, runtime_dir, instance=provider_name)

        job = _make_job(provider=provider_name, agent_name=provider_name, workspace_path=str(work_dir))
        submission = backend.execution_adapter.start(job, context=None, now='2026-07-22T00:00:00Z')

        # marker 应触发提前完成 —— 进程被 kill
        result = _poll_until_terminal(backend.execution_adapter, submission)
        assert result.decision.status is CompletionStatus.COMPLETED
        assert 'partial answer' in result.decision.reply
        assert 'CCB_DONE:' not in result.decision.reply


# ── pane integration ─────────────────────────────────────────────────


class _FakePaneBackend:
    """模拟 tmux pane：可编程 pane 内容 + 记录发送文本。"""

    def __init__(self, text: str = '') -> None:
        self._text = text
        self.sent_texts: list[str] = []

    def get_pane_content(self, pane_id: str, *, lines: int) -> str:
        del pane_id, lines
        return self._text

    def send_text_to_pane(self, pane_id: str, text: str) -> None:
        del pane_id
        self.sent_texts.append(text)


def _pane_submission(
    provider: str,
    job: JobRecord,
    backend: _FakePaneBackend,
    *,
    pane_id: str = '%9',
    req_id: str | None = None,
    now: str = '2026-07-22T00:00:00Z',
    completion_mode: str = 'marker_quiet',
    done_prefix: str = 'CCB_DONE:',
    quiet_secs_limit: float = 4.0,
    max_wait_secs: float = 10.0,
) -> ProviderSubmission:
    """Construct a ProviderSubmission with fake backend state for pane testing."""
    req_id_val = req_id or f'ccb_req_{job.job_id}'
    return ProviderSubmission(
        job_id=job.job_id,
        agent_name=job.agent_name,
        provider=provider,
        accepted_at=now,
        ready_at=now,
        source_kind=CompletionSourceKind.TERMINAL_TEXT,
        reply='',
        runtime_state={
            'mode': 'pane_quiet',
            'provider': provider,
            'reader': PaneSnapshotReader(backend=backend, pane_id=pane_id, lines=200),
            'backend': backend,
            'pane_id': pane_id,
            'req_id': req_id_val,
            'started_at': now,
            'last_change_at': now,
            'last_poll_at': now,
            'quiet_secs_limit': quiet_secs_limit,
            'max_wait_secs': max_wait_secs,
            'done_prefix': done_prefix,
            'completion_mode': completion_mode,
            'prompt_sent': True,
            'pending_prompt': f'CCB_REQ_ID: {req_id_val}\n\ndo the thing\n',
            'prompt_deferred_until_ready': False,
            'last_hash': None,
            'next_seq': 1,
        },
    )


class TestPaneIntegration:
    """pane completion 双档经 CustomPaneExecutionAdapter 的端到端验证。"""

    def test_pane_quiet_completion(self):
        """completion=quiet → prompt 不含 done 指令，quiet 层完成（修复：quiet_only 锚点后全文本提取）。"""
        spec = _spec(mode='pane', command='aider --dark-mode', completion='quiet')
        adapter = CustomPaneExecutionAdapter(spec, load_project_session_fn=lambda *a, **k: None)
        assert adapter._completion_mode == 'quiet_only'

        backend = _FakePaneBackend()
        job = _make_job(job_id='job-q1')

        sub = _pane_submission(
            'test', job, backend, req_id='job-q1',
            completion_mode='quiet_only', done_prefix='CCB_DONE:',
        )

        # 第一轮 poll：pane 有新内容（有回复文本，无 marker），记录 hash
        backend._text = 'CCB_REQ_ID: job-q1\n\nhello from quiet mode\n'
        r1 = adapter.poll(sub, now='2026-07-22T00:00:01Z')
        assert r1.decision is None  # 在途：hash 刚变，quiet_secs=0

        # 第二轮 poll：使用上一轮的 submission（含更新后的 state），
        # 内容不变，quiet_secs=4 >= quiet_limit=4，total=5 >= MIN_OBSERVED=2
        r2 = adapter.poll(r1.submission, now='2026-07-22T00:00:05Z')
        assert r2.decision is not None
        assert r2.decision.status is CompletionStatus.COMPLETED
        assert r2.decision.reason == 'pane_text_quiet'
        assert 'hello from quiet mode' in r2.decision.reply

    def test_pane_marker_completion(self):
        """completion=marker → marker 出现 → COMPLETED。"""
        spec = _spec(mode='pane', command='aider --dark-mode', completion='marker', marker='AIDER_DONE:')
        adapter = CustomPaneExecutionAdapter(spec, load_project_session_fn=lambda *a, **k: None)
        assert adapter._completion_mode == 'marker_only'

        backend = _FakePaneBackend()
        job = _make_job(job_id='job-m1')

        sub = _pane_submission(
            'test', job, backend, req_id='job-m1',
            completion_mode='marker_only', done_prefix='AIDER_DONE:',
        )

        # marker 出现 → COMPLETED
        backend._text = 'CCB_REQ_ID: job-m1\n\nanswer from aider\nAIDER_DONE: job-m1\n'
        result = adapter.poll(sub, now='2026-07-22T00:00:01Z')
        assert result.decision is not None
        assert result.decision.status is CompletionStatus.COMPLETED
        assert result.decision.reason == 'pane_done_marker'
        assert 'answer from aider' in result.decision.reply

    def test_pane_marker_only_no_complete_on_quiet(self):
        """completion=marker 时 quiet 到期不完成 → 等到 max_wait → DEGRADED。"""
        spec = _spec(mode='pane', command='aider --dark-mode', completion='marker', marker='AIDER_DONE:')
        adapter = CustomPaneExecutionAdapter(spec, load_project_session_fn=lambda *a, **k: None)
        assert adapter._completion_mode == 'marker_only'

        backend = _FakePaneBackend()
        job = _make_job(job_id='job-m2')

        sub = _pane_submission(
            'test', job, backend, req_id='job-m2',
            completion_mode='marker_only', done_prefix='AIDER_DONE:',
            quiet_secs_limit=1.0, max_wait_secs=10.0,
        )

        # 第一轮 poll：有新内容（无 marker），记录 hash
        backend._text = 'CCB_REQ_ID: job-m2\n\npartial reply without marker\n'
        r1 = adapter.poll(sub, now='2026-07-22T00:00:01Z')
        assert r1.decision is None  # 在途

        # t=3s: quiet_secs=2 >= quiet_limit=1，但 marker_only 档 quiet 不完成
        r2 = adapter.poll(r1.submission, now='2026-07-22T00:00:03Z')
        assert r2.decision is None  # 仍不完成

        # t=12s: total >= max_wait=10 → pane_quiet_timeout DEGRADED
        r3 = adapter.poll(r2.submission, now='2026-07-22T00:00:12Z')
        assert r3.decision is not None
        assert r3.decision.status is CompletionStatus.FAILED
        assert r3.decision.reason == 'pane_quiet_timeout'
        assert r3.decision.confidence is CompletionConfidence.DEGRADED


# ── factory error isolation ──────────────────────────────────────────


def test_factory_isolates_single_provider_failure():
    """单个 provider 组装失败不拖垮其余。"""
    from provider_custom.spec import CustomProviderSpec

    bad_spec = CustomProviderSpec(
        name='bad',
        mode='oneshot',
        command='',
    )
    good_spec = _spec(mode='pane', command='aider', completion='quiet')

    backends, errors = build_custom_backends({'bad': bad_spec, good_spec.name: good_spec})
    assert 'bad' in errors
    assert any(b.provider == good_spec.name for b in backends)
    assert len(backends) == 1  # 只有 good 成功
