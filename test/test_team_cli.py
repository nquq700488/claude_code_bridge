from __future__ import annotations

import json

import pytest

from cli.parser_runtime.commands import parse_team
from cli.services.team_lifecycle import team_down, team_list, team_status, team_up


class _Ctx:
    def __init__(self, root):
        self.project_root = root
        self.project = _Proj(root)


class _Proj:
    def __init__(self, root):
        self.project_root = root


class _Cmd:
    def __init__(self, **kw):
        self.__dict__.update(kw)


_V2_BASE = '''version = 2
default_agents = ["main"]
layout = "main"

[agents.main]
provider = "claude"
target = "main"
workspace_mode = "inplace"
restore = "auto"
permission = "manual"
'''


def _project(tmp_path, text=_V2_BASE):
    root = tmp_path / 'proj'
    (root / '.ccb').mkdir(parents=True)
    (root / '.ccb' / 'ccb.config').write_text(text, encoding='utf-8')
    return root


class TestParseTeam:
    def test_parse_list(self):
        cmd = parse_team(['list'], project=None, error_type=ValueError)
        assert cmd.action == 'list'
        assert cmd.kind == 'team'

    def test_parse_up(self):
        cmd = parse_team(['up', 'myteam', '--window', 'w1', '--parked'], project=None, error_type=ValueError)
        assert cmd.action == 'up'
        assert cmd.team_name == 'myteam'
        assert cmd.window == 'w1'
        assert cmd.parked is True

    def test_parse_down(self):
        cmd = parse_team(['down', 'myteam', '--unload'], project=None, error_type=ValueError)
        assert cmd.action == 'down'
        assert cmd.team_name == 'myteam'
        assert cmd.unload is True

    def test_parse_status(self):
        cmd = parse_team(['status', 'myteam', '--json'], project=None, error_type=ValueError)
        assert cmd.action == 'status'
        assert cmd.json_output is True

    def test_parse_unknown_action(self):
        with pytest.raises(ValueError, match='unknown team action'):
            parse_team(['fly'], project=None, error_type=ValueError)

    def test_parse_no_action(self):
        with pytest.raises(ValueError, match='team requires'):
            parse_team([], project=None, error_type=ValueError)


class TestTeamList:
    def test_list_empty(self, tmp_path):
        ctx = _Ctx(_project(tmp_path))
        result = team_list(ctx, _Cmd(action='list'))
        assert result == {'teams': {}}

    def test_list_with_team(self, tmp_path):
        text = _V2_BASE + '''
[teams.t]
topology = "mesh"
[[teams.t.members]]
name = "a"
provider = "claude"
[[teams.t.members]]
name = "b"
provider = "codex"
'''
        ctx = _Ctx(_project(tmp_path, text))
        result = team_list(ctx, _Cmd(action='list'))
        assert 't' in result['teams']
        assert result['teams']['t']['topology'] == 'mesh'
        assert result['teams']['t']['member_count'] == 2


_TEAM_CONFIG = _V2_BASE + '''
[teams.t]
topology = "mesh"
[[teams.t.members]]
name = "team-a"
provider = "claude"
[[teams.t.members]]
name = "team-b"
provider = "codex"
'''


class TestTeamUpDown:
    def test_team_up_creates_lifecycle_and_memory(self, tmp_path):
        root = _project(tmp_path, _TEAM_CONFIG)
        ctx = _Ctx(root)
        result = team_up(ctx, _Cmd(action='up', team_name='t'))
        assert result['team'] == 't'
        assert len(result['members']) == 2
        assert all(m['ok'] for m in result['members'])

        # 验证 lifecycle.json 已写入
        for name in ('team-a', 'team-b'):
            lc = root / '.ccb' / 'runtime' / 'agents' / name / 'lifecycle.json'
            assert lc.is_file()
            data = json.loads(lc.read_text(encoding='utf-8'))
            assert data['agent'] == name
            assert data['lifecycle_state'] == 'hidden'

        # 验证 memory.md 已写入
        for name in ('team-a', 'team-b'):
            mem = root / '.ccb' / 'agents' / name / 'memory.md'
            assert mem.is_file()
            content = mem.read_text(encoding='utf-8')
            assert 'Team: t' in content

        # 验证 team 实例状态
        state = root / '.ccb' / 'runtime' / 'teams' / 't' / 'state.json'
        assert state.is_file()

    def test_team_up_idempotent(self, tmp_path):
        root = _project(tmp_path, _TEAM_CONFIG)
        ctx = _Ctx(root)
        team_up(ctx, _Cmd(action='up', team_name='t'))
        result2 = team_up(ctx, _Cmd(action='up', team_name='t'))
        assert result2['status'] == 'already_running'

    def test_team_up_rejects_unknown_team(self, tmp_path):
        ctx = _Ctx(_project(tmp_path, _TEAM_CONFIG))
        with pytest.raises(ValueError, match='not defined'):
            team_up(ctx, _Cmd(action='up', team_name='nonexistent'))

    def test_team_up_rejects_unknown_provider(self, tmp_path):
        text = _V2_BASE + '''
[teams.bad]
topology = "mesh"
[[teams.bad.members]]
name = "a"
provider = "not-a-real-provider-xyz"
[[teams.bad.members]]
name = "b"
provider = "claude"
'''
        ctx = _Ctx(_project(tmp_path, text))
        with pytest.raises(ValueError, match='unknown provider'):
            team_up(ctx, _Cmd(action='up', team_name='bad'))

    def test_team_up_rejects_member_name_conflict(self, tmp_path):
        text = _V2_BASE + '''
[teams.t]
topology = "mesh"
[[teams.t.members]]
name = "main"
provider = "claude"
[[teams.t.members]]
name = "b"
provider = "codex"
'''
        ctx = _Ctx(_project(tmp_path, text))
        with pytest.raises(ValueError, match='conflicts'):
            team_up(ctx, _Cmd(action='up', team_name='t'))

    def test_team_down_marks_unloaded(self, tmp_path):
        root = _project(tmp_path, _TEAM_CONFIG)
        ctx = _Ctx(root)
        team_up(ctx, _Cmd(action='up', team_name='t'))
        result = team_down(ctx, _Cmd(action='down', team_name='t'))
        assert result['team'] == 't'

        # 成员 lifecycle 应为 unloaded
        for name in ('team-a', 'team-b'):
            lc = root / '.ccb' / 'runtime' / 'agents' / name / 'lifecycle.json'
            data = json.loads(lc.read_text(encoding='utf-8'))
            assert data['agent_lifecycle_status'] == 'unloaded'

        # team 实例状态应已清除
        state = root / '.ccb' / 'runtime' / 'teams' / 't' / 'state.json'
        assert not state.is_file()

    def test_team_down_rejects_not_up(self, tmp_path):
        ctx = _Ctx(_project(tmp_path, _TEAM_CONFIG))
        with pytest.raises(ValueError, match='not up'):
            team_down(ctx, _Cmd(action='down', team_name='t'))

    def test_team_status_not_up(self, tmp_path):
        ctx = _Ctx(_project(tmp_path, _TEAM_CONFIG))
        result = team_status(ctx, _Cmd(action='status', team_name='t'))
        assert result['status'] == 'not_up'

    def test_team_status_running(self, tmp_path):
        root = _project(tmp_path, _TEAM_CONFIG)
        ctx = _Ctx(root)
        team_up(ctx, _Cmd(action='up', team_name='t'))
        result = team_status(ctx, _Cmd(action='status', team_name='t'))
        assert result['status'] == 'running'
        assert len(result['members']) == 2
        assert result['definition_changed'] is False
