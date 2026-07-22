from __future__ import annotations

from pathlib import Path

from agents.config_loader import load_project_config


def team_list(context, command) -> dict:
    root = _project_root(context)
    config = load_project_config(root, include_loop_overlays=False).config
    teams = {}
    for name, spec in config.teams.items():
        teams[name] = {
            'topology': spec.topology,
            'member_count': len(spec.members),
            'description': spec.description,
        }
    return {'teams': teams}


def team_up(context, command) -> dict:
    return {'team': getattr(command, 'team_name', ''), 'members': [], 'error': 'not yet implemented (Task 5)'}


def team_down(context, command) -> dict:
    return {'team': getattr(command, 'team_name', ''), 'parked': True}


def team_status(context, command) -> dict:
    return {'team': getattr(command, 'team_name', ''), 'status': 'not_up', 'members': [], 'definition_changed': False}


def _project_root(context) -> Path:
    direct = getattr(context, 'project_root', None)
    if direct is not None:
        return Path(direct)
    paths = getattr(context, 'paths', None)
    if paths is not None and getattr(paths, 'project_root', None) is not None:
        return Path(paths.project_root)
    return Path(context.project.project_root)


__all__ = ['team_list', 'team_up', 'team_down', 'team_status']
