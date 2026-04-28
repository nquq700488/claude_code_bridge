from __future__ import annotations

from dataclasses import dataclass

from provider_core.protocol import (
    REQ_ID_PREFIX,
    make_req_id,
)

from .protocol_runtime import extract_reply_for_req, wrap_kimi_prompt


@dataclass(frozen=True)
class KimiRequest:
    client_id: str
    work_dir: str
    timeout_s: float
    quiet: bool
    message: str
    req_id: str | None = None
    caller: str = "claude"


@dataclass(frozen=True)
class KimiResult:
    exit_code: int
    reply: str
    req_id: str
    session_key: str
    done_seen: bool
    done_ms: int | None = None
    anchor_seen: bool = False
    fallback_scan: bool = False
    anchor_ms: int | None = None


__all__ = [
    "KimiRequest",
    "KimiResult",
    "extract_reply_for_req",
    "wrap_kimi_prompt",
]
