from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ccbd.api_models import JobRecord
from provider_core.protocol import request_anchor_for_job
from provider_execution.base import ProviderPollResult, ProviderRuntimeContext, ProviderSubmission
from terminal_runtime import get_backend_for_session

from .comm import OpenCodeLogReader
from .execution_runtime import poll_submission as _poll_submission_impl
from .execution_runtime import start_submission as _start_submission_impl
from .execution_runtime.helpers import load_session as _load_session_impl
from .execution_runtime.helpers import state_session_path as _state_session_path_impl
from .protocol import wrap_opencode_prompt
from .session import load_project_session


class OpenCodeProviderAdapter:
    provider = "opencode"

    def restore_diagnostics(self) -> dict[str, object]:
        return {
            "resume_supported": False,
            "restore_mode": "resubmit_required",
            "restore_reason": "provider_resume_unsupported",
            "restore_detail": "opencode live polling works, but restart-time execution resume is not implemented yet",
        }

    def start(self, job: JobRecord, *, context: ProviderRuntimeContext | None, now: str) -> ProviderSubmission:
        return _start_submission_impl(
            job,
            context=context,
            now=now,
            provider=self.provider,
            load_session_fn=_load_session,
            backend_for_session_fn=get_backend_for_session,
            reader_cls=OpenCodeLogReader,
            request_anchor_fn=request_anchor_for_job,
            wrap_prompt_fn=wrap_opencode_prompt,
        )

    def poll(self, submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
        submission = _refresh_reader_for_current_session_binding(submission)
        return _poll_submission_impl(
            submission,
            now=now,
            state_session_path_fn=_state_session_path,
        )


def _refresh_reader_for_current_session_binding(submission: ProviderSubmission) -> ProviderSubmission:
    """Rebuild the reader if the on-disk OpenCode session binding has changed."""
    state = dict(submission.runtime_state)
    if str(state.get('mode') or '').strip().lower() != 'active':
        return submission
    diagnostics = submission.diagnostics if isinstance(submission.diagnostics, dict) else {}
    raw = state.get('workspace_path') or diagnostics.get('workspace_path')
    if not raw:
        return submission
    try:
        work_dir = Path(str(raw)).expanduser()
    except Exception:
        return submission
    session = _load_session(work_dir, agent_name=submission.agent_name)
    if session is None:
        return submission
    reader = state.get('reader')
    if reader is None:
        return submission
    new_reader = OpenCodeLogReader(
        work_dir=Path(session.work_dir),
        project_id=getattr(session, 'opencode_project_id', None) or 'global',
        session_id_filter=getattr(session, 'opencode_session_id_filter', None),
    )
    new_state = new_reader.capture_state()
    old_session_id = str(state.get('state', {}).get('session_id') or state.get('session_id') or '')
    new_session_id = str(new_state.get('session_id') or '')
    if old_session_id == new_session_id:
        return submission
    updated_state = {
        **state,
        'reader': new_reader,
        'state': new_state,
        'session_path': _state_session_path(new_state),
        'workspace_path': str(work_dir),
        'anchor_emitted': True,
    }
    return replace(submission, runtime_state=updated_state)


def _load_session(work_dir: Path, *, agent_name: str):
    return _load_session_impl(work_dir, agent_name=agent_name, primary_agent="opencode", load_project_session_fn=load_project_session)


def _state_session_path(state: dict[str, object]) -> str:
    return _state_session_path_impl(state)


def build_execution_adapter() -> OpenCodeProviderAdapter:
    return OpenCodeProviderAdapter()


__all__ = ["OpenCodeProviderAdapter", "build_execution_adapter"]
