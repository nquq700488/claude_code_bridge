"""
Kimi communication module.

Reads replies from Kimi session storage (~/.kimi/sessions/<hash>/<uuid>/context.jsonl)
and sends messages by injecting text into the Kimi TUI pane via tmux.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


KIMI_SESSIONS_ROOT = Path.home() / ".kimi" / "sessions"


def _work_dir_hash(work_dir: Path) -> str:
    """Compute Kimi's work-dir hash (MD5 of absolute path string)."""
    normalized = str(work_dir.resolve())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def _find_latest_session_uuid(session_dir: Path) -> Optional[str]:
    """Find the most recently modified session subdirectory."""
    if not session_dir.exists():
        return None
    candidates = []
    for entry in session_dir.iterdir():
        if entry.is_dir():
            try:
                mtime = entry.stat().st_mtime
                candidates.append((mtime, entry.name))
            except OSError:
                continue
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _resolve_context_jsonl(work_dir: Path) -> Optional[Path]:
    """Resolve the path to Kimi's context.jsonl for a given work_dir."""
    h = _work_dir_hash(work_dir)
    session_dir = KIMI_SESSIONS_ROOT / h
    uuid = _find_latest_session_uuid(session_dir)
    if not uuid:
        return None
    context_path = session_dir / uuid / "context.jsonl"
    if context_path.exists():
        return context_path
    return None


def _parse_context_lines(path: Path) -> list[dict]:
    """Parse context.jsonl into a list of JSON objects."""
    lines: list[dict] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        lines.append(obj)
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return lines


def _extract_assistant_text(messages: list[dict]) -> Optional[str]:
    """Extract human-readable text from the latest assistant message."""
    for msg in reversed(messages):
        role = msg.get("role")
        if role != "assistant":
            continue
        content = msg.get("content")
        if not content:
            # Could be assistant with only tool_calls and no content
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
    """Read assistant replies from Kimi's context.jsonl."""

    def __init__(self, work_dir: Path):
        self.work_dir = work_dir

    def capture_state(self) -> Dict[str, Any]:
        """Capture the current reading state."""
        context_path = _resolve_context_jsonl(self.work_dir)
        if not context_path:
            return {"context_path": None, "last_checkpoint": -1, "last_text_hash": ""}

        messages = _parse_context_lines(context_path)
        checkpoint = _latest_checkpoint(messages)
        text = _extract_assistant_text(messages)
        return {
            "context_path": str(context_path),
            "last_checkpoint": checkpoint,
            "last_text_hash": hashlib.sha256((text or "").encode()).hexdigest() if text else "",
        }

    def try_get_message(self, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        """Try to read a new assistant message since the given state.

        Returns (reply_text, new_state).  If no new complete reply is available,
        returns (None, state).
        """
        context_path = _resolve_context_jsonl(self.work_dir)
        if not context_path:
            return None, state

        messages = _parse_context_lines(context_path)
        checkpoint = _latest_checkpoint(messages)
        last_checkpoint = state.get("last_checkpoint", -1)

        # If no new checkpoint, assume no new complete turn
        if checkpoint <= last_checkpoint:
            return None, state

        text = _extract_assistant_text(messages)
        if not text:
            return None, state

        text_hash = hashlib.sha256(text.encode()).hexdigest()
        if text_hash == state.get("last_text_hash"):
            return None, state

        new_state = {
            "context_path": str(context_path),
            "last_checkpoint": checkpoint,
            "last_text_hash": text_hash,
        }
        return text, new_state


class KimiCommunicator:
    """Facade for Kimi pane communication (not used directly by execution adapter)."""

    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self.reader = KimiLogReader(work_dir=work_dir)


__all__ = ["KimiCommunicator", "KimiLogReader", "KIMI_SESSIONS_ROOT"]
