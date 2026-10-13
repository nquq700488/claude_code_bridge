from __future__ import annotations

import os
import sys
import time
from functools import partial

from ccbd.socket_client import CcbdClientError

from .agent_health import ensure_agent_running
from .daemon import CcbdServiceError, connect_mounted_daemon
from .watch_runtime import (
    WatchEventBatch,
    default_watch_poll_interval_seconds,
    default_watch_timeout_seconds,
    watch_target as _watch_target_impl,
)

_AUTO_START_DISABLED_VALUES = frozenset({'0', 'false', 'no', 'off'})


def _watch_timeout_seconds() -> float | None:
    raw = os.environ.get('CCB_WATCH_TIMEOUT_S')
    if raw is None or str(raw).strip() == '':
        return default_watch_timeout_seconds()
    timeout = float(str(raw).strip())
    if timeout <= 0:
        return None
    return timeout


def _watch_poll_interval_seconds() -> float:
    return float(os.environ.get('CCB_WATCH_POLL_INTERVAL_S', default_watch_poll_interval_seconds()))


def watch_auto_start_enabled() -> bool:
    """Whether the watch may mount the daemon and start a stopped agent.

    On by default: `ccb pend --watch` is normally run right after `ccb ask`, and
    the target agent may not be up yet.  Set `CCB_WATCH_AUTO_START=0` to keep
    watch a read-only probe that fails fast instead.
    """
    raw = os.environ.get('CCB_WATCH_AUTO_START')
    if raw is None or str(raw).strip() == '':
        return True
    return str(raw).strip().lower() not in _AUTO_START_DISABLED_VALUES


def watch_target(context, command):
    def _resolve_timeout_seconds() -> float:
        explicit = getattr(command, 'timeout_s', None)
        if explicit is not None:
            return float(explicit)
        return _watch_timeout_seconds()

    return _watch_target_impl(
        context,
        command,
        connect_mounted_daemon_fn=connect_mounted_daemon,
        reconnect_error_classes=(CcbdClientError, CcbdServiceError),
        time_fn=time.time,
        sleep_fn=time.sleep,
        timeout_seconds_fn=_resolve_timeout_seconds,
        poll_interval_seconds_fn=_watch_poll_interval_seconds,
        ensure_agent_running_fn=partial(ensure_agent_running, context=context),
        notice_fn=lambda message: print(message, file=sys.stderr, flush=True),
        auto_start_enabled=watch_auto_start_enabled(),
    )


__all__ = ['WatchEventBatch', 'watch_auto_start_enabled', 'watch_target']
