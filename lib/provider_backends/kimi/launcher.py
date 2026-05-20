from __future__ import annotations

import os
import platform
import shlex
from pathlib import Path

from agents.models import AgentSpec
from cli.context import CliContext
from cli.models import ParsedStartCommand
from provider_core.contracts import ProviderRuntimeLauncher
from provider_core.runtime_shared import provider_start_parts
from workspace.models import WorkspacePlan


def _resolve_kimi_executable() -> str:
    """Find the Kimi CLI executable.

    Resolution order:
    1. KIMI_START_CMD environment variable
    2. 'kimi' on PATH
    3. VS Code extension bundled binary (macOS / Linux)
    4. Fallback to 'kimi'
    """
    env_cmd = os.environ.get('KIMI_START_CMD', '').strip()
    if env_cmd:
        return env_cmd

    # PATH lookup
    for path_dir in os.environ.get('PATH', '').split(os.pathsep):
        candidate = Path(path_dir) / 'kimi'
        if candidate.exists() and candidate.is_file():
            return str(candidate)

    # VS Code extension path (macOS)
    if platform.system() == 'Darwin':
        vscode_path = Path.home() / (
            "Library/Application Support/Code/User/globalStorage/"
            "moonshot-ai.kimi-code/bin/kimi/kimi"
        )
        if vscode_path.exists():
            return str(vscode_path)

    # VS Code extension path (Linux)
    if platform.system() == 'Linux':
        vscode_path = Path.home() / (
            ".config/Code/User/globalStorage/"
            "moonshot-ai.kimi-code/bin/kimi/kimi"
        )
        if vscode_path.exists():
            return str(vscode_path)

    # uv / pipx typical install path
    local_bin = Path.home() / '.local/bin/kimi'
    if local_bin.exists():
        return str(local_bin)

    return 'kimi'


def build_runtime_launcher() -> ProviderRuntimeLauncher:
    return ProviderRuntimeLauncher(
        provider='kimi',
        launch_mode='simple_tmux',
        build_start_cmd=build_start_cmd,
        build_session_payload=build_session_payload,
    )


def build_start_cmd(command: ParsedStartCommand, spec: AgentSpec, runtime_dir: Path, launch_session_id: str, *, prepared_state: dict[str, object] | None = None) -> str:
    cmd_parts = provider_start_parts('kimi')
    # When no custom start command is set, resolve the full path to the kimi
    # executable (checking PATH and known install locations).
    has_custom_cmd = bool(os.environ.get('KIMI_START_CMD', '').strip())
    if not has_custom_cmd and cmd_parts and cmd_parts[0] == 'kimi':
        resolved = _resolve_kimi_executable()
        cmd_parts = [resolved] + cmd_parts[1:]

    if command.restore:
        cmd_parts.append('--continue')

    cmd_parts.extend(spec.startup_args)
    cmd = ' '.join(shlex.quote(str(part)) for part in cmd_parts)

    # Export runtime env so Kimi can locate CCB context if needed
    env_prefix = ''
    if runtime_dir:
        env_prefix = f'export KIMI_RUNTIME_DIR={shlex.quote(str(runtime_dir))}'

    if env_prefix:
        return f'{env_prefix}; {cmd}'
    return cmd


def build_session_payload(
    context: CliContext,
    spec: AgentSpec,
    plan: WorkspacePlan,
    runtime_dir: Path,
    run_cwd: Path,
    pane_id: str,
    pane_title_marker: str,
    start_cmd: str,
    launch_session_id: str,
    prepared_state: dict[str, object],
) -> dict[str, object]:
    del prepared_state
    return {
        'ccb_session_id': launch_session_id,
        'agent_name': spec.name,
        'ccb_project_id': context.project.project_id,
        'runtime_dir': str(runtime_dir),
        'terminal': 'tmux',
        'tmux_session': pane_id,
        'pane_id': pane_id,
        'pane_title_marker': pane_title_marker,
        'workspace_path': str(plan.workspace_path),
        'work_dir': str(run_cwd),
        'start_dir': str(context.project.project_root),
        'kimi_start_cmd': start_cmd,
        'start_cmd': start_cmd,
    }


__all__ = ['build_runtime_launcher', 'build_start_cmd']
