from __future__ import annotations

from pathlib import Path

import pytest

from agents.config_loader import StructuredConfigValidationError, load_project_config
from provider_core.registry import build_default_backend_registry
from provider_core.catalog import build_default_provider_catalog
from provider_custom.factory import build_custom_backends
from provider_custom.parsing import parse_providers_section
from provider_custom.wiring import restore_custom_provider_state
from test_v3_config_loader import _project, _valid_v3_text


@pytest.fixture(autouse=True)
def _clean():
    yield
    restore_custom_provider_state({'wirings': {}, 'executables': {}})


def _specs():
    return parse_providers_section({
        'aider': {'mode': 'pane', 'command': 'aider', 'completion': 'quiet'},
        'px': {'mode': 'oneshot', 'command': 'px run', 'prompt_mode': 'arg', 'completion': 'exit'},
    })


def test_build_custom_backends_both_modes():
    backends, errors = build_custom_backends(_specs())
    assert errors == {}
    assert {b.provider for b in backends} == {'aider', 'px'}


def test_registry_accepts_extra_backends():
    backends, _ = build_custom_backends(_specs())
    registry = build_default_backend_registry(extra_backends=backends)
    assert registry.get('aider') is not None
    assert registry.get('px') is not None
    assert registry.get('claude') is not None  # 内置仍在


def test_catalog_lookup_custom_provider():
    backends, _ = build_custom_backends(_specs())
    catalog = build_default_provider_catalog(extra_backends=backends)
    assert catalog.get('aider').provider == 'aider'
    with pytest.raises(KeyError):
        catalog.get('nonexistent')


def test_duplicate_name_rejected():
    backends, _ = build_custom_backends(_specs())
    with pytest.raises(ValueError, match='duplicate'):
        build_default_backend_registry(extra_backends=[*backends, *backends])


def _rolepack_allow_provider(tmp_path: Path, role_id: str, provider: str) -> None:
    role_toml = tmp_path / 'roles' / 'installed' / role_id / 'current' / 'role.toml'
    text = role_toml.read_text(encoding='utf-8')
    role_toml.write_text(text.replace('"droid"]', f'"droid", "{provider}"]'), encoding='utf-8')


def test_v3_agent_may_reference_custom_provider(tmp_path, monkeypatch):
    text = _valid_v3_text().replace(
        'model = "gpt5.5"\nthinking = "medium"\n',
        '',
    ).replace(
        'provider = "claude"\nmodel = "Claude Sonnet 4.6 (Thinking)"',
        'provider = "aider"',
    ) + (
        '\n[providers.aider]\n'
        'mode = "pane"\n'
        'command = "aider"\n'
        'completion = "quiet"\n'
    )
    project_root = _project(tmp_path, monkeypatch, text=text)
    # rolepack 兼容性声明独立于 unknown-provider 校验：测试 rolepack 需显式声明支持 aider
    _rolepack_allow_provider(tmp_path, 'agentroles.ccb_round_reviewer', 'aider')

    result = load_project_config(project_root, include_loop_overlays=False)

    assert 'aider' in result.config.custom_providers
    assert result.config.workflow.dynamic['ccb_round_reviewer'].provider == 'aider'


def test_v3_unknown_provider_still_rejected(tmp_path, monkeypatch):
    text = _valid_v3_text().replace('provider = "claude"', 'provider = "not-a-provider"')
    project_root = _project(tmp_path, monkeypatch, text=text)

    with pytest.raises(StructuredConfigValidationError) as exc_info:
        load_project_config(project_root, include_loop_overlays=False)

    assert exc_info.value.code == 'v3_provider_unknown'
    assert exc_info.value.path == 'workflow.dynamic.ccb_round_reviewer.provider'
