"""
Kimi prompt wrapping and reply extraction.
"""
from __future__ import annotations

from provider_core.protocol import (
    is_done_text,
    strip_done_text,
)


def wrap_kimi_prompt(message: str, req_id: str, *, caller: str = "claude") -> str:
    """Wrap a user message for Kimi CLI.

    Kimi CLI receives plain text via tmux send-keys.
    We inject the req_id anchor so the reply can be correlated.
    """
    message = (message or "").rstrip()
    return f"{req_id}\n\n{message}\n"


def extract_reply_for_req(text: str, req_id: str, *, caller: str = "claude") -> tuple[str, bool]:
    """Extract the reply for a given request from Kimi output.

    For Kimi, the reply comes from context.jsonl structured data,
    so this is mainly a pass-through with done-marker cleanup.
    Returns (reply, done_seen).
    """
    cleaned = strip_done_text(text, req_id) if req_id else text
    if req_id and is_done_text(text, req_id):
        return cleaned.strip(), True
    return cleaned.strip(), False


__all__ = ["extract_reply_for_req", "wrap_kimi_prompt"]
