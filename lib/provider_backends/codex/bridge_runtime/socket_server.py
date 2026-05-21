from __future__ import annotations

import json
import os
import socket
import threading
from pathlib import Path
from typing import Any, Callable


def start_bridge_socket_server(
    socket_path: Path,
    *,
    process_request_fn: Callable[[dict[str, Any]], None],
    log_fn: Callable[[str], None],
) -> "BridgeSocketServer":
    """Start a background Unix Domain Socket server for the Codex bridge.

    The server runs in a daemon thread and feeds received requests into the
    same ``process_request_fn`` used by the FIFO path.
    """
    server = BridgeSocketServer(socket_path, process_request_fn=process_request_fn, log_fn=log_fn)
    server.start()
    return server


class BridgeSocketServer:
    def __init__(
        self,
        socket_path: Path,
        *,
        process_request_fn: Callable[[dict[str, Any]], None],
        log_fn: Callable[[str], None],
    ) -> None:
        self._socket_path = Path(socket_path)
        self._process_request = process_request_fn
        self._log = log_fn
        self._server_sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._request_lock = threading.Lock()
        self._handler_semaphore = threading.BoundedSemaphore(16)

    def start(self) -> None:
        if not hasattr(socket, "AF_UNIX"):
            self._log("Unix domain sockets not supported on this platform, skipping socket server")
            return

        # Clean up stale socket file
        if self._socket_path.exists():
            try:
                self._socket_path.unlink()
            except OSError as exc:
                self._log(f"Failed to remove stale socket file: {exc}")
                return

        try:
            self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._server_sock.bind(str(self._socket_path))
            self._server_sock.listen(128)
        except OSError as exc:
            self._log(f"Failed to bind bridge socket: {exc}")
            return

        self._running = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        self._log(f"Bridge socket server listening on {self._socket_path}")

    def stop(self) -> None:
        self._running = False
        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except OSError:
                pass
            self._server_sock = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._socket_path.exists():
            try:
                self._socket_path.unlink()
            except OSError:
                pass

    def _serve(self) -> None:
        sock = self._server_sock
        while self._running and sock is not None:
            try:
                sock.settimeout(1.0)
                conn, _ = sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            # Handle each connection in its own thread so the accept loop
            # never blocks on slow clients.
            handler = threading.Thread(target=self._handle_connection, args=(conn,), daemon=True)
            handler.start()

    def _handle_connection(self, conn: socket.socket) -> None:
        with self._handler_semaphore:
            try:
                with conn:
                    conn.settimeout(10.0)
                    raw = b""
                    while b"\n" not in raw:
                        chunk = conn.recv(65536)
                        if not chunk:
                            break
                        raw += chunk

                    if not raw:
                        return

                    try:
                        line = raw.split(b"\n", 1)[0].decode("utf-8")
                        payload = json.loads(line)
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        self._log(f"Bridge socket received invalid JSON: {exc}")
                        conn.sendall(b'{"status":"error","reason":"invalid_json"}\n')
                        return

                    try:
                        with self._request_lock:
                            self._process_request(payload)
                        conn.sendall(b'{"status":"ok"}\n')
                    except Exception as exc:
                        self._log(f"Bridge socket request processing failed: {exc}")
                        conn.sendall(b'{"status":"error","reason":"processing_failed"}\n')
            except socket.timeout:
                self._log("Bridge socket client timed out")
            except Exception as exc:
                self._log(f"Bridge socket connection error: {exc}")


__all__ = ["start_bridge_socket_server", "BridgeSocketServer"]
