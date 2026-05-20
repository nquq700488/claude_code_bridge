from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from ccbd.api_models import JobRecord
from completion.models import CompletionItemKind, CompletionSourceKind
from provider_core.protocol import request_anchor_for_job
from provider_execution.active import prepare_active_poll, prepare_active_start
from provider_execution.base import ProviderPollResult, ProviderRuntimeContext, ProviderSubmission
from provider_execution.common import build_item, no_wrap_requested, send_prompt_to_runtime_target
from terminal_runtime import get_backend_for_session

from .comm import MmxLogReader
from .protocol_runtime import anchor_seen_in_text, extract_reply_for_req, wrap_mmx_prompt
from .session import load_project_session as _load_project_session


class MmxProviderAdapter:
    provider = 'mmx'

    def restore_diagnostics(self) -> dict[str, object]:
        return {
            'resume_supported': False,
            'restore_mode': 'resubmit_required',
            'restore_reason': 'provider_resume_unsupported',
            'restore_detail': 'mmx uses atomic pane-log turns; restart-time execution resume is not implemented',
        }

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
            return prepared

        return self._build_submission(job, prepared, now=now)

    def poll(self, submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
        prepared = prepare_active_poll(submission, now=now)
        if prepared is None or isinstance(prepared, ProviderPollResult):
            return prepared

        reader = prepared.reader
        state = submission.runtime_state.get('state') or {}
        runtime = _poll_runtime_state(submission)
        items = []

        text, new_state = reader.try_get_message(state)

        if text:
            # Detect anchor echo (daemon received our request)
            if anchor_seen_in_text(text, submission.job_id) and not runtime['anchor_emitted']:
                items.append(
                    build_item(
                        submission,
                        kind=CompletionItemKind.ANCHOR_SEEN,
                        timestamp=now,
                        seq=int(runtime['next_seq']),
                        payload={'turn_id': runtime['request_anchor']},
                    )
                )
                runtime['next_seq'] = int(runtime['next_seq']) + 1
                runtime['anchor_emitted'] = True

            reply, done_seen = extract_reply_for_req(text, submission.job_id)
            if done_seen:
                runtime['reply_buffer'] = reply
                request_anchor = runtime['request_anchor']
                items.append(
                    build_item(
                        submission,
                        kind=CompletionItemKind.ASSISTANT_FINAL,
                        timestamp=now,
                        seq=int(runtime['next_seq']),
                        payload={
                            'text': reply,
                            'reply': reply,
                            'final_answer': reply,
                            'turn_id': request_anchor,
                        },
                    )
                )
                runtime['next_seq'] = int(runtime['next_seq']) + 1
                items.append(
                    build_item(
                        submission,
                        kind=CompletionItemKind.TURN_BOUNDARY,
                        timestamp=now,
                        seq=int(runtime['next_seq']),
                        payload={
                            'reason': 'assistant_completed',
                            'last_agent_message': reply,
                            'turn_id': request_anchor,
                        },
                    )
                )
                runtime['next_seq'] = int(runtime['next_seq']) + 1

        updated = replace(
            submission,
            reply=runtime['reply_buffer'],
            runtime_state={
                **submission.runtime_state,
                'state': new_state,
                'anchor_emitted': runtime['anchor_emitted'],
                'next_seq': runtime['next_seq'],
                'reply_buffer': runtime['reply_buffer'],
            },
        )
        if not items and updated.reply == submission.reply and updated.runtime_state == submission.runtime_state:
            return None
        return ProviderPollResult(submission=updated, items=tuple(items))

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
        # mmx manifest declares supports_resume=False; this method exists only
        # to satisfy the protocol and should not be reached in practice.
        return None

    def _build_submission(self, job: JobRecord, prepared, *, now: str) -> ProviderSubmission:
        log_path = prepared.backend.ensure_pane_log(prepared.pane_id)
        reader = MmxLogReader(work_dir=prepared.work_dir)
        if log_path:
            reader.set_pane_log_path(log_path)
        state = reader.capture_state()

        prompt = job.request.body if no_wrap_requested(job) else wrap_mmx_prompt(job.request.body, job.job_id)
        send_prompt_to_runtime_target(prepared.backend, prepared.pane_id, prompt)

        request_anchor = request_anchor_for_job(job.job_id)
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
                'request_anchor': request_anchor,
                'anchor_emitted': False,
                'next_seq': 1,
                'reply_buffer': '',
            },
        )


def _poll_runtime_state(submission: ProviderSubmission) -> dict[str, object]:
    runtime_state = submission.runtime_state
    return {
        'request_anchor': str(runtime_state.get('request_anchor') or '').strip() or None,
        'next_seq': int(runtime_state.get('next_seq', 1)),
        'anchor_emitted': bool(runtime_state.get('anchor_emitted', False)),
        'reply_buffer': str(runtime_state.get('reply_buffer') or ''),
    }


def _load_session(work_dir: Path, *, agent_name: str):
    """Wrap load_project_session to accept agent_name keyword argument."""
    return _load_project_session(work_dir, instance=agent_name)


def build_execution_adapter():
    return MmxProviderAdapter()


__all__ = ['MmxProviderAdapter', 'build_execution_adapter']
