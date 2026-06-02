"""
Kimi communication module.

Reads replies from Kimi session storage and sends messages by injecting
text into the Kimi TUI pane via tmux.

Supports two Kimi CLI session formats:
- Legacy:  ~/.kimi/sessions/<MD5>/<uuid>/context.jsonl
- Current: ~/.kimi-code/sessions/wd_<name>_<hash>/session_<uuid>/agents/main/wire.jsonl
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

KIMI_SESSIONS_ROOT = Path.home() / ".kimi" / "sessions"
KIMI_CODE_SESSIONS_ROOT = Path.home() / ".kimi-code" / "sessions"
SESSION_INDEX_PATH = Path.home() / ".kimi-code" / "session_index.jsonl"


# ── legacy format (context.jsonl) ──────────────────────────────────────────

def _work_dir_hash(work_dir: Path) -> str:
    """Compute Kimi's work-dir hash (MD5 of absolute path string)."""
    normalized = str(work_dir.resolve())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def _find_latest_session_uuid(session_dir: Path) -> Optional[str]:
    """Find the session with the most recently modified context.jsonl."""
    if not session_dir.exists():
        return None
    candidates = []
    for entry in session_dir.iterdir():
        if not entry.is_dir():
            continue
        context_path = entry / "context.jsonl"
        if not context_path.is_file():
            continue
        try:
            mtime = context_path.stat().st_mtime
        except OSError:
            continue
        candidates.append((mtime, entry.name))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _resolve_context_jsonl(work_dir: Path, *, prefer_uuid: Optional[str] = None) -> Tuple[Optional[Path], Optional[str]]:
    """Resolve the path to Kimi's context.jsonl for a given work_dir.

    Returns (path, uuid) where uuid is the session UUID.
    """
    h = _work_dir_hash(work_dir)
    session_dir = KIMI_SESSIONS_ROOT / h

    if prefer_uuid:
        preferred = session_dir / prefer_uuid / "context.jsonl"
        if preferred.exists():
            return preferred, prefer_uuid

    uuid = _find_latest_session_uuid(session_dir)
    if not uuid:
        return None, None
    context_path = session_dir / uuid / "context.jsonl"
    if context_path.exists():
        return context_path, uuid
    return None, None


def _parse_new_lines(path: Path, last_pos: int) -> Tuple[list[dict], int]:
    """Parse only new lines from a JSONL file since last_pos.

    Returns (new_messages, new_pos).
    """
    new_messages: list[dict] = []
    try:
        file_size = path.stat().st_size
    except OSError:
        return [], last_pos

    if last_pos > file_size:
        last_pos = 0

    try:
        with path.open("r", encoding="utf-8") as f:
            if last_pos > 0:
                try:
                    f.seek(last_pos)
                except OSError:
                    pass
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        new_messages.append(obj)
                except json.JSONDecodeError:
                    continue
            new_pos = f.tell()
    except OSError:
        return [], last_pos
    return new_messages, new_pos


def _extract_assistant_text(messages: list[dict]) -> Optional[str]:
    """Extract human-readable text from the latest assistant message."""
    for msg in reversed(messages):
        role = msg.get("role")
        if role != "assistant":
            continue
        content = msg.get("content")
        if not content:
            continue
        texts: list[str] = []
        thinks: list[str] = []
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                part_type = part.get("type")
                if part_type == "text":
                    text = part.get("text")
                    if text:
                        texts.append(str(text))
                elif part_type == "think":
                    think = part.get("think")
                    if think:
                        thinks.append(str(think))
        elif isinstance(content, str):
            texts.append(content)
        if texts:
            return "\n".join(texts)
        if thinks:
            return "\n".join(thinks)
    return None


def _extract_assistant_think(messages: list[dict]) -> Optional[str]:
    """Extract think/reasoning content from the latest assistant message."""
    for msg in reversed(messages):
        role = msg.get("role")
        if role != "assistant":
            continue
        content = msg.get("content")
        if not content:
            continue
        thinks: list[str] = []
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "think":
                    think = part.get("think")
                    if think:
                        thinks.append(str(think))
        if thinks:
            return "\n".join(thinks)
    return None


