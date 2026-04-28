from __future__ import annotations

from provider_backends.pane_log_support import PaneLogCommunicatorBase, PaneLogReaderBase


class MmxLogReader(PaneLogReaderBase):
    poll_env_var = 'MMX_POLL_INTERVAL'


class MmxCommunicator(PaneLogCommunicatorBase):
    provider_key = 'mmx'
    provider_label = 'MiniMax'
    session_filename = '.mmx-session'
    sync_timeout_env = 'MMX_SYNC_TIMEOUT'
    missing_session_message = (
        "No active mmx session found. "
        "Run 'ccb mmx' (or add mmx to ccb.config) first"
    )
    unhealthy_message = (
        "Session unhealthy: {status}\n"
        "Hint: run ccb mmx (or add mmx to ccb.config) to start a new session"
    )
    reader_cls = MmxLogReader


__all__ = ['MmxCommunicator', 'MmxLogReader']
