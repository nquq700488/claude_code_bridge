from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ccbd.api_models import JobRecord
from completion.models import CompletionConfidence, CompletionDecision, CompletionItemKind, CompletionSourceKind, CompletionStatus
from provider_core.protocol import request_anchor_for_job
from provider_execution.active import prepare_active_poll, prepare_active_start
from provider_execution.base import ProviderPollResult, ProviderRuntimeContext, ProviderSubmission
from provider_execution.common import build_item, no_wrap_requested, send_prompt_to_runtime_target
from provider_execution.reliability import CompletionReliabilityPolicy
from terminal_runtime import get_backend_for_session

from .comm import KimiLogReader, _is_bound_elsewhere, _list_session_candidates
from .protocol_runtime import extract_reply_for_req, wrap_kimi_prompt
from .session import load_project_session as _load_project_session


class KimiProviderAdapter:
    provider = "kimi"
    completion_reliability_policy = CompletionReliabilityPolicy(
        provider='kimi',
        primary_authority='session_snapshot',
        no_terminal_timeout_s=600.0,
    )

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
            load_session_fn=_load_session,
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
                "session_uuid": state.get("session_uuid", ""),
                "no_wrap": no_wrap,
                "workspace_path": str(prepared.work_dir),
            },
        )

    def poll(self, submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
        submission = _refresh_reader_for_current_session_binding(submission)
        prepared = prepare_active_poll(submission, now=now)
        if prepared is None or isinstance(prepared, ProviderPollResult):
            return prepared

        state = submission.runtime_state.get("state") or {}
        runtime = _poll_runtime_state(submission)
        items = []

        # --- Session auto-discovery: switch to newer session if safe ---
        state, _ = _maybe_rotate_session(
            state,
            work_dir=prepared.reader.work_dir,
            runtime=runtime,
            items=items,
            submission=submission,
            now=now,
        )

        reply, state = prepared.reader.try_get_message(state)

        # Session rotation detection (context path changed by reader)
        new_session_path = str(state.get("context_path") or "")
        _apply_session_rotation(submission, runtime, items, new_session_path=new_session_path, now=now)

        # Emit anchor once before the first reply
        _emit_anchor(submission, runtime, items, now=now)

        # Emit think content as partial progress (visible feedback during long tasks)
        _emit_think_partial(submission, runtime, items, state=state, now=now)

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
                "session_uuid": runtime["session_uuid"],
            },
        )
        if not items and updated.reply == submission.reply and updated.runtime_state == submission.runtime_state:
            return None
        return ProviderPollResult(submission=updated, items=tuple(items))


def _refresh_reader_for_current_session_binding(submission: ProviderSubmission) -> ProviderSubmission:
    """Rebuild the reader if the on-disk Kimi session binding has changed.

    Kimi's reader re-resolves session paths on every try_get_message call,
    so the reader itself is less stale-prone. This acts as defense-in-depth
    to catch cases where the session uuid or context path changed since start.
    """
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
    new_reader = KimiLogReader(work_dir=Path(session.work_dir))
    new_state = new_reader.capture_state()
    old_session_uuid = str(state.get('session_uuid') or '')
    new_session_uuid = str(new_state.get('session_uuid') or '')
    old_context_path = str(state.get('state', {}).get('context_path') or state.get('session_path') or '')
    new_context_path = str(new_state.get('context_path') or '')
    if old_session_uuid == new_session_uuid and old_context_path == new_context_path:
        return submission
    return replace(
        submission,
        runtime_state={
            **state,
            'reader': new_reader,
            'state': new_state,
            'session_path': new_state.get('context_path', ''),
            'session_uuid': new_state.get('session_uuid', ''),
            'workspace_path': str(work_dir),
            'anchor_emitted': state.get('no_wrap', False),
            'reply_buffer': '',
        },
    )


