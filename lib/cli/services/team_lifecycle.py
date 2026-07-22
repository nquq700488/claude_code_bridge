from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from agents.config_loader import load_project_config
from provider_custom.wiring import custom_provider_names
from teams.protocols import render_team_protocol


def team_list(context, command) -> dict:
    root = _project_root(context)
    config = load_project_config(root, include_loop_overlays=False).config
    teams = {}
    for name, spec in config.teams.items():
        instance = _load_team_instance(root, name)
        record = {
            'topology': spec.topology,
            'member_count': len(spec.members),
            'description': spec.description,
        }
        if instance:
            record['instance_status'] = instance.get('status', 'running')
        teams[name] = record
    return {'teams': teams}


def team_up(context, command) -> dict:
    root = _project_root(context)
    team_name = str(getattr(command, 'team_name', '') or '').strip()
    if not team_name:
        raise ValueError('team name is required')

    config = load_project_config(root, include_loop_overlays=False).config
    if team_name not in config.teams:
        raise ValueError(f'team {team_name!r} not defined in config')

    team = config.teams[team_name]
    member_results: list[dict] = []

    # 幂等检查
    existing = _load_team_instance(root, team_name)
    if existing and existing.get('status') == 'running':
        return {
            'team': team_name,
            'members': [
                {'name': m['name'], 'ok': True, 'state': 'existing'}
                for m in existing.get('members', [])
            ],
            'status': 'already_running',
        }
    if existing and existing.get('status') == 'partial':
        # 重试失败成员：只添加缺失的
        existing_names = {m['name'] for m in existing.get('members', [])}
        retry_members = [m for m in team.members if m.name not in existing_names]
        protocols = render_team_protocol(team)
        retry_results = []
        for m in retry_members:
            try:
                _write_member_lifecycle(context, root, m)
                _write_member_protocol(root, m.name, protocols.get(m.name, ''))
                retry_results.append({'name': m.name, 'ok': True})
            except Exception as exc:
                retry_results.append({'name': m.name, 'ok': False, 'error': str(exc)})
        # 更新 instance 状态
        all_members = existing.get('members', []) + [
            {'name': r['name'], 'provider': team.members[0].provider}
            for r in retry_results if r.get('ok')
        ]
        all_ok = len(all_members) == len(team.members)
        existing['members'] = all_members
        existing['status'] = 'running' if all_ok else 'partial'
        existing['upped_at'] = _utc_now()
        _write_team_instance(root, team_name, existing)
        _trigger_reload(context)
        return {
            'team': team_name,
            'members': retry_results + [
                {'name': m['name'], 'ok': True, 'state': 'existing'} for m in existing.get('members', [])
            ],
            'status': 'retried_partial',
        }
    if existing and existing.get('status') == 'parked':
        # 恢复 parked team：重新激活所有成员
        for m in existing.get('members', []):
            _mark_member_active(root, m['name'])
        existing['status'] = 'running'
        existing['upped_at'] = _utc_now()
        _write_team_instance(root, team_name, existing)
        _trigger_reload(context)
        return {
            'team': team_name,
            'members': [{'name': m['name'], 'ok': True, 'state': 'resumed'} for m in existing.get('members', [])],
            'status': 'resumed_from_parked',
        }

    # 校验成员名不与已有 agent 冲突（静态 + 动态 overlay）
    active_agents = config.agents
    for m in team.members:
        if m.name in active_agents:
            raise ValueError(
                f'team member {m.name!r} conflicts with existing agent'
            )

    # 校验 provider 已注册
    valid_providers = _valid_provider_names()
    for m in team.members:
        if m.provider not in valid_providers:
            raise ValueError(
                f'team member {m.name!r} uses unknown provider {m.provider!r}'
            )

    # 渲染协议
    protocols = render_team_protocol(team)

    # 逐成员写 lifecycle 状态 + 协议注入
    ok_members = []
    for m in team.members:
        try:
            _write_member_lifecycle(context, root, m)
            _write_member_protocol(root, m.name, protocols.get(m.name, ''))
            member_results.append({'name': m.name, 'ok': True})
            ok_members.append(m)
        except Exception as exc:
            member_results.append({'name': m.name, 'ok': False, 'error': str(exc)})

    # 写 team 实例状态（仅记录成功的成员，失败可重试）
    definition_hash = _team_definition_hash(team)
    all_ok = len(ok_members) == len(team.members)
    _write_team_instance(root, team_name, {
        'team_name': team_name,
        'topology': team.topology,
        'upped_at': _utc_now(),
        'definition_hash': definition_hash,
        'status': 'running' if all_ok else 'partial',
        'members': [{'name': m.name, 'provider': m.provider} for m in ok_members],
    })

    # 触发 reload
    reload_note = _trigger_reload(context)
    return {
        'team': team_name,
        'members': member_results,
        'reload': reload_note,
    }


