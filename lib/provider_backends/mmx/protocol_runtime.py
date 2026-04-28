"""
MiniMax prompt wrapping and reply extraction.
Simplified version without skills injection.
"""
from __future__ import annotations


def wrap_mmx_prompt(message: str, req_id: str, *, caller: str = "claude") -> str:
    """Wrap a user message for mmx-daemon.

    mmx-daemon expects plain text lines; req_id is passed through
    so that the reply can be correlated.
    """
    # mmx-daemon reads lines from stdin directly;
    # we just pass the message as-is.
    return f"{message}\n"


def extract_reply_for_req(text: str, req_id: str, *, caller: str = "claude") -> tuple[str, bool]:
    """Extract the reply for a given request from mmx-daemon output.

    mmx-daemon outputs:
        <reply text>
        CCB_DONE

    Returns (reply, done_seen).
    """
    lines = text.splitlines()
    # Find the last CCB_DONE and take everything before it
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == "CCB_DONE":
            reply = "\n".join(lines[:i]).strip()
            return reply, True
    # No CCB_DONE found — return whatever we have
    return text.strip(), False
