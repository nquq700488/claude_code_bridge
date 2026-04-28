from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable

from ccbd.api_models import JobRecord
from completion.models import (
    CompletionConfidence,
    CompletionDecision,
    CompletionSourceKind,
    CompletionStatus,
)
from provider_execution.active import prepare_active_poll, prepare_active_start
from provider_execution.base import ProviderPollResult, ProviderRuntimeContext, ProviderSubmission
from provider_execution.common import no_wrap_requested, send_prompt_to_runtime_target
from provider_execution.common_runtime.terminal import send_prompt_to_runtime_target as _send_prompt
from terminal_runtime import get_backend_for_session

from .comm import MmxLogReader
from .protocol_runtime import extract_reply_for_req, wrap_mmx_prompt
from .session import load_project_session as _load_project_session


class MmxProviderAdapter:
    provider = 'mmx'

    def start(self, job: JobRecord, *, context: ProviderRuntimeContext | None, now: str) -> ProviderSubmission:
        prepared = prepare_active_start(
            job,
            context=context,
            provider='mmx',
            source_kind=CompletionSourceKind.PROTOCOL_EVENT_STREAM,
            now=now,
            missing_session_reason='missing_mmx_session',
            load_session_fn=_load_session,
            backend_for_session_fn=get_backend_for_session,
        )
        if not hasattr(prepared, 'session'):
            # Error submission returned
            return prepared

        # Ensure pane log is configured so the reader can observe output
        log_path = prepared.backend.ensure_pane_log(prepared.pane_id)
        reader = MmxLogReader(work_dir=prepared.work_dir)
        if log_path:
            reader.set_pane_log_path(log_path)
        state = reader.capture_state()

        prompt = job.request.body if no_wrap_requested(job) else wrap_mmx_prompt(job.request.body, job.job_id)
        send_prompt_to_runtime_target(prepared.backend, prepared.pane_id, prompt)

        return ProviderSubmission(
            job_id=job.job_id,
            agent_name=job.agent_name,
            provider='mmx',
            accepted_at=now,
            ready_at=now,
            source_kind=CompletionSourceKind.PROTOCOL_EVENT_STREAM,
            reply='',
            diagnostics={'provider': 'mmx', 'mode': 'active', 'workspace_path': str(prepared.work_dir)},
            runtime_state={
                'mode': 'active',
                'reader': reader,
                'state': state,
                'backend': prepared.backend,
                'pane_id': prepared.pane_id,
                'workspace_path': str(prepared.work_dir),
            },
        )

    def poll(self, submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
        prepared = prepare_active_poll(submission, now=now)
        if prepared is None or isinstance(prepared, ProviderPollResult):
            return prepared

        reader = prepared.reader
        state = submission.runtime_state.get('state') or {}

        text, new_state = reader.try_get_message(state)

        if text:
            reply, done_seen = extract_reply_for_req(text, submission.job_id)
            if done_seen:
                decision = CompletionDecision(
                    terminal=True,
                    status=CompletionStatus.COMPLETED,
                    reason='completed',
                    confidence=CompletionConfidence.EXACT,
                    reply=reply,
                    anchor_seen=True,
                    reply_started=True,
                    reply_stable=True,
                    provider_turn_ref=None,
                    source_cursor=None,
                    finished_at=now,
                )
                return ProviderPollResult(
                    submission=replace(
                        submission,
                        reply=reply,
                        status=CompletionStatus.COMPLETED,
                        runtime_state={**submission.runtime_state, 'state': new_state},
                    ),
                    decision=decision,
                )

        # Update state for next poll
        submission.runtime_state['state'] = new_state
        return None

    def export_runtime_state(self, submission: ProviderSubmission) -> dict[str, object]:
        return {
            'mode': submission.runtime_state.get('mode'),
            'state': submission.runtime_state.get('state') or {},
            'pane_id': submission.runtime_state.get('pane_id'),
            'workspace_path': submission.runtime_state.get('workspace_path'),
        }

    def resume(
        self,
        job: JobRecord,
        submission: ProviderSubmission,
        *,
        context: ProviderRuntimeContext | None,
        persisted_state,
        now: str,
    ) -> ProviderSubmission | None:
        # For mmx, resume is similar to start but reuses the existing pane
        prepared = prepare_active_start(
            job,
            context=context,
            provider='mmx',
            source_kind=CompletionSourceKind.PROTOCOL_EVENT_STREAM,
            now=now,
            missing_session_reason='missing_mmx_session',
            load_session_fn=_load_session,
            backend_for_session_fn=get_backend_for_session,
        )
        if not hasattr(prepared, 'session'):
            return prepared

        log_path = prepared.backend.ensure_pane_log(prepared.pane_id)
        reader = MmxLogReader(work_dir=prepared.work_dir)
        if log_path:
            reader.set_pane_log_path(log_path)
        state = reader.capture_state()

        return ProviderSubmission(
            job_id=job.job_id,
            agent_name=job.agent_name,
            provider='mmx',
            accepted_at=now,
            ready_at=now,
            source_kind=CompletionSourceKind.PROTOCOL_EVENT_STREAM,
            reply='',
            diagnostics={'provider': 'mmx', 'mode': 'active', 'workspace_path': str(prepared.work_dir)},
            runtime_state={
                'mode': 'active',
                'reader': reader,
                'state': state,
                'backend': prepared.backend,
                'pane_id': prepared.pane_id,
                'workspace_path': str(prepared.work_dir),
            },
        )


def _load_session(work_dir: Path, *, agent_name: str):
    """Wrap load_project_session to accept agent_name keyword argument."""
    return _load_project_session(work_dir, instance=agent_name)


def build_execution_adapter():
    return MmxProviderAdapter()


__all__ = ['MmxProviderAdapter', 'build_execution_adapter']
