from __future__ import annotations

from cli.context import CliContext
from cli.models import ParsedRestartCommand

from .daemon import invoke_mounted_daemon


def restart_agent(context: CliContext, command: ParsedRestartCommand) -> dict:
    return invoke_mounted_daemon(
        context,
        allow_restart_stale=False,
        request_fn=lambda client: client.project_restart_panes(command.agent_names),
    )


__all__ = ['restart_agent']
