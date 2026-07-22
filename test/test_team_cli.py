from __future__ import annotations
import pytest
from cli.services.team_lifecycle import team_list
from cli.parser_runtime.commands import parse_team


class _Ctx:
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
