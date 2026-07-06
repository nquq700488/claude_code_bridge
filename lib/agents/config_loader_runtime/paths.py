from __future__ import annotations

from pathlib import Path

from project.discovery import CCB_DIRNAME

from .common import CONFIG_FILENAME


def project_config_path(project_root: Path) -> Path:
    return Path(project_root).expanduser().resolve() / CCB_DIRNAME / CONFIG_FILENAME


def user_default_config_path() -> Path:
    return Path.home().expanduser().resolve() / CCB_DIRNAME / CONFIG_FILENAME


def resolve_config_profile_path(project_root: Path) -> Path | None:
    """If .ccb/ccb.config has config_profile, return the resolved profile config path.

    Returns None if no profile is configured (no redirect needed — use
    ccb.config directly).

    The profile router is a one-line TOML directive like::

        config_profile = "compact"

    Which resolves to .ccb/ccb-compact.config.

    Profile target files do NOT support nested config_profile (no recursion,
    avoids redirect cycles).
    """
    primary = project_config_path(project_root)
    if not primary.is_file():
        return None
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    try:
        data = tomllib.loads(primary.read_text(encoding='utf-8'))
    except Exception:
        return None
    profile = str(data.get('config_profile') or '').strip()
    if not profile:
        return None
    resolved = primary.parent / f'ccb-{profile}.config'
    if not resolved.is_file():
        raise FileNotFoundError(
            f'Config profile "{profile}" points to {resolved}, but that file does not exist. '
            f'Create it or remove config_profile from {primary}.'
        )
    return resolved


__all__ = ['project_config_path', 'resolve_config_profile_path', 'user_default_config_path']