def team_down(context, command) -> dict:
    root = _project_root(context)
    team_name = str(getattr(command, 'team_name', '') or '').strip()
    unload = bool(getattr(command, 'unload', False))

    instance = _load_team_instance(root, team_name)
    if not instance:
        raise ValueError(f'team {team_name!r} is not up')

    # 逐成员处理：默认 park，--unload 则标记为 unloaded
    for m in instance.get('members', []):
        _mark_member_down(context, root, m['name'], unload=unload)

    if unload:
        # --unload: 清除实例状态
        _remove_team_instance(root, team_name)
    else:
        # 默认 park: 保留实例状态，更新 status 为 parked
        instance['status'] = 'parked'
        _write_team_instance(root, team_name, instance)

    reload_note = _trigger_reload(context)
    return {
        'team': team_name,
        'parked': not unload,
        'reload': reload_note,
    }


def team_status(context, command) -> dict:
    root = _project_root(context)
    team_name = str(getattr(command, 'team_name', '') or '').strip()

    config = load_project_config(root, include_loop_overlays=False).config
    if team_name not in config.teams:
        raise ValueError(f'team {team_name!r} not defined in config')

    team = config.teams[team_name]
    instance = _load_team_instance(root, team_name)

    if not instance:
        return {
            'team': team_name,
            'status': 'not_up',
            'members': [],
            'definition_changed': False,
        }

    current_hash = _team_definition_hash(team)
    definition_changed = instance.get('definition_hash') != current_hash

    member_states = []
    for m in instance.get('members', []):
        state = _read_member_lifecycle_state(root, m['name'])
        member_states.append({
            'name': m['name'],
            'provider': m['provider'],
            'state': state.get('lifecycle_state', 'unknown') if state else 'missing',
            'status': state.get('agent_lifecycle_status', 'unknown') if state else 'missing',
        })

    return {
        'team': team_name,
        'status': instance.get('status', 'running'),
        'members': member_states,
        'definition_changed': definition_changed,
        'upped_at': instance.get('upped_at'),
    }


# ── helpers ──────────────────────────────────────────────────────────

_TEAMS_DIR = 'teams'
_AGENTS_DIR = 'agents'
_MEMORY_FILE = 'memory.md'


def _project_root(context) -> Path:
    direct = getattr(context, 'project_root', None)
    if direct is not None:
        return Path(direct)
    paths = getattr(context, 'paths', None)
    if paths is not None and getattr(paths, 'project_root', None) is not None:
        return Path(paths.project_root)
    return Path(context.project.project_root)


def _runtime_dir(root: Path) -> Path:
    return root / '.ccb' / 'runtime'


def _teams_dir(root: Path) -> Path:
    return _runtime_dir(root) / _TEAMS_DIR


def _agents_dir(root: Path) -> Path:
    return _runtime_dir(root) / _AGENTS_DIR


def _validate_name_safe(name: str, label: str) -> None:
    """Raise ValueError if name contains path traversal sequences."""
    if '..' in name or '/' in name or '\\' in name:
        raise ValueError(f'{label} contains forbidden path characters: {name!r}')


def _team_state_path(root: Path, team_name: str) -> Path:
    _validate_name_safe(team_name, 'team name')
    return _teams_dir(root) / team_name / 'state.json'


def _member_lifecycle_path(root: Path, agent_name: str) -> Path:
    _validate_name_safe(agent_name, 'agent name')
    return _agents_dir(root) / agent_name / 'lifecycle.json'


def _member_memory_path(root: Path, agent_name: str) -> Path:
    _validate_name_safe(agent_name, 'agent name')
    return root / '.ccb' / _AGENTS_DIR / agent_name / _MEMORY_FILE


def _valid_provider_names() -> frozenset[str]:
    # 内置 + 自定义 provider 名
    from provider_command_defaults import SUPPORTED_PROVIDER_NAMES

    return frozenset(SUPPORTED_PROVIDER_NAMES) | frozenset(custom_provider_names())


