from __future__ import annotations

from pathlib import Path
import os

from ccbd.api_models import RpcRequest
from .socket_client_runtime import (
    CcbdClientError,
    bind_endpoint,
    client_endpoints,
    connect_socket,
    decode_response,
    recv_response_line,
    send_request,
)


class CcbdClient:
    def __init__(self, socket_path: str | Path, *, timeout_s: float | None = None) -> None:
        self._socket_path = Path(socket_path)
        self._timeout_s = _resolve_timeout(timeout_s)

    def with_timeout(self, timeout_s: float | None) -> "CcbdClient":
        return type(self)(self._socket_path, timeout_s=timeout_s)

    def request(self, op: str, payload: dict | None = None) -> dict:
        req = RpcRequest(op=op, request=payload or {})
        try:
            sock = connect_socket(self._socket_path, timeout_s=self._timeout_s)
        except CcbdClientError as exc:
            # connect_socket normally wraps its own OSError/TimeoutError before
            # it returns here, so annotate that path explicitly as pre-send.
            _set_rpc_phase(exc, 'connect')
            raise
        except OSError as exc:
            error = _client_error(str(exc), phase='connect')
            raise error from exc
        try:
            try:
                send_request(sock, req)
            except OSError as exc:
                error = _client_error(str(exc), phase='send')
                raise error from exc
            try:
                raw = recv_response_line(sock)
            except OSError as exc:
                error = _client_error(str(exc), phase='receive')
                raise error from exc
        finally:
            sock.close()
        if not raw:
            raise _client_error('empty response from ccbd', phase='receive')
        response = decode_response(raw)
        if not response.ok:
            raise _client_error(response.error or 'ccbd request failed', phase='response')
        return response.payload

    def __getattr__(self, name: str):
        endpoint = client_endpoints.get(name)
        if endpoint is None:
            raise AttributeError(name)
        call = bind_endpoint(self, name=name, endpoint=endpoint)
        object.__setattr__(self, name, call)
        return call


def _client_error(message: str, *, phase: str) -> CcbdClientError:
    error = CcbdClientError(message)
    _set_rpc_phase(error, phase)
    return error


def _set_rpc_phase(error: BaseException, phase: str) -> None:
    try:
        if not getattr(error, 'ccb_rpc_phase', None):
            error.ccb_rpc_phase = phase  # type: ignore[attr-defined]
    except Exception:
        pass


def _resolve_timeout(explicit: float | None) -> float:
    if explicit is not None:
        try:
            return max(0.1, float(explicit))
        except Exception:
            return 3.0
    for env_name in ('CCB_CCBD_CLIENT_TIMEOUT_S',):
        raw = os.environ.get(env_name)
        if not raw:
            continue
        try:
            return max(0.1, float(raw))
        except Exception:
            continue
    return 3.0


__all__ = ['CcbdClient', 'CcbdClientError']
