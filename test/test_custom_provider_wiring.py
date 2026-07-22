from __future__ import annotations

import json

import pytest

from provider_command_defaults import provider_start_parts, register_custom_provider_executable
from provider_custom.parsing import parse_providers_section
from provider_custom.wiring import (
    custom_provider_names,
    custom_provider_wiring,
    resolve_env_value,
    restore_custom_provider_state,
    snapshot_custom_provider_state,
    sync_custom_provider_wirings,
)
from provider_model_shortcuts import (
    provider_model_runtime_env,
    provider_model_runtime_env_keys,
    provider_model_startup_args,
    startup_args_contain_model_flag,
)
from provider_profiles import provider_api_shortcut_env
from provider_profiles.materializer import provider_api_env_keys


@pytest.fixture(autouse=True)
def _clean_wirings():
    yield
    restore_custom_provider_state({'wirings': {}, 'executables': {}})


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


def _write_project(tmp_path, text: str):
    root = tmp_path / 'proj'
    (root / '.ccb').mkdir(parents=True)
    (root / '.ccb' / 'ccb.config').write_text(text, encoding='utf-8')
    return root


def _sync(**overrides):
    table = {
        'mode': 'pane', 'command': 'aider', 'completion': 'marker',
        'key_env': 'AIDER_API_KEY', 'url_env': 'AIDER_BASE_URL', 'model_env': 'AIDER_MODEL',
    }
    table.update(overrides)
    specs = parse_providers_section({'aider': table})
    sync_custom_provider_wirings(specs)
    return specs['aider']


def test_wiring_registered_and_names_listed():
    _sync()
    assert custom_provider_names() == ('aider',)
    wiring = custom_provider_wiring('Aider')
    assert wiring is not None and wiring.key_env == 'AIDER_API_KEY'


def test_api_shortcut_env_via_dynamic_wiring():
    _sync()
    env = provider_api_shortcut_env('aider', key='sk-x', url='https://api.x/v1')
    assert env == {'AIDER_API_KEY': 'sk-x', 'AIDER_BASE_URL': 'https://api.x/v1'}
    assert provider_api_env_keys('aider') == {'AIDER_API_KEY', 'AIDER_BASE_URL'}


def test_api_shortcut_unwired_field_raises():
    specs = parse_providers_section({'aider': {
        'mode': 'pane', 'command': 'aider', 'completion': 'marker', 'key_env': 'AIDER_API_KEY',
    }})
    sync_custom_provider_wirings(specs)
    with pytest.raises(ValueError, match='url'):
        provider_api_shortcut_env('aider', url='https://api.x')


def test_model_shortcut_env_mode():
    _sync()
    assert provider_model_startup_args('aider', model='gpt-5') == ()
    assert provider_model_runtime_env('aider', model='gpt-5') == {'AIDER_MODEL': 'gpt-5'}
    assert provider_model_runtime_env_keys('aider') == {'AIDER_MODEL'}


def test_model_shortcut_flag_mode():
    # 显式只有 model_flag 的接线（无 model_env）：
    # 解析合法——model_flag 单独存在表示"支持 flag 接线、默认值留给 agent 级"。
    specs = parse_providers_section({'aider': {
        'mode': 'pane', 'command': 'aider', 'completion': 'marker', 'model_flag': '--model',
    }})
    sync_custom_provider_wirings(specs)
    assert provider_model_startup_args('aider', model='gpt-5') == ('--model', 'gpt-5')
    assert provider_model_runtime_env('aider', model='gpt-5') == {}
    assert startup_args_contain_model_flag('aider', ('--model', 'gpt-5')) is True


def test_model_shortcut_unwired_raises():
    specs = parse_providers_section({'aider': {'mode': 'pane', 'command': 'aider', 'completion': 'marker'}})
    sync_custom_provider_wirings(specs)
    with pytest.raises(ValueError, match='model'):
        provider_model_startup_args('aider', model='gpt-5')


def test_env_value_indirection(monkeypatch):
    monkeypatch.setenv('MY_KEY', 'sk-resolved')
    assert resolve_env_value('$MY_KEY') == 'sk-resolved'
    assert resolve_env_value('$MISSING_VAR_XYZ') is None
    assert resolve_env_value('sk-plain') == 'sk-plain'
    assert resolve_env_value(None) is None


def test_register_custom_provider_executable():
    register_custom_provider_executable('aider', 'aider-cli')
    assert provider_start_parts('aider') == ['aider-cli']
    register_custom_provider_executable('codex', 'evil')  # 内置名不可覆盖
    assert provider_start_parts('codex') != ['evil']


def test_snapshot_restore_roundtrip():
    _sync()
    register_custom_provider_executable('aider', 'aider-cli')
    snap = snapshot_custom_provider_state()
    # 模拟"另一个配置"污染全局状态
    sync_custom_provider_wirings(parse_providers_section({'other': {
        'mode': 'pane', 'command': 'other', 'completion': 'quiet',
    }}))
    register_custom_provider_executable('other', 'other-cli')
    assert custom_provider_names() == ('other',)
    restore_custom_provider_state(snap)
    assert custom_provider_names() == ('aider',)
    assert provider_start_parts('aider') == ['aider-cli']
    assert provider_start_parts('other') == ['other']  # 注册被还原，回退同名默认


def test_failed_parse_leaves_previous_wiring_intact(tmp_path):
    # 先成功加载含自定义 provider 的配置，再加载一个会在 providers 之后失败的配置；
    # 断言失败后 wiring 仍是第一份配置的状态（validators 的 snapshot/restore 纪律）。
    from agents.config_loader import load_project_config
    from agents.config_loader_runtime.common import ConfigValidationError

    good = _write_project(
        tmp_path / 'good',
        _V2_BASE + '\n[providers.aider]\nmode = "pane"\ncommand = "aider"\ncompletion = "marker"\n',
    )
    load_project_config(good, include_loop_overlays=False)
    assert custom_provider_names() == ('aider',)

    bad = _write_project(
        tmp_path / 'bad',
        _V2_BASE + '\n[providers.badx]\nmode = "bogus"\ncommand = "x"\n',
    )
    with pytest.raises(ConfigValidationError):
        load_project_config(bad, include_loop_overlays=False)
    assert custom_provider_names() == ('aider',)  # 失败不留痕


def test_default_load_with_overlays_keeps_custom_providers(tmp_path):
    # 回归：loop/dynamic overlay 的 _copy_config 逐字段重建 ProjectConfig 时
    # 曾丢弃 custom_providers——默认参数 load（include_loop_overlays=True）
    # 且存在活动 loop 状态时必须保留 [providers] 解析结果。
    from agents.config_loader import load_project_config

    root = _write_project(
        tmp_path,
        _V2_BASE + '\n[providers.aider]\nmode = "pane"\ncommand = "aider"\ncompletion = "marker"\n',
    )
    capacity_path = root / '.ccb' / 'runtime' / 'loops' / 'loop-a' / 'capacity.json'
    capacity_path.parent.mkdir(parents=True)
    capacity_path.write_text(
        json.dumps({
            'loop_capacity_status': 'ensured',
            'loop_id': 'loop-a',
            'agents': [
                {'name': 'loopbot', 'profile': 'worker', 'provider': 'claude', 'state': 'planned'},
            ],
        }),
        encoding='utf-8',
    )
    config = load_project_config(root).config
    assert 'loopbot' in config.agents  # overlay 确实重建了 config
    assert config.custom_providers
    assert 'aider' in config.custom_providers