def _team_definition_hash(team) -> str:
    data = json.dumps(team.to_record(), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def _write_member_lifecycle(context, root: Path, member) -> None:
    """为 team 成员写入 dynamic agent 生命周期状态。

    团队成员的 lifecycle.json 格式与 ccb agent add 一致，
    但允许省略 role（spec 中 role 为可选字段）。
    """
    name = member.name
    lifecycle_path = _member_lifecycle_path(root, name)
    lifecycle_path.parent.mkdir(parents=True, exist_ok=True)

    now = _utc_now()
    state_dir = lifecycle_path.parent
    payload = {
        'schema_version': 1,
        'record_type': 'ccb_dynamic_agent_lifecycle',
        'agent_lifecycle_status': 'active',
        'agent': name,
        'profile': None,
        'role': member.role,
        'provider': member.provider,
        'model': member.model,
        'thinking': None,
        'workspace_mode': 'inplace',
        'workspace_group': None,
        'workspace_root': None,
        'workspace_path': None,
        'startup_args': [],
        'provider_profile': {},
        'target': '.',
        'labels': ['ccb-dynamic', 'ccb-team-member'],
        'description': member.description or f'Team member: {name}',
        'role_class': 'team_member',
        'lifecycle_state': 'hidden',  # team members start hidden
        'visibility_state': 'hidden',
        'dispatch_disabled': False,
        'window_name': None,
        'window_class': None,
        'loop_id': None,
        'node_id': None,
        'placement': {
            'mode': 'auto',
            'window_name': None,
            'window_class': None,
            'loop_id': None,
            'node_id': None,
            'layout_policy': 'append-or-create-window',
        },
        'lifetime': 'session',
        'created_at': now,
        'created_sequence': 1,
        'updated_at': now,
        'created_by': 'ccb team up',
        'last_reason': 'team up',
        'ask_target': name,
        'state_path': str(lifecycle_path),
        'events_path': str(state_dir / 'events.jsonl'),
    }
    _atomic_write_json(lifecycle_path, payload)


def _write_member_protocol(root: Path, agent_name: str, protocol_text: str) -> None:
    """写入团队协议到 agent private memory.md。

    此文件自动流经 project_memory 管线（SOURCE_AGENT_PRIVATE），
    在 provider 启动时注入到其 memory bundle 中。
    """
    memory_path = _member_memory_path(root, agent_name)
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    # 如果已有内容（手工写的 agent memory），追加而非覆盖
    existing = ''
    if memory_path.is_file():
        existing = memory_path.read_text(encoding='utf-8').rstrip()
    content = f"{existing}\n\n{protocol_text}".strip() + '\n'
    memory_path.write_text(content, encoding='utf-8')


def _mark_member_down(context, root: Path, agent_name: str, *, unload: bool = False) -> None:
    """标记 team 成员状态。

    unload=False（默认）: park 成员（lifecycle_state='parked', dispatch_disabled=True）
    unload=True: 标记为 unloaded
    """
    lifecycle_path = _member_lifecycle_path(root, agent_name)
    if not lifecycle_path.is_file():
        return
    try:
        payload = json.loads(lifecycle_path.read_text(encoding='utf-8'))
        if isinstance(payload, dict):
            if unload:
                payload['agent_lifecycle_status'] = 'unloaded'
                payload['lifecycle_state'] = 'unloaded'
            else:
                payload['lifecycle_state'] = 'parked'
                payload['dispatch_disabled'] = True
            payload['updated_at'] = _utc_now()
            _atomic_write_json(lifecycle_path, payload)
    except Exception:
        pass


def _mark_member_active(root: Path, agent_name: str) -> None:
    """重新激活被 park 的 team 成员。"""
    lifecycle_path = _member_lifecycle_path(root, agent_name)
    if not lifecycle_path.is_file():
        return
    try:
        payload = json.loads(lifecycle_path.read_text(encoding='utf-8'))
        if isinstance(payload, dict):
            payload['lifecycle_state'] = 'visible'
            payload['dispatch_disabled'] = False
            payload['agent_lifecycle_status'] = 'active'
            payload['updated_at'] = _utc_now()
            _atomic_write_json(lifecycle_path, payload)
    except Exception:
        pass


def _read_member_lifecycle_state(root: Path, agent_name: str) -> dict | None:
    path = _member_lifecycle_path(root, agent_name)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _load_team_instance(root: Path, team_name: str) -> dict | None:
    path = _team_state_path(root, team_name)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_team_instance(root: Path, team_name: str, payload: dict) -> None:
    path = _team_state_path(root, team_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(path, payload)


def _remove_team_instance(root: Path, team_name: str) -> None:
    path = _team_state_path(root, team_name)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _trigger_reload(context) -> str:
    """通知 ccbd 重载配置。"""
    try:
        from cli.services.daemon import connect_current_mounted_daemon

        handle = connect_current_mounted_daemon(context)
        handle.client.project_reload_config(dry_run=False)
        return 'reloaded'
    except Exception:
        return 'skipped (ccbd not running; 下次 ccb start 生效)'


def _atomic_write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + '.tmp')
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, path)


def team_ui(context, command) -> dict:
    """启动 team 群聊 UI Web 页面。"""
    from .team_ui import open_team_ui_url, prepare_team_ui

    handle = prepare_team_ui(context, command)
    open_team_ui_url(handle.url)
    handle.serve_forever()
    return handle.summary


def _utc_now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


__all__ = ['team_list', 'team_up', 'team_down', 'team_status', 'team_ui']
