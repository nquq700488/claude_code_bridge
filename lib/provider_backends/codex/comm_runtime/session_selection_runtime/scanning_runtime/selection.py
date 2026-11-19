from __future__ import annotations

import time
from pathlib import Path

from ...debug import debug_log_reader
from .candidates import bind_preferred_log, candidate_logs

# Codex can fork a live session into a newer rollout file that keeps the same
# session id. Re-scanning for that fork is a directory walk, so bound readers
# check at most this often instead of once per poll.
_BOUND_RESCAN_INTERVAL_S = 2.0


def scan_latest(reader) -> Path | None:
    latest: Path | None = None
    latest_mtime = -1.0
    for path, mtime in candidate_logs(reader):
        if mtime >= latest_mtime:
            latest = path
            latest_mtime = mtime
    return latest


def latest_log(reader) -> Path | None:
    preferred = reader._preferred_log
    if _preferred_is_bound(reader, preferred):
        debug_log_reader(f"Using preferred log (bound): {preferred}")
        return preferred

    if preferred and preferred.exists():
        latest = scan_latest(reader)
        chosen = _select_preferred_or_latest(reader, preferred, latest)
        if chosen is not None:
            return chosen

    debug_log_reader("No valid preferred log, scanning...")
    latest = scan_latest(reader)
    if latest is None:
        return None
    return bind_preferred_log(reader, latest)


def _preferred_is_bound(reader, preferred: Path | None) -> bool:
    if preferred is None or not preferred.exists():
        return False
    from ..state import follow_workspace_sessions

    if not (reader._session_id_filter and not follow_workspace_sessions(reader)):
        return False
    # A bound reader used to freeze on its first file, so a session Codex
    # forked mid-turn stayed invisible: no anchor, no reply, job stuck running.
    now = time.monotonic()
    if now - float(getattr(reader, '_bound_scan_at', 0.0) or 0.0) < _BOUND_RESCAN_INTERVAL_S:
        return True
    reader._bound_scan_at = now
    return not _has_newer_candidate(reader, preferred)


def _has_newer_candidate(reader, preferred: Path) -> bool:
    try:
        preferred_mtime = preferred.stat().st_mtime
    except OSError:
        return False
    for path, mtime in candidate_logs(reader):
        if path != preferred and mtime > preferred_mtime:
            debug_log_reader(f"Bound log has a newer session file: {path}")
            return True
    return False


def _select_preferred_or_latest(reader, preferred: Path, latest: Path | None) -> Path | None:
    if latest is None or latest == preferred:
        debug_log_reader(f"Using preferred log: {preferred}")
        return preferred
    try:
        preferred_mtime = preferred.stat().st_mtime
        latest_mtime = latest.stat().st_mtime
        if latest_mtime > preferred_mtime:
            reader._preferred_log = latest
            debug_log_reader(f"Preferred log stale; switching to latest: {latest}")
            return latest
    except OSError:
        reader._preferred_log = latest
        debug_log_reader(f"Preferred log stat failed; switching to latest: {latest}")
        return latest
    debug_log_reader(f"Using preferred log: {preferred}")
    return preferred


__all__ = ["latest_log", "scan_latest"]