def _latest_checkpoint(messages: list[dict]) -> int:
    """Return the highest checkpoint id seen in messages."""
    highest = -1
    for msg in messages:
        if msg.get("role") == "_checkpoint":
            cid = msg.get("id")
            if isinstance(cid, int) and cid > highest:
                highest = cid
    return highest


# ── current format (wire.jsonl) ────────────────────────────────────────────

def _resolve_wire_session(work_dir: Path, *, prefer_uuid: Optional[str] = None) -> Optional[Path]:
    """Find the latest wire.jsonl session dir for work_dir via session_index.jsonl.

    Returns the path to the wire.jsonl file, or None if no session found.
    """
    index_path = SESSION_INDEX_PATH
    if not index_path.exists():
        return None

    work_dir_str = str(work_dir.resolve())
    best_mtime = 0.0
    best_wire_path: Optional[Path] = None

    try:
        with index_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("workDir") != work_dir_str:
                    continue
                session_dir = Path(entry["sessionDir"])
                wire_path = session_dir / "agents" / "main" / "wire.jsonl"
                if not wire_path.is_file():
                    continue
                if prefer_uuid and entry.get("sessionId") == prefer_uuid:
                    return wire_path
                try:
                    mtime = wire_path.stat().st_mtime
                except OSError:
                    mtime = 0.0
                if mtime > best_mtime:
                    best_mtime = mtime
                    best_wire_path = wire_path
    except OSError:
        pass

    return best_wire_path


def _extract_wire_reply_text_and_terminal(events: list[dict]) -> Tuple[Optional[str], Optional[str], bool]:
    """Extract reply text and think content from wire.jsonl events.

    Returns (text, think, has_end_turn) — the concatenated text/think parts
    from content.part events, and whether a turn-ending step.end event
    with finishReason == 'end_turn' was observed.
    """
    text_parts: list[str] = []
    think_parts: list[str] = []
    has_end_turn = False
    for ev in events:
        ev_type = ev.get("type")
        if ev_type != "context.append_loop_event":
            continue
        inner = ev.get("event") or {}
        inner_type = inner.get("type")
        if inner_type == "content.part":
            part = inner.get("part") or {}
            part_type = part.get("type")
            if part_type == "text":
                t = (part.get("text") or "").strip()
                if t:
                    text_parts.append(t)
            elif part_type == "think":
                t = (part.get("think") or "").strip()
                if t:
                    think_parts.append(t)
        elif inner_type == "step.end":
            if inner.get("finishReason") == "end_turn":
                has_end_turn = True
    text = "\n".join(text_parts) if text_parts else None
    think = "\n".join(think_parts) if think_parts else None
    return text, think, has_end_turn


# ── unified reader ─────────────────────────────────────────────────────────

