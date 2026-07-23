from __future__ import annotations

import json

import pytest

from cli.parser_runtime.commands import parse_team


class TestParseTeamUi:
    def test_parse_ui(self):
        cmd = parse_team(['ui', 'myteam'], project=None, error_type=ValueError)
        assert cmd.action == 'ui'
        assert cmd.team_name == 'myteam'
        assert cmd.kind == 'team'
        assert cmd.port == 8888

    def test_parse_ui_with_port(self):
        cmd = parse_team(['ui', 'myteam', '--port', '9999'], project=None, error_type=ValueError)
        assert cmd.action == 'ui'
        assert cmd.team_name == 'myteam'
        assert cmd.port == 9999


_V2_BASE = '''version = 2
default_agents = ["main"]
layout = "main"

[agents.main]
provider = "claude"
target = "main"
workspace_mode = "inplace"
restore = "auto"
permission = "manual"

[teams.t]
topology = "mesh"
[[teams.t.members]]
name = "team-a"
provider = "claude"
[[teams.t.members]]
name = "team-b"
provider = "codex"
'''


def _project(tmp_path, text=_V2_BASE):
    root = tmp_path / 'proj'
    (root / '.ccb').mkdir(parents=True)
    (root / '.ccb' / 'ccb.config').write_text(text, encoding='utf-8')
    return root


class _Ctx:
    def __init__(self, root):
        self.project_root = root
        self.project = type('_P', (), {'project_root': root})()


class _Cmd:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class TestTeamUiServer:
    def test_prepare_team_ui_creates_handle(self, tmp_path):
        root = _project(tmp_path)
        from cli.services.team_ui import prepare_team_ui

        # First team start to create instance state
        from cli.services.team_lifecycle import team_start
        ctx = _Ctx(root)
        team_start(ctx, _Cmd(action='start', team_name='t'))

        # Now prepare UI handle
        handle = prepare_team_ui(ctx, _Cmd(action='ui', team_name='t', port=0))
        assert 'team_ui_status' in handle.summary
        assert handle.summary['team'] == 't'
        assert handle.url.startswith('http://127.0.0.1:')
        handle.close()

    def test_prepare_team_ui_rejects_unknown_team(self, tmp_path):
        root = _project(tmp_path)
        from cli.services.team_ui import prepare_team_ui
        ctx = _Ctx(root)
        with pytest.raises(ValueError, match='not defined'):
            prepare_team_ui(ctx, _Cmd(action='ui', team_name='nonexistent'))

    def test_api_state_endpoint(self, tmp_path):
        root = _project(tmp_path)
        from cli.services.team_lifecycle import team_start
        from cli.services.team_ui import _build_state_payload

        ctx = _Ctx(root)
        team_start(ctx, _Cmd(action='start', team_name='t'))

        state = _build_state_payload(root, 't')
        assert state['team'] == 't'
        assert state['status'] == 'running'
        assert len(state['members']) == 2
        member_names = {m['name'] for m in state['members']}
        assert member_names == {'team-a', 'team-b'}

    def test_api_timeline_endpoint(self, tmp_path):
        root = _project(tmp_path)
        from cli.services.team_lifecycle import team_start
        from cli.services.team_ui import _build_timeline_payload

        ctx = _Ctx(root)
        team_start(ctx, _Cmd(action='start', team_name='t'))

        timeline = _build_timeline_payload(root, 't', '')
        assert 'events' in timeline
        assert 'cursor' in timeline

    def test_api_send_validation(self, tmp_path):
        root = _project(tmp_path)
        from cli.services.team_ui import _handle_send

        result = _handle_send(root, 't', {'to': '', 'body': 'hi'})
        assert result['status'] == 'error'

        result = _handle_send(root, 't', {'to': 'x', 'body': ''})
        assert result['status'] == 'error'
