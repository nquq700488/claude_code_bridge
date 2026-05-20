"""
Kimi communication module.

Reads replies from Kimi session storage (~/.kimi/sessions/<hash>/<uuid>/context.jsonl)
and sends messages by injecting text into the Kimi TUI pane via tmux.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


KIMI_SESSIONS_ROOT = Path.home() / ".kimi" / "sessions"


def _work_dir_hash(work_dir: Path) -> str:
    """Compute Kimi's work-dir hash (MD5 of absolute path string).

    Uses MD5 to match Kimi CLI's own session-directory naming convention.
    """
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
    If prefer_uuid is given and that session still exists, use it to avoid
    jumping between sessions.
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
    """Parse only new lines from context.jsonl since last_pos.

    Returns (new_messages, new_pos).
    """
    new_messages: list[dict] = []
    try:
        file_size = path.stat().st_size
    except OSError:
        return [], last_pos

    # If the file shrank (truncation or rotation), start from the beginning
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
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text")
                    if text:
                        texts.append(str(text))
        elif isinstance(content, str):
            texts.append(content)
        if texts:
            return "\n".join(texts)
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


class KimiLogReader:
    """Read assistant replies from Kimi's context.jsonl with incremental parsing."""

    def __init__(self, work_dir: Path):
        self.work_dir = work_dir

    def capture_state(self) -> Dict[str, Any]:
        """Capture the current reading state."""
        context_path, uuid = _resolve_context_jsonl(self.work_dir)
        if not context_path:
            return {
                "context_path": None,
                "session_uuid": None,
                "last_checkpoint": -1,
                "last_text_hash": "",
                "last_pos": 0,
                "last_inode": None,
            }

        messages, file_pos = _parse_new_lines(context_path, 0)
        checkpoint = _latest_checkpoint(messages)
        text = _extract_assistant_text(messages)
        think = _extract_assistant_think(messages)
        try:
            inode = context_path.stat().st_ino
        except OSError:
            inode = None

        return {
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

        Reads only new lines appended since the last known file position.
        Returns (reply_text, new_state).
        """
        prefer_uuid: Optional[str] = state.get("session_uuid")
        context_path, uuid = _resolve_context_jsonl(self.work_dir, prefer_uuid=prefer_uuid)
        if not context_path:
            return None, state

        # Detect file rotation (new session or inode change)
        last_inode = state.get("last_inode")
        try:
            current_inode = context_path.stat().st_ino
        except OSError:
            current_inode = None

        last_pos = state.get("last_pos", 0)
        if current_inode is not None and last_inode is not None and current_inode != last_inode:
            last_pos = 0  # File rotated, read from start

        new_messages, file_pos = _parse_new_lines(context_path, last_pos)
        if not new_messages:
            return None, {
                **state,
                "context_path": str(context_path),
                "session_uuid": uuid,
                "last_pos": file_pos,
                "last_inode": current_inode,
            }

        # Accumulate all messages for checkpoint/text/think extraction
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
