from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WebhookConfig:
    """Webhook configuration parsed from environment variables."""

    url: str | None
    local_sock: str | None
    cmd: str | None
    secret: str | None
    timeout_s: float
    max_retries: int
    events: frozenset[str]
    enabled: bool
    mode: str  # 'http' | 'local_sock' | 'cmd'


def load_webhook_config_from_env() -> WebhookConfig:
    """Load webhook config from environment variables.

    Modes (auto-selected by priority):
      1. CCB_WEBHOOK_URL        -> HTTP POST mode
      2. CCB_WEBHOOK_CMD        -> Local command mode (JSON via stdin)
      3. CCB_WEBHOOK_ENABLED=1  -> Local Unix socket mode (default .ccb/ccbd/webhook.sock)

    Supported env vars:
      CCB_WEBHOOK_ENABLED     – Set to 1 to enable local socket mode when URL/CMD are absent
      CCB_WEBHOOK_URL         – Target URL for HTTP webhook POSTs
      CCB_WEBHOOK_CMD         – Local command to execute (JSON sent via stdin)
      CCB_WEBHOOK_SOCK        – Override local Unix socket path (default: .ccb/ccbd/webhook.sock)
      CCB_WEBHOOK_SECRET      – Optional HMAC secret for HTTP mode
      CCB_WEBHOOK_TIMEOUT_S   – Request timeout in seconds (default: 10)
      CCB_WEBHOOK_MAX_RETRIES – Max retry attempts (default: 3)
                                Also accepts legacy CCB_WEBHOOK_MAX_RETRY
      CCB_WEBHOOK_EVENTS      – Comma-separated event filter; empty = all
    """
    url = (os.environ.get('CCB_WEBHOOK_URL') or '').strip() or None
    cmd = (os.environ.get('CCB_WEBHOOK_CMD') or '').strip() or None

    # Local socket path: default to project-relative .ccb/ccbd/webhook.sock
    raw_sock = (os.environ.get('CCB_WEBHOOK_SOCK') or '').strip()
    if raw_sock:
        local_sock = raw_sock
    else:
        # Try to resolve relative to current working directory (assumed project root)
        local_sock = str(Path('.ccb/ccbd/webhook.sock').resolve())

    enabled_flag = (os.environ.get('CCB_WEBHOOK_ENABLED') or '').strip()
    enabled = bool(url or cmd or enabled_flag in {'1', 'true', 'yes', 'on'})

    if url:
        mode = 'http'
    elif cmd:
        mode = 'cmd'
    elif enabled:
        mode = 'local_sock'
    else:
        mode = 'disabled'

    secret = (os.environ.get('CCB_WEBHOOK_SECRET') or '').strip() or None

    raw_timeout = (os.environ.get('CCB_WEBHOOK_TIMEOUT_S') or '').strip()
    try:
        timeout_s = max(1.0, float(raw_timeout)) if raw_timeout else 10.0
    except ValueError:
        timeout_s = 10.0

    # Prefer CCB_WEBHOOK_MAX_RETRIES, fall back to legacy CCB_WEBHOOK_MAX_RETRY
    raw_retries = (os.environ.get('CCB_WEBHOOK_MAX_RETRIES') or '').strip()
    if not raw_retries:
        raw_retries = (os.environ.get('CCB_WEBHOOK_MAX_RETRY') or '').strip()
    try:
        max_retries = max(0, int(raw_retries)) if raw_retries else 3
    except ValueError:
        max_retries = 3

    raw_events = (os.environ.get('CCB_WEBHOOK_EVENTS') or '').strip()
    if raw_events:
        events = frozenset(e.strip() for e in raw_events.split(',') if e.strip())
    else:
        events = frozenset()  # empty means all events

    return WebhookConfig(
        url=url,
        local_sock=local_sock if mode == 'local_sock' else None,
        cmd=cmd,
        secret=secret,
        timeout_s=timeout_s,
        max_retries=max_retries,
        events=events,
        enabled=enabled,
        mode=mode,
    )
