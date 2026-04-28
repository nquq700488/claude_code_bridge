from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ccbd.api_models import JobRecord
from completion.models import CompletionConfidence, CompletionDecision, CompletionItemKind, CompletionSourceKind, CompletionStatus
from provider_core.protocol import request_anchor_for_job
from provider_execution.active import prepare_active_poll, prepare_active_start
from provider_execution.base import ProviderPollResult, ProviderRuntimeContext, ProviderSubmission
from provider_execution.common import build_item, no_wrap_requested, send_prompt_to_runtime_target
from terminal_runtime import get_backend_for_session

from .comm import KimiLogReader
from .protocol_runtime import extract_reply_for_req, wrap_kimi_prompt
from .session import load_project_session


class KimiProviderAdapter:
    provider = "kimi"

    def restore_diagnostics(self) -> dict[str, object]:
        return {
            "resume_supported": False,
            "restore_mode": "resubmit_required",
            "restore_reason": "provider_resume_unsupported",
            "restore_detail": "kimi live polling works, but restart-time execution resume is not implemented yet",
        }

    def start(self, job: JobRecord, *, context: ProviderRuntimeContext | None, now: str) -> ProviderSubmission:
        prepared = prepare_active_start(
            job,
            context=context,
            provider=self.provider,
            source_kind=CompletionSourceKind.SESSION_SNAPSHOT,
            now=now,
            missing_session_reason="missing_kimi_session",
            load_session_fn=load_project_session,
            backend_for_session_fn=get_backend_for_session,
        )
        if not hasattr(prepared, "session"):
            # Error submission returned
            return prepared

        reader = KimiLogReader(work_dir=Path(prepared.session.work_dir))
        state = reader.capture_state()
        request_anchor = request_anchor_for_job(job.job_id)
        no_wrap = no_wrap_requested(job)
        prompt = job.request.body if no_wrap else wrap_kimi_prompt(job.request.body, request_anchor)
        send_prompt_to_runtime_target(prepared.backend, prepared.pane_id, prompt)

        return ProviderSubmission(
            job_id=job.job_id,
            agent_name=job.agent_name,
            provider=self.provider,
            accepted_at=now,
            ready_at=now,
            source_kind=CompletionSourceKind.SESSION_SNAPSHOT,
            reply="",
            diagnostics={"provider": self.provider, "mode": "active", "workspace_path": str(prepared.work_dir)},
            runtime_state={
                "mode": "active",
                "reader": reader,
                "state": state,
                "backend": prepared.backend,
                "pane_id": prepared.pane_id,
                "request_anchor": request_anchor,
                "next_seq": 1,
                "anchor_emitted": no_wrap,
                "reply_buffer": "",
                "session_path": state.get("context_path", ""),
                "no_wrap": no_wrap,
            },
        )

    def poll(self, submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
        prepared = prepare_active_poll(submission, now=now)
        if prepared is None or isinstance(prepared, ProviderPollResult):
            return prepared

        state = submission.runtime_state.get("state") or {}
        runtime = _poll_runtime_state(submission)
        items = []

        reply, state = prepared.reader.try_get_message(state)

        # Session rotation detection (context path changed)
        new_session_path = str(state.get("context_path") or "")
        _apply_session_rotation(submission, runtime, items, new_session_path=new_session_path, now=now)

        # Emit anchor once before the first reply
        _emit_anchor(submission, runtime, items, now=now)

        if reply:
            _append_reply_item(submission, runtime, items, reply=reply, state=state, now=now)

        updated = replace(
            submission,
            reply=runtime["reply_buffer"],
            runtime_state={
                **submission.runtime_state,
                "state": state,
                "next_seq": runtime["next_seq"],
                "anchor_emitted": runtime["anchor_emitted"],
                "reply_buffer": runtime["reply_buffer"],
                "session_path": runtime["session_path"],
            },
        )
        if not items and updated.reply == submission.reply and updated.runtime_state == submission.runtime_state:
            return None
        return ProviderPollResult(submission=updated, items=tuple(items))


def _poll_runtime_state(submission: ProviderSubmission) -> dict[str, object]:
    runtime_state = submission.runtime_state
    return {
        "request_anchor": str(runtime_state.get("request_anchor") or "").strip() or None,
        "next_seq": int(runtime_state.get("next_seq", 1)),
        "anchor_emitted": bool(runtime_state.get("anchor_emitted", False)),
        "no_wrap": bool(runtime_state.get("no_wrap", False)),
        "reply_buffer": str(runtime_state.get("reply_buffer") or ""),
        "session_path": str(runtime_state.get("session_path") or ""),
    }


def _apply_session_rotation(
    submission: ProviderSubmission,
    runtime: dict[str, object],
    items: list,
    *,
    new_session_path: str | None,
    now: str,
) -> None:
    session_path = str(runtime["session_path"])
    if not new_session_path or new_session_path == session_path:
        return
    items.append(
        build_item(
            submission,
            kind=CompletionItemKind.SESSION_ROTATE,
            timestamp=now,
            seq=int(runtime["next_seq"]),
            payload={
                "session_path": new_session_path,
            },
            cursor_kwargs={"session_path": new_session_path},
        )
    )
    runtime["next_seq"] = int(runtime["next_seq"]) + 1
    runtime["session_path"] = new_session_path
    runtime["anchor_emitted"] = bool(runtime["no_wrap"])
    runtime["reply_buffer"] = ""


def _emit_anchor(
    submission: ProviderSubmission,
    runtime: dict[str, object],
    items: list,
    *,
    now: str,
) -> None:
    if runtime["anchor_emitted"]:
        return
    session_path = str(runtime["session_path"] or "") or None
    items.append(
        build_item(
            submission,
            kind=CompletionItemKind.ANCHOR_SEEN,
            timestamp=now,
            seq=int(runtime["next_seq"]),
            payload={"turn_id": runtime["request_anchor"]},
            cursor_kwargs={"session_path": session_path},
        )
    )
    runtime["next_seq"] = int(runtime["next_seq"]) + 1
    runtime["anchor_emitted"] = True


def _append_reply_item(
    submission: ProviderSubmission,
    runtime: dict[str, object],
    items: list,
    *,
    reply,
    state: dict[str, object],
    now: str,
) -> None:
    if not _reply_matches_request(runtime, state):
        return
    request_anchor = str(runtime["request_anchor"] or "").strip() or None
    cleaned = _clean_reply(reply)
    if not cleaned:
        return
    runtime["reply_buffer"] = cleaned
    session_path = str(runtime["session_path"] or "") or None
    items.append(
        build_item(
            submission,
            kind=CompletionItemKind.ASSISTANT_FINAL,
            timestamp=now,
            seq=int(runtime["next_seq"]),
            payload={
                "text": cleaned,
                "reply": cleaned,
                "final_answer": cleaned,
                "turn_id": request_anchor,
                "session_path": session_path,
            },
            cursor_kwargs={"session_path": session_path},
        )
    )
    runtime["next_seq"] = int(runtime["next_seq"]) + 1
    items.append(
        build_item(
            submission,
            kind=CompletionItemKind.TURN_BOUNDARY,
            timestamp=now,
            seq=int(runtime["next_seq"]),
            payload={
                "reason": "assistant_completed",
                "last_agent_message": cleaned,
                "turn_id": request_anchor,
                "session_path": session_path,
            },
            cursor_kwargs={"session_path": session_path},
        )
    )
    runtime["next_seq"] = int(runtime["next_seq"]) + 1


def _reply_matches_request(runtime: dict[str, object], state: dict[str, object]) -> bool:
    if bool(runtime.get("no_wrap", False)):
        return True
    # Kimi does not embed req_id in structured logs; we conservatively accept
    # any new assistant message after our prompt was sent.
    return True


def _clean_reply(reply) -> str:
    return str(reply).strip()


def build_execution_adapter() -> KimiProviderAdapter:
    return KimiProviderAdapter()


__all__ = ["KimiProviderAdapter", "build_execution_adapter"]
