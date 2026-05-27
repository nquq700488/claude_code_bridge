from __future__ import annotations

import hashlib
import hmac
import json
import queue
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from typing import Any

from .config import WebhookConfig


class WebhookSender:
    """Webhook sender with a bounded worker queue, dedupe, and graceful close.

    Supports three delivery modes:
      - http:        POST to CCB_WEBHOOK_URL
      - cmd:         Execute CCB_WEBHOOK_CMD with JSON via stdin
      - local_sock:  Connect to local Unix socket (default .ccb/ccbd/webhook.sock)

    Guarantees:
    - After close() returns, no new events are accepted.
    - close() waits up to flush_timeout_s for queued events to be processed.
    - Events submitted after close() begins are dropped.

    Limitations:
    - close() is deadline-limited best-effort; in-flight deliveries that
      exceed the deadline may still be running when close() returns.
    """

    def __init__(self, config: WebhookConfig) -> None:
        self._config = config
        self._queue: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=256)
        self._worker: threading.Thread | None = None
        self._shutdown = False
        self._lock = threading.Lock()
        # Dedupe cache: {(event_type, agent_name, health): timestamp}
        self._dedupe: dict[tuple[str, str, str], float] = {}
        self._dedupe_lock = threading.Lock()
        self._dedupe_ttl_s = 5.0

    def send(self, event_type: str, payload: dict[str, Any]) -> None:
        """Enqueue a webhook event for async delivery."""
        if not self._config.enabled:
            return
        if self._config.events and event_type not in self._config.events:
            return

        # Dedupe for agent.recovered / agent.degraded
        if event_type in ('agent.recovered', 'agent.degraded'):
            agent_name = str(payload.get('agent_name') or '').strip()
            health = str(payload.get('health') or '').strip()
            if agent_name and health:
                key = (event_type, agent_name, health)
                now = time.monotonic()
                with self._dedupe_lock:
                    last = self._dedupe.get(key)
                    if last is not None and now - last < self._dedupe_ttl_s:
                        return
                    self._dedupe[key] = now
                    # prune old entries
                    cutoff = now - self._dedupe_ttl_s
                    self._dedupe = {k: v for k, v in self._dedupe.items() if v > cutoff}

        # Atomically check shutdown and enqueue under _lock to prevent
        # close() from inserting sentinel while we are still enqueueing.
        with self._lock:
            if self._shutdown:
                return
            if self._worker is None:
                self._worker = threading.Thread(target=self._run_worker, daemon=True)
                self._worker.start()
            try:
                self._queue.put_nowait(
                    {
                        "event": event_type,
                        "payload": payload,
                    }
                )
            except queue.Full:
                self._log(f"webhook queue full; dropping event {event_type}")

    def close(self, *, flush_timeout_s: float = 5.0) -> None:
        """Signal the worker to stop and wait for queued events.

        This is deadline-limited best-effort: in-flight deliveries
        that exceed flush_timeout_s may still be running when close()
        returns.
        """
        with self._lock:
            if self._worker is None or self._shutdown:
                return
            self._shutdown = True

        deadline = time.monotonic() + flush_timeout_s
        # Drain queue: wait until empty or deadline, polling every 50ms.
        while time.monotonic() < deadline:
            if self._queue.empty():
                break
            time.sleep(0.05)

        # Insert sentinel (non-blocking; queue should have room after drain)
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            self._log("webhook queue full during close; sentinel dropped")

        # Wait for worker to finish (with remaining deadline)
        if self._worker is not None and self._worker.is_alive():
            remaining = max(0.0, deadline - time.monotonic())
            self._worker.join(timeout=remaining)
        self._worker = None

    def _run_worker(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                self._queue.task_done()
                break
            try:
                self._attempt_deliver(item["event"], item["payload"])
            except Exception as exc:
                self._log(f"webhook delivery error: {exc}")
            finally:
                self._queue.task_done()

    def _attempt_deliver(self, event_type: str, payload: dict[str, Any]) -> None:
        body = json.dumps(
            {
                "event": event_type,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "payload": payload,
            },
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")

        mode = self._config.mode
        if mode == 'http':
            self._deliver_http(body, event_type)
        elif mode == 'cmd':
            self._deliver_cmd(body, event_type)
        elif mode == 'local_sock':
            self._deliver_local_sock(body, event_type)

    def _deliver_http(self, body: bytes, event_type: str) -> None:
        url = self._config.url
        if not url:
            return

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "CCB-Webhook/1.0",
            "X-CCB-Event": event_type,
        }
        if self._config.secret:
            ts = str(int(time.time()))
            signature = _hmac_signature(self._config.secret, body, ts)
            headers["X-CCB-Signature"] = signature
            headers["X-CCB-Signature-Timestamp"] = ts

        last_error: Exception | None = None
        for attempt in range(self._config.max_retries + 1):
            if attempt > 0:
                backoff = min(2 ** attempt, 30)
                self._log(f"webhook retry {attempt}/{self._config.max_retries} for {event_type} in {backoff}s")
                time.sleep(backoff)
            try:
                req = urllib.request.Request(
                    url,
                    data=body,
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self._config.timeout_s) as resp:
                    status = resp.status
                    if 200 <= status < 300:
                        self._log(f"webhook {event_type} delivered ({status})")
                        return
                    if 300 <= status < 400:
                        last_error = urllib.error.HTTPError(url, status, None, None, None)
                        continue
                    if 400 <= status < 500:
                        self._log(f"webhook {event_type} failed with {status} (no retry)")
                        return
                    last_error = urllib.error.HTTPError(url, status, None, None, None)
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code in (400, 401, 403, 404, 422):
                    self._log(f"webhook {event_type} failed with {exc.code} (no retry)")
                    return
            except Exception as exc:
                last_error = exc

        self._log(f"webhook {event_type} exhausted all retries; dropped")

    def _deliver_local_sock(self, body: bytes, event_type: str) -> None:
        """Deliver event via local Unix domain socket.

        Best-effort: if no listener is present, the event is silently dropped.
        This allows local processes to optionally listen on the socket.
        """
        sock_path = self._config.local_sock
        if not sock_path:
            return
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(self._config.timeout_s)
                sock.connect(sock_path)
                sock.sendall(body + b"\n")
                self._log(f"webhook {event_type} delivered to local sock")
        except (FileNotFoundError, ConnectionRefusedError):
            # No listener; silently drop
            pass
        except Exception as exc:
            self._log(f"webhook local_sock error for {event_type}: {exc}")

    def _deliver_cmd(self, body: bytes, event_type: str) -> None:
        """Deliver event by executing a local command with JSON via stdin."""
        cmd = self._config.cmd
        if not cmd:
            return
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                input=body,
                capture_output=True,
                timeout=self._config.timeout_s,
            )
            if result.returncode == 0:
                self._log(f"webhook {event_type} delivered via cmd")
            else:
                stderr = (result.stderr or b'').decode('utf-8', errors='replace')[:200]
                self._log(f"webhook {event_type} cmd failed (rc={result.returncode}): {stderr}")
        except subprocess.TimeoutExpired:
            self._log(f"webhook {event_type} cmd timed out")
        except Exception as exc:
            self._log(f"webhook cmd error for {event_type}: {exc}")

    @staticmethod
    def _log(message: str) -> None:
        # Simple stderr log for operational visibility
        print(f"[CCB-Webhook] {message}", flush=True)


def _hmac_signature(secret: str, body: bytes, timestamp: str) -> str:
    """Generate HMAC-SHA256 signature of timestamp + body."""
    key = secret.encode("utf-8")
    data = f"{timestamp}.".encode("utf-8") + body
    sig = hmac.new(key, data, hashlib.sha256).hexdigest()
    return f"sha256={sig}"