def _poll_runtime_state(submission: ProviderSubmission) -> dict[str, object]:
    runtime_state = submission.runtime_state
    return {
        "request_anchor": str(runtime_state.get("request_anchor") or "").strip() or None,
        "next_seq": int(runtime_state.get("next_seq", 1)),
        "anchor_emitted": bool(runtime_state.get("anchor_emitted", False)),
        "no_wrap": bool(runtime_state.get("no_wrap", False)),
        "reply_buffer": str(runtime_state.get("reply_buffer") or ""),
        "session_path": str(runtime_state.get("session_path") or ""),
        "session_uuid": str(runtime_state.get("session_uuid") or ""),
        "last_think_hash": str(runtime_state.get("last_think_hash") or ""),
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
    """Check whether the reply from the reader belongs to the current request.

    Kimi's structured logs (context.jsonl) do not embed request anchors, so
    exact correlation is not possible. The KimiLogReader already guards against
    stale data via checkpoint and text-hash comparison, so the reply we receive
    here is guaranteed to be new since the last poll. We conservatively accept
    it as belonging to the current turn.
    """
    if bool(runtime.get("no_wrap", False)):
        return True
    return True


def _clean_reply(reply) -> str:
    return str(reply).strip()


def _emit_think_partial(
    submission: ProviderSubmission,
    runtime: dict[str, object],
    items: list,
    *,
    state: dict[str, object],
    now: str,
) -> None:
    """Emit ASSISTANT_PARTIAL with think content for visible progress during long tasks."""
    think = str(state.get("last_think") or "").strip()
    if not think:
        return
    think_hash = str(state.get("last_think_hash") or "").strip()
    if think_hash == runtime.get("last_think_hash"):
        return
    session_path = str(runtime["session_path"] or "") or None
    items.append(
        build_item(
            submission,
            kind=CompletionItemKind.ASSISTANT_CHUNK,
            timestamp=now,
            seq=int(runtime["next_seq"]),
            payload={
                "text": think,
                "turn_id": runtime["request_anchor"],
                "session_path": session_path,
            },
            cursor_kwargs={"session_path": session_path},
        )
    )
    runtime["next_seq"] = int(runtime["next_seq"]) + 1
    runtime["last_think_hash"] = think_hash


def _maybe_rotate_session(
    state: dict[str, object],
    *,
    work_dir: Path,
    runtime: dict[str, object],
    items: list,
    submission: ProviderSubmission,
    now: str,
) -> tuple[dict[str, object], bool]:
    """Check if a newer Kimi session exists and rotate if safe.

    Returns (new_state, rotated).
    """
    current_uuid = str(state.get("session_uuid") or "").strip()
    candidates = _list_session_candidates(work_dir)
    if not candidates:
        return state, False

    latest_mtime, latest_uuid, latest_path = candidates[0]
    if latest_uuid == current_uuid:
        return state, False

    # Find current session's mtime among candidates
    current_mtime = 0.0
    for mtime, uuid, _ in candidates:
        if uuid == current_uuid:
            current_mtime = mtime
            break

    if current_uuid and current_mtime >= latest_mtime:
        return state, False

    # Avoid switching to a session already bound by another CCB agent
    if _is_bound_elsewhere(latest_uuid, work_dir):
        return state, False

    # Rotate: emit event and reset reader state for the new session
    items.append(
        build_item(
            submission,
            kind=CompletionItemKind.SESSION_ROTATE,
            timestamp=now,
            seq=int(runtime["next_seq"]),
            payload={
                "session_path": str(latest_path),
                "old_session_uuid": current_uuid,
                "new_session_uuid": latest_uuid,
            },
            cursor_kwargs={"session_path": str(latest_path)},
        )
    )
    runtime["next_seq"] = int(runtime["next_seq"]) + 1
    runtime["anchor_emitted"] = bool(runtime["no_wrap"])
    runtime["reply_buffer"] = ""
    runtime["session_uuid"] = latest_uuid

    new_state = {
        **state,
        "session_uuid": latest_uuid,
        "context_path": str(latest_path),
        "last_pos": 0,
        "last_inode": None,
        "last_checkpoint": -1,
        "last_text_hash": "",
        "pending_text": "",
    }
    return new_state, True


def _load_session(work_dir: Path, *, agent_name: str):
    """Wrap load_project_session to accept agent_name keyword argument."""
    return _load_project_session(work_dir, instance=agent_name)


def build_execution_adapter() -> KimiProviderAdapter:
    return KimiProviderAdapter()


__all__ = ["KimiProviderAdapter", "build_execution_adapter"]
