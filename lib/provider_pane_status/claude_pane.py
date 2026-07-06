from __future__ import annotations

from dataclasses import dataclass
import re


ACTIVE_STATES = frozenset({"working", "tool_running"})
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
CLAUDE_TOOL_RUNNING_RE = re.compile(
    r"^\s*●\s*thinking\s+for\s+(?:\d+\s*h\s*)?(?:\d+\s*m\s*)?\d+\s*s,\s+running\s+\d+\s+shell\s+commands?\b",
    re.IGNORECASE,
)
CLAUDE_SPINNER_RE = re.compile(
    r"^\s*[✢✳✶✽]\s+.+\((?:\d+\s*h\s*)?(?:\d+\s*m\s*)?\d+\s*s\b.*(?:tokens?|thought)",
    re.IGNORECASE,
)
CLAUDE_THOUGHT_RAN_RE = re.compile(
    r"^\s*thought\s+for\s+(?:\d+\s*h\s*)?(?:\d+\s*m\s*)?\d+\s*s,\s+ran\s+\d+\s+shell\s+commands?\b",
    re.IGNORECASE,
)
CLAUDE_VERB_FOR_RE = re.compile(
    r"^\s*[✻✽]\s+\S+\s+for\s+(?:\d+\s*h\s*)?(?:\d+\s*m\s*)?\d+\s*s\b",
    re.IGNORECASE,
)
SCHEDULED_TASK_MARKERS = (
    "running scheduled task",
    "shell still running",
    "shells still running",
)
WAITING_MARKERS = (
    "permission required",
    "requires permission",
    "approval required",
    "waiting for permission",
    "waiting for approval",
    "do you want to proceed",
)
API_ERROR_MARKERS = (
    "api error",
    "rate limit",
    "rate_limit",
    "too many requests",
    "overloaded",
    "model_not_found",
    "model unavailable",
    "request failed",
)
ERROR_MARKERS = (
    "error:",
    "failed",
    "connection refused",
    "connection reset",
    "connection timed out",
)
STATUS_CATALOG: dict[str, str] = {
    "working": "Claude pane shows visible model/runtime activity.",
    "tool_running": "Claude pane shows a shell/tool/scheduled task is running.",
    "terminal_summary": "Claude pane shows a past-tense turn summary; this is not completion authority.",
    "waiting_for_user": "Claude pane shows an explicit permission or approval wait.",
    "api_error": "Claude pane shows provider/API/model/rate-limit failure text.",
    "failed": "Claude pane shows generic visible provider/runtime failure text.",
    "pane_dead": "The tmux pane or server is gone.",
    "unknown": "Pane evidence is empty, contradictory, or not yet classified.",
}


@dataclass(frozen=True)
class ClaudePaneStatus:
    state: str
    reason: str
    matched_patterns: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            "state": self.state,
            "reason": self.reason,
            "matched_patterns": list(self.matched_patterns),
            "notes": list(self.notes),
        }


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text or "")


def normalize_screen(text: str) -> str:
    cleaned = strip_ansi(text).replace("\r", "\n").replace("\xa0", " ")
    lines = [line.rstrip() for line in cleaned.splitlines()]
    return "\n".join(lines)


def parse_claude_pane_status(
    pane_text: str | None,
    *,
    pane_dead: bool = False,
) -> ClaudePaneStatus:
    """Classify visible Claude pane text using explicit tail evidence only."""
    if pane_dead:
        return ClaudePaneStatus("pane_dead", "pane_dead", ("pane_dead",))

    normalized = normalize_screen(pane_text or "")
    recent_lines = [line.rstrip() for line in normalized.splitlines() if line.strip()]
    recent = " ".join(line.strip() for line in recent_lines[-20:]).lower()
    if not recent:
        return ClaudePaneStatus("unknown", "empty_capture")

    if _last_tool_running_index(recent_lines) >= 0:
        return ClaudePaneStatus("tool_running", "claude_pane_tool_running", ("tool_running_line",))

    if _last_spinner_index(recent_lines) >= 0:
        return ClaudePaneStatus("working", "claude_pane_spinner_active", ("spinner_line",))

    matches = _matched(SCHEDULED_TASK_MARKERS, recent)
    if matches:
        return ClaudePaneStatus("tool_running", "claude_pane_scheduled_task_running", matches)

    matches = _matched(WAITING_MARKERS, recent)
    if matches:
        return ClaudePaneStatus("waiting_for_user", "claude_pane_waiting_for_user", matches)

    matches = _matched(API_ERROR_MARKERS, recent)
    if matches:
        return ClaudePaneStatus("api_error", "provider_api_error", matches)

    matches = _matched(ERROR_MARKERS, recent)
    if matches:
        return ClaudePaneStatus("failed", "provider_error_text", matches)

    if _last_terminal_summary_index(recent_lines) >= 0:
        return ClaudePaneStatus(
            "terminal_summary",
            "claude_pane_terminal_summary",
            ("terminal_summary",),
            ("not_completion_authority",),
        )

    return ClaudePaneStatus("unknown", "no_known_status_pattern")


def _last_tool_running_index(lines: list[str]) -> int:
    for index in range(len(lines) - 1, -1, -1):
        if CLAUDE_TOOL_RUNNING_RE.search(lines[index]):
            return index
    return -1


def _last_spinner_index(lines: list[str]) -> int:
    for index in range(len(lines) - 1, -1, -1):
        if CLAUDE_SPINNER_RE.search(lines[index]):
            return index
    return -1


def _last_terminal_summary_index(lines: list[str]) -> int:
    for index in range(len(lines) - 1, -1, -1):
        line = lines[index]
        if CLAUDE_THOUGHT_RAN_RE.search(line) or CLAUDE_VERB_FOR_RE.search(line):
            return index
    return -1


def _matched(markers: tuple[str, ...], text: str) -> tuple[str, ...]:
    return tuple(marker for marker in markers if marker in text)


__all__ = [
    "ACTIVE_STATES",
    "ClaudePaneStatus",
    "STATUS_CATALOG",
    "normalize_screen",
    "parse_claude_pane_status",
    "strip_ansi",
]
