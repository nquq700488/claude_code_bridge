from __future__ import annotations

import json
from pathlib import Path
import sys
import time

import pytest

from ccbd.api_models import DeliveryScope, JobRecord, JobStatus, MessageEnvelope
from completion.models import CompletionSourceKind, CompletionStatus
from provider_custom.env import provider_level_env
from provider_custom.oneshot import _make_marker_observer, build_custom_oneshot_backend
from provider_custom.parsing import parse_providers_section
from provider_custom.wiring import restore_custom_provider_state
from provider_execution.base import ProviderRuntimeContext, ProviderSubmission


@pytest.fixture(autouse=True)
def _clean():
    yield
    restore_custom_provider_state({'wirings': {}, 'executables': {}})


def _spec(**overrides):
    table = {'mode': 'oneshot', 'command': 'px run --format text', 'prompt_mode': 'arg', 'completion': 'exit'}
    table.update(overrides)
    return parse_providers_section({'px': table})['px']


def _job(work_dir: Path, *, agent_name: str = 'px1') -> JobRecord:
    return JobRecord(
        job_id='job_px_run123',
        submission_id='sub_px',
        agent_name=agent_name,
        provider='px',
        request=MessageEnvelope(
            project_id='proj',
            to_agent=agent_name,
            from_actor='main',
            body='Reply exactly from px',
            task_id=None,
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        ),
        status=JobStatus.RUNNING,
        terminal_decision=None,
        cancel_requested_at=None,
        created_at='2026-06-13T00:00:00Z',
        updated_at='2026-06-13T00:00:00Z',
        workspace_path=str(work_dir),
    )


def _runtime_context(work_dir: Path, *, agent_name: str = 'px1') -> ProviderRuntimeContext:
    return ProviderRuntimeContext(
        agent_name=agent_name,
        workspace_path=str(work_dir),
        backend_type='pane-backed',
        runtime_ref='%1',
        session_ref=str(work_dir / '.ccb' / f'.px-{agent_name}-session'),
    )


def _write_session(work_dir: Path, *, agent_name: str = 'px1') -> None:
    runtime_dir = work_dir / '.ccb' / 'agents' / agent_name / 'provider-runtime' / 'px'
    session = {
        'active': True,
        'agent_name': agent_name,
        'runtime_dir': str(runtime_dir),
        'completion_artifact_dir': str(runtime_dir / 'completion'),
        'work_dir': str(work_dir),
        'pane_id': '%1',
    }
    session_path = work_dir / '.ccb' / f'.px-{agent_name}-session'
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(json.dumps(session, ensure_ascii=True), encoding='utf-8')


def _run_to_terminal(adapter, submission: ProviderSubmission):
    current = submission
    for index in range(150):
        result = adapter.poll(current, now=f'2026-06-13T00:00:{index % 60:02d}Z')
        if result is not None:
            current = result.submission
            if result.decision is not None:
                return result
        time.sleep(0.02)
    raise AssertionError('provider adapter did not terminalize')


def test_backend_components_present():
    backend = build_custom_oneshot_backend(_spec())
    assert backend.provider == 'px'
    assert backend.manifest is not None
    assert backend.execution_adapter is not None
    assert backend.session_binding is not None
    assert backend.runtime_launcher is not None


def test_provider_level_env_resolution(monkeypatch):
    monkeypatch.setenv('PX_KEY', 'sk-from-env')
    spec = _spec(key='$PX_KEY', key_env='PX_API_KEY', url='https://u', url_env='PX_URL',
                 model='m1', model_env='PX_MODEL', env={'PX_FLAG': '1'})
    env = provider_level_env(spec)
    assert env == {'PX_API_KEY': 'sk-from-env', 'PX_URL': 'https://u', 'PX_MODEL': 'm1', 'PX_FLAG': '1'}


def test_marker_observer(tmp_path):
    observe = _make_marker_observer('CCB_DONE:')
    out = tmp_path / 'run.out'
    out.write_text('line one\nline two\nCCB_DONE: job_1\n', encoding='utf-8')
    obs = observe(out)
    assert obs.finished is True
    assert obs.finish_reason == 'done'
    assert obs.text == 'line one\nline two'
    out.write_text('partial reply\n', encoding='utf-8')
    obs = observe(out)
    assert obs.finished is False
    assert obs.text == 'partial reply'


def test_prompt_via_stdin_config():
    spec = _spec(prompt_mode='stdin')
    backend = build_custom_oneshot_backend(spec)
    assert backend.execution_adapter.config.prompt_via_stdin is True


def test_provider_level_model_flag_assembled_into_command():
    spec = _spec(model='gpt-5', model_flag='--model')
    backend = build_custom_oneshot_backend(spec)

    class _Req:
        prompt = 'hello'
        job = None  # 无 agent 覆盖时 job 为 None，回退 provider 默认值

    cmd = backend.execution_adapter.config.command_builder(_Req())
    assert cmd[:2] == ['px', 'run']
    assert '--model' in cmd and 'gpt-5' in cmd
    assert cmd[-1] == 'hello'  # prompt 仍居末位（arg 模式）


