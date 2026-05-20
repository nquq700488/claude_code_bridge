"""
MiniMax prompt wrapping and reply extraction.

Uses non-standard markers (CCB_REQ:, CCB_DONE) deliberately — the pane log
parser strips CCB_REQ_ID: and CCB_DONE: markers, but we need raw text to
pass through so we can do our own completion detection.
"""
from __future__ import annotations

# Deliberately NOT using CCB_REQ_ID:/CCB_DONE: from provider_core.protocol.
# The pane log reader consumes those markers, but mmx's poll loop needs the
# raw CCB_DONE line to detect completion.
REQ_ID_MARKER = "CCB_REQ:"
DONE_MARKER = "CCB_DONE"
MSG_END_MARKER = "CCB_MSG_END"


def wrap_mmx_prompt(message: str, req_id: str, *, caller: str = "claude") -> str:
    """Wrap a user message for mmx-daemon with req_id correlation.

    The first line carries CCB_REQ:<req_id> so the daemon can echo it back.
    The message is terminated by CCB_MSG_END so the daemon knows where
    the multi-line message ends.
    """
    return f"{REQ_ID_MARKER}{req_id}\n{message}\n{MSG_END_MARKER}\n"


def anchor_seen_in_text(text: str, req_id: str) -> bool:
    """Check whether the mmx-daemon has echoed the request anchor."""
    return f"{REQ_ID_MARKER}{req_id}" in text


def extract_reply_for_req(text: str, req_id: str, *, caller: str = "claude") -> tuple[str, bool]:
    """Extract the reply for a given request from mmx-daemon output.

    mmx-daemon outputs:
        CCB_REQ:<req_id>
        <reply text>
        CCB_DONE

    Returns (reply, done_seen). The CCB_REQ echo line is stripped from the
    reply so callers get clean reply text.
    """
    lines = text.splitlines()
    # Find the last CCB_DONE and take everything before it
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == DONE_MARKER:
            # Take lines before CCB_DONE, strip the CCB_REQ echo line
            reply_lines = lines[:i]
            if reply_lines and reply_lines[0].strip().startswith(REQ_ID_MARKER):
                reply_lines = reply_lines[1:]
            reply = "\n".join(reply_lines).strip()
            return reply, True
    return text.strip(), False


__all__ = ["anchor_seen_in_text", "extract_reply_for_req", "wrap_mmx_prompt"]
