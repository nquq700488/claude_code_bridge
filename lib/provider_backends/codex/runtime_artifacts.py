from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from storage.path_helpers import SocketPlacement, choose_socket_placement


@dataclass(frozen=True)
class CodexRuntimeArtifacts:
    runtime_dir: Path
    input_fifo: Path
    output_fifo: Path
    bridge_socket: Path
    completion_dir: Path
    history_dir: Path
    history_file: Path
    bridge_log: Path
    bridge_stdout_log: Path
    bridge_stderr_log: Path
    bridge_pid: Path
    codex_pid: Path
    app_server_socket_placement: SocketPlacement
    app_server_socket: Path
    app_server_pid: Path
    app_server_stdout_log: Path
    app_server_stderr_log: Path
    app_server_remote_marker: Path


def _bridge_socket_path(runtime_dir: Path) -> Path:
    """Return a Unix-domain socket path that fits platform limits.

    macOS limits AF_UNIX paths to 104 bytes (including null terminator).
    When the default path under ``runtime_dir`` would exceed that, fall
    back to a short path in ``/tmp`` keyed by a hash of ``runtime_dir``.
    """
    runtime_dir = Path(runtime_dir)
    default_path = runtime_dir / 'bridge.sock'
    # Leave a few bytes of headroom for the null terminator and safety.
    if len(str(default_path)) <= 100:
        return default_path
    import hashlib
    short_hash = hashlib.sha256(str(runtime_dir).encode()).hexdigest()[:16]
    return Path(f'/tmp/ccb-codex-{short_hash}.sock')


def codex_runtime_artifact_layout(runtime_dir: Path) -> CodexRuntimeArtifacts:
    runtime_dir = Path(runtime_dir)
    socket_placement = codex_app_server_socket_placement(runtime_dir)
    return CodexRuntimeArtifacts(
        runtime_dir=runtime_dir,
        input_fifo=runtime_dir / 'input.fifo',
        output_fifo=runtime_dir / 'output.fifo',
        bridge_socket=_bridge_socket_path(runtime_dir),
        completion_dir=runtime_dir / 'completion',
        history_dir=runtime_dir / 'history',
        history_file=runtime_dir / 'history' / 'session.jsonl',
        bridge_log=runtime_dir / 'bridge.log',
        bridge_stdout_log=runtime_dir / 'bridge.stdout.log',
        bridge_stderr_log=runtime_dir / 'bridge.stderr.log',
        bridge_pid=runtime_dir / 'bridge.pid',
        codex_pid=runtime_dir / 'codex.pid',
        app_server_socket_placement=socket_placement,
        app_server_socket=socket_placement.effective_path,
        app_server_pid=runtime_dir / 'app-server.pid',
        app_server_stdout_log=runtime_dir / 'app-server.stdout.log',
        app_server_stderr_log=runtime_dir / 'app-server.stderr.log',
        app_server_remote_marker=runtime_dir / 'app-server.remote',
    )


def codex_app_server_socket_placement(runtime_dir: Path) -> SocketPlacement:
    runtime_path = Path(runtime_dir).expanduser()
    socket_key = hashlib.sha256(str(runtime_path.absolute()).encode('utf-8')).hexdigest()[:16]
    return choose_socket_placement(
        preferred_path=runtime_path / 'app-server.sock',
        project_socket_key=socket_key,
        preferred_root_kind='runtime',
    )


def ensure_runtime_artifact_layout(runtime_dir: Path) -> CodexRuntimeArtifacts:
    artifacts = codex_runtime_artifact_layout(runtime_dir)
    artifacts.runtime_dir.mkdir(parents=True, exist_ok=True)
    artifacts.completion_dir.mkdir(parents=True, exist_ok=True)
    artifacts.history_dir.mkdir(parents=True, exist_ok=True)
    _touch_file(artifacts.bridge_log)
    return artifacts


def cleanup_codex_app_server_shutdown_artifacts(runtime_dir: Path) -> tuple[Path, ...]:
    """Remove exact app-server authority artifacts after provider processes stop."""
    artifacts = codex_runtime_artifact_layout(runtime_dir)
    removed: list[Path] = []
    for path in (artifacts.app_server_pid, artifacts.app_server_remote_marker):
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        except OSError:
            continue
        removed.append(path)
    try:
        if artifacts.app_server_socket.is_socket():
            artifacts.app_server_socket.unlink()
            removed.append(artifacts.app_server_socket)
    except (FileNotFoundError, OSError):
        pass
    return tuple(removed)


def _touch_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8'):
        pass


__all__ = [
    'CodexRuntimeArtifacts',
    'cleanup_codex_app_server_shutdown_artifacts',
    'codex_app_server_socket_placement',
    'codex_runtime_artifact_layout',
    'ensure_runtime_artifact_layout',
]
