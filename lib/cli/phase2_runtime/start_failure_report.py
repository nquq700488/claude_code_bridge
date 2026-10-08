from __future__ import annotations

from dataclasses import dataclass
import time

from ccbd.system import parse_utc_timestamp

_POLL_INTERVAL_S = 0.25
_MAX_REASON_CHARS = 400

# How a report was tied back to the failing attempt.
_MATCH_RUN_ID = 'run_id'
_MATCH_TIMESTAMP = 'timestamp'


@dataclass(frozen=True)
class StartOutcome:
    """Best-effort verdict read from the daemon-authored startup report."""

    status: str
    reason: str | None
    report_path: str


def resolve_start_outcome(
    context,
    exc,
    *,
    attempt_started_at: str,
    grace_s: float = 0.0,
    poll_interval_s: float = _POLL_INTERVAL_S,
    sleep_fn=time.sleep,
    monotonic_fn=time.monotonic,
) -> StartOutcome:
    """Poll the startup report until this attempt's outcome lands.

    The daemon writes the report only once the start transaction finishes,
    which routinely outlives the client's own RPC timeout (a cold start can
    spend ~60s preparing provider runtimes).  Reading once at failure time
    therefore still sees the *previous* report, so wait for one that provably
    belongs to this attempt rather than reporting a bare transport timeout.

    ``grace_s=0`` degrades to a single read, which keeps the fast-fail paths
    unchanged: when the daemon answered with an error it already wrote the
    report, so the first read hits.

    Never raises.  Anything unusable — absent or malformed report, an
    unattributable one, this project's paths being unreadable — yields
    ``status='unknown'`` so the caller can re-raise the original exception.
    """
    path = _report_path(context)
    deadline = monotonic_fn() + max(0.0, float(grace_s))
    while True:
        report = _load_report(context)
        match = _match_kind(context, report, exc, attempt_started_at=attempt_started_at)
        if match is not None:
            status = str(getattr(report, 'status', '') or '').strip()
            if status == 'failed':
                reason = _truncate(_single_line(getattr(report, 'failure_reason', None)))
                if reason:
                    return StartOutcome('failed', reason, path)
            elif status == 'ok' and match == _MATCH_RUN_ID:
                # This report only proves that the daemon reached its initial
                # startup boundary.  The start RPC still has CLI-side
                # post-processing to complete, so the handler must not treat
                # this as a successful command.
                return StartOutcome('ok', None, path)
        remaining = deadline - monotonic_fn()
        if remaining <= 0:
            return StartOutcome('unknown', None, path)
        sleep_fn(min(poll_interval_s, remaining))


def _report_path(context) -> str:
    try:
        return str(context.paths.ccbd_startup_report_path)
    except Exception:
        return ''


def _load_report(context):
    try:
        from ccbd.lifecycle_report_store import CcbdStartupReportStore

        return CcbdStartupReportStore(context.paths).load()
    except Exception:
        # Absent file, malformed/foreign record, unreadable paths -- all of it
        # must fall back to the original exception rather than mask it.
        return None


def _match_kind(context, report, exc, *, attempt_started_at: str) -> str | None:
    if report is None or not _report_belongs_to_project(context, report):
        return None
    report_run_id = str(getattr(report, 'startup_run_id', '') or '').strip()
    if report_run_id:
        # start_command reports are correlated exactly; never attribute another
        # attempt's report to this failure.
        attempt_run_id = str(getattr(exc, 'startup_run_id', '') or '').strip()
        if attempt_run_id and report_run_id == attempt_run_id:
            return _MATCH_RUN_ID
        return None
    # Run-id-less reports are daemon boot reports.  Do not let a later
    # start_command report from another transaction pass the timestamp fallback.
    if str(getattr(report, 'trigger', '') or '').strip() != 'daemon_boot':
        return None
    if _generated_after(report, attempt_started_at):
        return _MATCH_TIMESTAMP
    return None


def _report_belongs_to_project(context, report) -> bool:
    try:
        expected = str(context.project.project_id or '').strip()
        actual = str(getattr(report, 'project_id', '') or '').strip()
    except Exception:
        return False
    return bool(expected and actual and expected == actual)


def _generated_after(report, attempt_started_at: str) -> bool:
    if not attempt_started_at:
        return False
    try:
        generated_at = parse_utc_timestamp(str(getattr(report, 'generated_at', '') or ''))
        return generated_at >= parse_utc_timestamp(attempt_started_at)
    except Exception:
        return False


def _single_line(value) -> str:
    return ' | '.join(line.strip() for line in str(value or '').splitlines() if line.strip())


def _truncate(value: str, limit: int = _MAX_REASON_CHARS) -> str:
    return value if len(value) <= limit else value[: limit - 1].rstrip() + '…'


__all__ = ['StartOutcome', 'resolve_start_outcome']