class KimiLogReader:
    """Read assistant replies from Kimi session storage.

    Supports both legacy (context.jsonl) and current (wire.jsonl) formats.
    """

    def __init__(self, work_dir: Path):
        self.work_dir = work_dir

    def capture_state(self) -> Dict[str, Any]:
        """Capture the current reading state, preferring wire format."""
        wire_path = _resolve_wire_session(self.work_dir)
        if wire_path is not None:
            return self._capture_wire_state(wire_path)

        context_path, uuid = _resolve_context_jsonl(self.work_dir)
        if context_path is not None:
            return self._capture_context_state(context_path, uuid)

        return {
            "format": None,
            "context_path": None,
            "session_uuid": None,
            "last_checkpoint": -1,
            "last_text_hash": "",
            "last_pos": 0,
            "last_inode": None,
        }

    def _capture_wire_state(self, wire_path: Path) -> Dict[str, Any]:
        events, file_pos = _parse_new_lines(wire_path, 0)
        text, think, _ = _extract_wire_reply_text_and_terminal(events)
        try:
            inode = wire_path.stat().st_ino
        except OSError:
            inode = None

        return {
            "format": "wire_jsonl",
            "context_path": str(wire_path),
            "session_uuid": None,
            "last_checkpoint": -1,
            "last_text_hash": hashlib.sha256((text or "").encode()).hexdigest() if text else "",
            "last_think": think or "",
            "last_think_hash": hashlib.sha256((think or "").encode()).hexdigest() if think else "",
            "last_pos": file_pos,
            "last_inode": inode,
            "pending_text": "",
        }

    def _capture_context_state(self, context_path: Path, uuid: Optional[str]) -> Dict[str, Any]:
        messages, file_pos = _parse_new_lines(context_path, 0)
        checkpoint = _latest_checkpoint(messages)
        text = _extract_assistant_text(messages)
        think = _extract_assistant_think(messages)
        try:
            inode = context_path.stat().st_ino
        except OSError:
            inode = None

        return {
            "format": "context_jsonl",
            "context_path": str(context_path),
            "session_uuid": uuid,
            "last_checkpoint": checkpoint,
            "last_text_hash": hashlib.sha256((text or "").encode()).hexdigest() if text else "",
            "last_think": think or "",
            "last_think_hash": hashlib.sha256((think or "").encode()).hexdigest() if think else "",
            "last_pos": file_pos,
            "last_inode": inode,
        }

    def try_get_message(self, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        """Try to read a new assistant message since the given state.

        Returns (reply_text, new_state).
        """
        fmt = state.get("format")
        if fmt == "wire_jsonl":
            return self._try_get_wire_message(state)
        return self._try_get_context_message(state)

    def _try_get_wire_message(self, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        wire_path = _resolve_wire_session(self.work_dir, prefer_uuid=state.get("session_uuid"))
        if wire_path is None:
            return None, state

        last_inode = state.get("last_inode")
        try:
            current_inode = wire_path.stat().st_ino
        except OSError:
            current_inode = None

        last_pos = state.get("last_pos", 0)
        if current_inode is not None and last_inode is not None and current_inode != last_inode:
            last_pos = 0

        events, file_pos = _parse_new_lines(wire_path, last_pos)
        if not events:
            return None, {
                **state,
                "context_path": str(wire_path),
                "last_pos": file_pos,
                "last_inode": current_inode,
            }

        new_text, new_think, has_end_turn = _extract_wire_reply_text_and_terminal(events)

        # If the file was replaced (inode changed), discard any pending text from the old file.
        pending_text = str(state.get("pending_text") or "") if (current_inode == last_inode) else ""
        if new_text:
            pending_text = (pending_text + "\n" + new_text).strip()

        # Build updated state with new think/position (think partials can still be emitted).
        updated_state = {
            **state,
            "context_path": str(wire_path),
            "last_think": new_think or state.get("last_think", ""),
            "last_think_hash": hashlib.sha256((new_think or "").encode()).hexdigest(),
            "last_pos": file_pos,
            "last_inode": current_inode,
            "pending_text": pending_text,
        }

        # Only emit a reply once the turn has definitively ended.
        if not has_end_turn:
            return None, updated_state

        if not pending_text:
            return None, {
                **updated_state,
                "pending_text": "",
            }

        text_hash = hashlib.sha256(pending_text.encode()).hexdigest()
        if text_hash == state.get("last_text_hash"):
            return None, {
                **updated_state,
                "pending_text": "",
            }

        return pending_text, {
            **updated_state,
            "last_text_hash": text_hash,
            "pending_text": "",
        }

    def _try_get_context_message(self, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        prefer_uuid: Optional[str] = state.get("session_uuid")
        context_path, uuid = _resolve_context_jsonl(self.work_dir, prefer_uuid=prefer_uuid)
        if not context_path:
            return None, state

        last_inode = state.get("last_inode")
        try:
            current_inode = context_path.stat().st_ino
        except OSError:
            current_inode = None

        last_pos = state.get("last_pos", 0)
        if current_inode is not None and last_inode is not None and current_inode != last_inode:
            last_pos = 0

        new_messages, file_pos = _parse_new_lines(context_path, last_pos)
        if not new_messages:
            return None, {
                **state,
                "context_path": str(context_path),
                "session_uuid": uuid,
                "last_pos": file_pos,
                "last_inode": current_inode,
            }

        checkpoint = _latest_checkpoint(new_messages)
        new_text = _extract_assistant_text(new_messages)
        new_think = _extract_assistant_think(new_messages)

        if not new_text:
            return None, {
                **state,
                "context_path": str(context_path),
                "session_uuid": uuid,
                "last_checkpoint": max(checkpoint, state.get("last_checkpoint", -1)),
                "last_think": new_think or state.get("last_think", ""),
                "last_think_hash": hashlib.sha256((new_think or "").encode()).hexdigest(),
                "last_pos": file_pos,
                "last_inode": current_inode,
            }

        text_hash = hashlib.sha256(new_text.encode()).hexdigest()
        if text_hash == state.get("last_text_hash"):
            return None, {
                **state,
                "last_think": new_think or state.get("last_think", ""),
                "last_think_hash": hashlib.sha256((new_think or "").encode()).hexdigest(),
                "last_pos": file_pos,
                "last_inode": current_inode,
            }

        new_state = {
            **state,
            "context_path": str(context_path),
            "session_uuid": uuid,
            "last_checkpoint": max(checkpoint, state.get("last_checkpoint", -1)),
            "last_text_hash": text_hash,
            "last_think": new_think or "",
            "last_think_hash": hashlib.sha256((new_think or "").encode()).hexdigest(),
            "last_pos": file_pos,
            "last_inode": current_inode,
        }
        return new_text, new_state


class KimiCommunicator:
    """Facade for Kimi pane communication (not used directly by execution adapter)."""

    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self.reader = KimiLogReader(work_dir=work_dir)


def _list_session_candidates(work_dir: Path) -> tuple[tuple[float, str, Path], ...]:
    """List all valid Kimi session candidates for a work_dir, sorted by mtime desc."""
    h = _work_dir_hash(work_dir)
    session_dir = KIMI_SESSIONS_ROOT / h
    candidates: list[tuple[float, str, Path]] = []
    try:
        for entry in session_dir.iterdir():
            if not entry.is_dir():
                continue
            context_path = entry / "context.jsonl"
            if not context_path.is_file():
                continue
            try:
                mtime = context_path.stat().st_mtime
            except OSError:
                continue
            candidates.append((mtime, entry.name, context_path))
    except OSError:
        return ()
    candidates.sort(key=lambda x: x[0], reverse=True)
    return tuple(candidates)


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _is_bound_elsewhere(uuid: str, work_dir: Path) -> bool:
    """Check if the given Kimi session uuid is bound by another CCB session."""
    from .session import find_project_session_file

    session_file = find_project_session_file(work_dir)
    if not session_file:
        return False

    latest_path = KIMI_SESSIONS_ROOT / _work_dir_hash(work_dir) / uuid / "context.jsonl"
    try:
        latest_resolved = latest_path.resolve()
    except OSError:
        latest_resolved = latest_path

    session_dir = session_file.parent
    try:
        other_sessions = sorted(session_dir.glob(".kimi*-session"))
    except OSError:
        return False

    for other in other_sessions:
        if other.resolve() == session_file.resolve():
            continue
        data = _read_json(other)
        if not data:
            continue
        other_path = str(data.get("kimi_session_path") or "").strip()
        if other_path:
            try:
                if Path(other_path).resolve() == latest_resolved:
                    return True
            except OSError:
                pass
        other_uuid = str(data.get("kimi_session_id") or "").strip()
        if other_uuid == uuid:
            return True
    return False


__all__ = ["KimiCommunicator", "KimiLogReader", "KIMI_SESSIONS_ROOT"]
