from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from agents.config_loader import load_project_config
from agents.config_loader_runtime.paths import project_config_path, resolve_config_profile_path
from provider_custom.factory import build_custom_backends
from provider_custom.wiring import restore_custom_provider_state, snapshot_custom_provider_state
from storage.atomic import atomic_write_text


class ProviderAdminError(ValueError):
    pass


def provider_list(context, command) -> dict:
    root = _project_root(context)
    config = load_project_config(root, include_loop_overlays=False).config
    providers = {name: spec.to_record() for name, spec in config.custom_providers.items()}
    # 组装失败的 provider 必须可见（评审 R1：不得只退化为 unknown provider）——
    # list 输出带每个 provider 的可用状态与失败原因
    _backends, errors = build_custom_backends(config.custom_providers)
    for name, reason in errors.items():
        if name in providers:
            providers[name]['status'] = 'unavailable'
            providers[name]['error'] = reason
    for name in providers:
        providers[name].setdefault('status', 'ok')
    return providers


def provider_add(context, command) -> dict:
    root = _project_root(context)
    path = _config_path(root)
    name = str(command.provider_name or '').strip().lower()
    fields = {k: v for k, v in dict(command.options).items() if v is not None}
    before = path.read_text(encoding='utf-8') if path.is_file() else 'version = 2\n'
    if re.search(rf'^\[providers\.{re.escape(name)}\]\s*$', before, re.MULTILINE):
        raise ProviderAdminError(f'provider {name} already exists; use `ccb provider remove {name}` first')
    block = _render_provider_block(name, fields)
    after = before.rstrip('\n') + '\n\n' + block + '\n'
    _validate_config_text(root, after)  # 校验失败则不落盘
    atomic_write_text(path, after)
    key_value = fields.get('key')
    warnings = []
    if isinstance(key_value, str) and key_value and not key_value.startswith('$'):
        warnings.append('明文 key 已写入配置文件（可入 git 的仓库建议改用 $ENV_VAR 间接引用）')
    reload_note = _maybe_reload(context, command)
    return {'added': name, 'warnings': warnings, 'reload': reload_note}


def provider_remove(context, command) -> dict:
    root = _project_root(context)
    path = _config_path(root)
    name = str(command.provider_name or '').strip().lower()
    refs = _provider_references(root, name)
    if refs:
        raise ProviderAdminError(
            f'provider {name} is referenced by agents: {", ".join(sorted(refs))}; remove them first'
        )
    before = path.read_text(encoding='utf-8')
    after = _remove_provider_block(before, name)
    if after == before:
        raise ProviderAdminError(f'provider {name} not defined in {path}')
    _validate_config_text(root, after)
    atomic_write_text(path, after)
    return {'removed': name, 'reload': _maybe_reload(context, command)}


def _render_provider_block(name: str, fields: dict) -> str:
    lines = [f'[providers.{name}]']
    for key in ('description', 'mode', 'command', 'completion', 'marker', 'prompt_mode', 'home_env',
                'key', 'url', 'model', 'key_env', 'url_env', 'model_env', 'model_flag'):
        if key in fields:
            lines.append(f'{key} = {json.dumps(str(fields[key]))}')
    for key in ('quiet_secs', 'timeout_secs'):
        if key in fields:
            lines.append(f'{key} = {fields[key]}')
    env = fields.get('env') or {}
    if env:
        pairs = ', '.join(f'{k} = {json.dumps(str(v))}' for k, v in env.items())
        lines.append(f'env = {{ {pairs} }}')
    return '\n'.join(lines)


def _remove_provider_block(text: str, name: str) -> str:
    lines = text.split('\n')
    out: list[str] = []
    skipping = False
    header_re = re.compile(rf'^\[providers\.{re.escape(name)}\]\s*$')
    for line in lines:
        if header_re.match(line):
            skipping = True
            continue
        if skipping and re.match(r'^\[', line):
            skipping = False
        if not skipping:
            out.append(line)
    return '\n'.join(out)


def _validate_config_text(root: Path, text: str) -> None:
    # 只读校验纪律（评审 R1）：临时目录加载会触发 wiring sync，
    # 必须在 finally 中还原进程级 provider 状态，校验行为不得产生副作用
    snapshot = snapshot_custom_provider_state()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            (tmp_root / '.ccb').mkdir()
            (tmp_root / '.ccb' / 'ccb.config').write_text(text, encoding='utf-8')
            try:
                load_project_config(tmp_root, include_loop_overlays=False)
            except Exception as exc:
                raise ProviderAdminError(f'config validation failed: {exc}') from exc
    finally:
        restore_custom_provider_state(snapshot)


def _provider_references(root: Path, name: str) -> list[str]:
    # 检查 config.agents（含动态 agent overlay）+ team 成员引用
    config = load_project_config(root).config
    refs = [agent_name for agent_name, spec in config.agents.items() if spec.provider == name]
    for team_name, team_spec in (config.teams or {}).items():
        for member in (getattr(team_spec, 'members', None) or ()):
            member_name = getattr(member, 'name', None)
            member_provider = getattr(member, 'provider', None)
            if member_provider == name and member_name is not None:
                refs.append(f'{member_name} (team {team_name})')
    return refs


def _maybe_reload(context, command) -> str:
    if getattr(command, 'no_reload', False):
        return 'skipped (--no-reload)'
    try:
        from cli.services.daemon import connect_current_mounted_daemon

        handle = connect_current_mounted_daemon(context)
        handle.client.project_reload_config(dry_run=False)
    except Exception:
        return 'skipped (ccbd not running; 下次 ccb start 生效)'
    return 'reloaded'


def _project_root(context) -> Path:
    # 测试 stub 直接暴露 .project_root；真实 CliContext 走 .paths.project_root
    # （与 storage.paths.PathLayout 对齐），再兜底 .project.project_root。
    direct = getattr(context, 'project_root', None)
    if direct is not None:
        return Path(direct)
    paths = getattr(context, 'paths', None)
    if paths is not None and getattr(paths, 'project_root', None) is not None:
        return Path(paths.project_root)
    return Path(context.project.project_root)


def _config_path(root: Path) -> Path:
    # resolve_config_profile_path 无 profile 时返回 None（而非抛 FileNotFoundError）。
    resolved = resolve_config_profile_path(root)
    if resolved is not None:
        return resolved
    return project_config_path(root)


__all__ = [
    'ProviderAdminError',
    'provider_add',
    'provider_list',
    'provider_remove',
]