def test_agent_model_override_via_provider_options():
    """agent 级 model_flag 覆盖：provider_options 中 model+model_flag 替代 provider 默认。"""
    spec = _spec(model='gpt-5', model_flag='--model')
    backend = build_custom_oneshot_backend(spec)

    class _Job:
        provider_options = {'model': 'gpt-4', 'model_flag': '--model'}

    class _Req:
        prompt = 'hello'
        job = _Job()

    cmd = backend.execution_adapter.config.command_builder(_Req())
    assert cmd[:2] == ['px', 'run']
    assert '--model' in cmd and 'gpt-4' in cmd
    assert 'gpt-5' not in cmd  # provider 默认被 agent 覆盖
    assert cmd[-1] == 'hello'


def test_agent_model_env_override_via_provider_options():
    """agent 级 model_env 覆盖：provider_options 中 model_env+model 注入环境变量。"""
    spec = _spec(model='gpt-5', model_env='PX_MODEL')
    backend = build_custom_oneshot_backend(spec)

    class _Job:
        provider_options = {'model': 'gpt-4o', 'model_env': 'PX_MODEL'}

    class _Req:
        prompt = 'hello'
        job = _Job()
        session_data = {}

    env = backend.execution_adapter.config.env_builder(_Req())
    assert env['PX_MODEL'] == 'gpt-4o'


def test_marker_finish_terminates_running_process(monkeypatch, tmp_path):
    # oneshot marker 档的提前完成语义：observer 报 finished 时，
    # NativeCliSubprocessAdapter._terminal 会 terminate 仍在运行的子进程
    # （execution.py 的 observation.finished 分支 → _terminate_process）。
    stub = tmp_path / 'marker_stub.py'
    stub.write_text(
        'import time\n'
        'print("stub reply body", flush=True)\n'
        'print("CCB_DONE: job_px_run123", flush=True)\n'
        'time.sleep(100)\n',
        encoding='utf-8',
    )
    spec = _spec(command=f'{sys.executable} {stub}', completion='marker')
    backend = build_custom_oneshot_backend(spec)
    adapter = backend.execution_adapter

    terminate_calls: list[dict[str, object]] = []
    from provider_backends.native_cli_support import execution as native_execution

    original_terminate = native_execution._terminate_process

    def _recording_terminate(state, *, grace):
        terminate_calls.append({'provider': state.get('provider'), 'job_id': state.get('job_id'), 'grace': grace})
        return original_terminate(state, grace=grace)

    monkeypatch.setattr(native_execution, '_terminate_process', _recording_terminate)

    work_dir = tmp_path / 'repo'
    work_dir.mkdir()
    _write_session(work_dir)

    submission = adapter.start(_job(work_dir), context=_runtime_context(work_dir), now='2026-06-13T00:00:00Z')
    assert submission.source_kind is CompletionSourceKind.STRUCTURED_RESULT_STREAM

    terminal = _run_to_terminal(adapter, submission)

    assert terminal.decision is not None
    assert terminal.decision.status is CompletionStatus.COMPLETED
    assert 'stub reply body' in terminal.decision.reply
    assert terminate_calls, 'marker finish must terminate the still-running child process'
    assert terminate_calls[0]['job_id'] == 'job_px_run123'
    assert terminate_calls[0]['provider'] == 'px'


def test_stdin_prompt_reaches_process_via_file_redirect(tmp_path):
    # prompt_via_stdin=True 时 prompt 落临时文件并以文件句柄作 stdin（不写管道），
    # stub 从 stdin 读到的内容应包含 job body。
    stub = tmp_path / 'stdin_stub.py'
    stub.write_text(
        'import sys\n'
        'data = sys.stdin.read()\n'
        'print("GOT_STDIN_BEGIN")\n'
        'print(data)\n'
        'print("GOT_STDIN_END")\n',
        encoding='utf-8',
    )
    spec = _spec(command=f'{sys.executable} {stub}', prompt_mode='stdin', completion='exit')
    backend = build_custom_oneshot_backend(spec)
    adapter = backend.execution_adapter

    work_dir = tmp_path / 'repo'
    work_dir.mkdir()
    _write_session(work_dir)

    submission = adapter.start(_job(work_dir), context=_runtime_context(work_dir), now='2026-06-13T00:00:00Z')
    assert submission.source_kind is CompletionSourceKind.STRUCTURED_RESULT_STREAM

    terminal = _run_to_terminal(adapter, submission)

    assert terminal.decision is not None
    assert terminal.decision.status is CompletionStatus.COMPLETED
    assert 'GOT_STDIN_BEGIN' in terminal.decision.reply
    assert 'Reply exactly from px' in terminal.decision.reply
