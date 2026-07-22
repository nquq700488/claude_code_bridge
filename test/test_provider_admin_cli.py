from __future__ import annotations

import pytest

from cli.services.provider_admin import provider_add, provider_list, provider_remove


# 与 test_custom_provider_wiring.py 的 _V2_BASE 对齐：v2 校验要求
# layout / workspace_mode / restore / permission 字段齐全。
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


class _Ctx:  # 最小 context：按 provider_admin 实际用到的属性裁剪
    def __init__(self, root):
        self.project_root = root


class _Cmd:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_add_writes_config_and_list_reads_back(tmp_path):
    ctx = _Ctx(_project(tmp_path))
    provider_add(ctx, _Cmd(action='add', provider_name='aider', no_reload=True, json=False, options={
        'mode': 'pane', 'command': 'aider --dark-mode', 'completion': 'marker',
    }))
    listed = provider_list(ctx, _Cmd(action='list', json=True))
    assert listed['aider']['mode'] == 'pane'
    assert listed['aider']['command'] == 'aider --dark-mode'
    # 配置文本注释与其他段不受影响
    text = (tmp_path / 'proj' / '.ccb' / 'ccb.config').read_text(encoding='utf-8')
    assert '[agents.main]' in text and '[providers.aider]' in text


def test_add_rejects_invalid_spec(tmp_path):
    ctx = _Ctx(_project(tmp_path))
    with pytest.raises(Exception, match='completion'):
        provider_add(ctx, _Cmd(action='add', provider_name='aider', no_reload=True, json=False,
                               options={'mode': 'pane', 'command': 'aider'}))
    assert '[providers.aider]' not in (tmp_path / 'proj' / '.ccb' / 'ccb.config').read_text(encoding='utf-8')


def test_remove_blocked_by_agent_reference(tmp_path):
    text = _V2_BASE + '''
[providers.aider]
mode = "pane"
command = "aider"
completion = "marker"

[agents.helper]
provider = "aider"
target = "helper"
workspace_mode = "inplace"
restore = "auto"
permission = "manual"
'''
    ctx = _Ctx(_project(tmp_path, text))
    with pytest.raises(Exception, match='helper'):
        provider_remove(ctx, _Cmd(action='remove', provider_name='aider', no_reload=True))


def test_remove_roundtrip(tmp_path):
    text = _V2_BASE + '''
[providers.aider]
mode = "pane"
command = "aider"
completion = "marker"
'''
    ctx = _Ctx(_project(tmp_path, text))
    provider_remove(ctx, _Cmd(action='remove', provider_name='aider', no_reload=True))
    assert provider_list(ctx, _Cmd(action='list', json=True)) == {}
