from __future__ import annotations

import json
import os
import socket
from datetime import datetime
from typing import Any

from .common import ensure_session_health, remember_log_hint


# How long to wait for a socket connection/write before falling back to FIFO.
_SOCKET_CONNECT_TIMEOUT_S = 5.0
_SOCKET_ACK_TIMEOUT_S = 2.0


def send_message(comm, content: str) -> tuple[str, dict[str, Any]]:
    marker = comm._generate_marker()
    message = {
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "marker": marker,
    }

    state = comm.log_reader.capture_state()

    # Dual-track delivery: prefer Unix Domain Socket, fallback to FIFO.
    if _try_send_via_socket(comm, message):
        return marker, state

    # Fallback to legacy FIFO path for backwards compatibility.
    _send_via_fifo(comm, message)
    return marker, state


def _try_send_via_socket(comm, message: dict[str, Any]) -> bool:
    """Attempt to send message via Unix Domain Socket.

    Returns True on success, False if socket is unavailable so caller can
    fallback to FIFO.
    """
    sock_path = getattr(comm, "bridge_socket", None)
    if sock_path is None:
        return False

    payload = json.dumps(message, ensure_ascii=False) + "\n"
    try:
        payload_bytes = payload.encode("utf-8", errors="replace")
    except UnicodeEncodeError:
        payload_bytes = payload.encode("utf-8", errors="replace")

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(_SOCKET_CONNECT_TIMEOUT_S)
            sock.connect(str(sock_path))
            sock.sendall(payload_bytes)
            # Wait for a short ACK so we know the bridge actually received it.
            sock.settimeout(_SOCKET_ACK_TIMEOUT_S)
            ack = sock.recv(1024)
            if ack:
                try:
                    ack_data = json.loads(ack.decode())
                    return ack_data.get("status") == "ok"
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return False
            # Empty ACK is treated as success (older bridge versions).
            return True
    except (OSError, socket.timeout, ConnectionRefusedError):
        # Socket not available or bridge not listening — caller will fallback.
        return False


def _send_via_fifo(comm, message: dict[str, Any]) -> None:
    """Legacy FIFO delivery path."""
    payload = json.dumps(message, ensure_ascii=False) + "\n"
    with open(comm.input_fifo, "w", encoding="utf-8") as fifo:
        fifo.write(payload)
        fifo.flush()


def ask_async(comm, question: str) -> bool:
    try:
        ensure_session_health(comm)
        marker, state = comm._send_message(question)
        remember_log_hint(comm, state)
        print(f"✅ Sent to Codex (marker: {marker[:12]}...)")
        print("Hint: `ccb pend <agent|job_id>` is only a supplementary observer view, not an authoritative completion path")
        return True
    except Exception as exc:
        print(f"❌ Send failed: {exc}")
        return False


__all__ = ["ask_async", "send_message"]
