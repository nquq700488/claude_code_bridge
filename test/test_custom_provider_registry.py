from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.config_loader import StructuredConfigValidationError, load_project_config
from ccbd import reload_apply_graph as reload_apply_graph_module
from ccbd import reload_apply_service as reload_apply_service_module
from ccbd.handlers import project_reload as project_reload_module
from ccbd.handlers.project_reload import build_project_reload_config_handler
from ccbd.reload_apply_graph import build_reload_service_graph
from ccbd.reload_apply_results import stage_result
from provider_command_defaults import (
    provider_start_parts,
    register_custom_provider_executable,
)
from provider_core.registry import build_default_backend_registry
from provider_core.catalog import build_default_provider_catalog
from provider_custom.factory import build_custom_backends
from provider_custom.parsing import parse_providers_section
from provider_custom.wiring import (
    custom_provider_names,
    restore_custom_provider_state,
    sync_custom_provider_wirings,
)
from provider_execution.registry import build_default_execution_registry
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


# --- Task 7: reload 路径重建 provider 注册表 -------------------------------


def _aider_specs():
    return parse_providers_section({
        'aider': {'mode': 'pane', 'command': 'aider', 'completion': 'quiet'},
    })


def _px_specs():
    return parse_providers_section({
        'px': {'mode': 'oneshot', 'command': 'px run', 'prompt_mode': 'arg', 'completion': 'exit'},
    })


class _FakeReloadConfig:
    def __init__(self, custom_providers):
        self.custom_providers = custom_providers
        self.agents = {}

    def to_record(self):
        return {'custom_providers': sorted(self.custom_providers)}


class _FakeGraph:
    def __init__(self, config):
        self.config = config
        self.config_identity = {'config_signature': 'sig'}
        self.version = 1


class _ReloadFakeApp:
    """轻量 fake app：只持有 reload 管线真实读取的字段，其余属性一律 None。"""

    def __init__(self, config):
        self.project_root = Path('/nonexistent-ccb-reload-test')
        self.project_id = 'reload-test'
        self.provider_catalog = build_default_provider_catalog()
        self.execution_registry = build_default_execution_registry()
        self.custom_provider_backends = ()
        self.custom_provider_errors = {}
        self.start_maintenance_lock = None
        self._graph = _FakeGraph(config)

    def current_service_graph(self):
        return self._graph

    def __getattr__(self, name):
        return None


def _reload_app():
    app = _ReloadFakeApp(_FakeReloadConfig(_aider_specs()))
    return app, app.provider_catalog, app.execution_registry


def _patch_config_load(monkeypatch, tmp_path, specs):
    """替换 handler 的配置读取：模拟真实 load 的进程级副作用（sync wiring + 注册 executable）。"""
    config_file = tmp_path / 'ccb.config'
    config_file.write_text('# fake config placeholder', encoding='utf-8')
    monkeypatch.setattr(project_reload_module, 'project_config_path', lambda root: config_file)

    def fake_load(root):
        sync_custom_provider_wirings(specs)
        for name in specs:
            register_custom_provider_executable(name, f'{name}-custom-bin')
        return SimpleNamespace(config=_FakeReloadConfig(specs))

    monkeypatch.setattr(project_reload_module, 'load_project_config', fake_load)


def _patch_apply_pipeline(monkeypatch, outcome):
    """monkeypatch reload_apply_service 各 stage 函数，强制驱动到指定 outcome。"""
    service = reload_apply_service_module
    plan = {
        'status': 'ok',
        'plan_class': 'maintenance_change',
        'future_safe_to_apply': True,
        'operations': [],
    }
    if outcome == 'no_change':
        plan = {**plan, 'plan_class': 'no_change'}
    monkeypatch.setattr(service, 'build_reload_dry_run_plan', lambda *a, **k: dict(plan))
    monkeypatch.setattr(service, 'current_namespace', lambda app, provided: (None, {}))
    monkeypatch.setattr(service, 'pre_namespace_unload_blocker', lambda *a, **k: None)
    monkeypatch.setattr(service, 'pre_namespace_replace_blocker', lambda *a, **k: None)
    monkeypatch.setattr(service, 'begin_reload_handoff', lambda *a, **k: object())
    monkeypatch.setattr(service, 'clear_reload_handoff', lambda *a, **k: None)
    if outcome == 'blocked':
        monkeypatch.setattr(service, 'plan_blocker', lambda p: ('forced_block', 'forced for test'))
        return
    if outcome == 'exception':
        def _boom(*a, **k):
            raise RuntimeError('forced graph build failure')

        monkeypatch.setattr(service, 'build_reload_service_graph', _boom)
        return
    monkeypatch.setattr(
        service,
        'build_reload_service_graph',
        lambda app, new_config, **kwargs: _FakeGraph(new_config),
    )
    if outcome == 'namespace_patch_failed':
        monkeypatch.setattr(service, '_namespace_patch_stage', lambda *a, **k: {'status': 'failed'})
    else:
        monkeypatch.setattr(service, '_namespace_patch_stage', lambda *a, **k: {'status': 'applied'})
    monkeypatch.setattr(service, 'run_runtime_mount', lambda *a, **k: {'status': 'noop'})

    def fake_publish(app, old_graph, target_graph, plan, **kwargs):
        if outcome == 'publish_failed':
            return stage_result(
                'failed',
                'publish_transaction',
                old_graph,
                target_graph,
                plan,
                diagnostics={'reason': 'forced_publish_failure'},
            )
        return stage_result(
            'published',
            'publish_transaction',
            old_graph,
            target_graph,
            plan,
            diagnostics={'graph_published': True},
        )

    monkeypatch.setattr(service, 'publish_stage', fake_publish)


def test_reload_graph_uses_rebuilt_catalog(monkeypatch):
    backends, errors = build_custom_backends(_px_specs())
    assert errors == {}
    candidate_catalog = build_default_provider_catalog(extra_backends=backends)
    app, _, _ = _reload_app()
    captured = {}

    def fake_build_graph(deps):
        captured['deps'] = deps
        return _FakeGraph(deps.config)

    monkeypatch.setattr(reload_apply_graph_module, 'build_ccbd_service_graph', fake_build_graph)

    build_reload_service_graph(
        app,
        _FakeReloadConfig(_px_specs()),
        provider_catalog=candidate_catalog,
        extra_provider_backends=tuple(backends),
    )

    deps = captured['deps']
    assert deps.provider_catalog is candidate_catalog
    assert deps.provider_catalog.get('px').provider == 'px'
    assert deps.extra_provider_backends
    assert tuple(deps.extra_provider_backends) == tuple(backends)


def test_reload_published_commits_app_fields_and_wiring(monkeypatch, tmp_path):
    app, old_catalog, old_registry = _reload_app()
    _patch_config_load(monkeypatch, tmp_path, _px_specs())
    _patch_apply_pipeline(monkeypatch, 'published')

    handler = build_project_reload_config_handler(app, app.current_service_graph)
    payload = handler({'dry_run': False})

    assert payload['status'] == 'published'
    assert app.provider_catalog is not old_catalog
    assert app.provider_catalog.get('px').provider == 'px'
    assert app.execution_registry is not old_registry
    assert app.execution_registry.get('px') is not None
    assert [b.provider for b in app.custom_provider_backends] == ['px']
    assert app.custom_provider_errors == {}
    assert 'px' in custom_provider_names()  # published 路径 wiring 不回滚


@pytest.mark.parametrize(
    'outcome',
    ['blocked', 'no_change', 'namespace_patch_failed', 'publish_failed', 'exception'],
)
def test_reload_unpublished_outcomes_restore_everything(monkeypatch, tmp_path, outcome):
    # 基线：含 [providers.aider] 的配置已生效（wiring = aider）
    sync_custom_provider_wirings(_aider_specs())
    app, old_catalog, old_registry = _reload_app()
    old_backends = app.custom_provider_backends
    _patch_config_load(monkeypatch, tmp_path, _px_specs())
    _patch_apply_pipeline(monkeypatch, outcome)

    handler = build_project_reload_config_handler(app, app.current_service_graph)
    if outcome == 'exception':
        with pytest.raises(RuntimeError, match='forced graph build failure'):
            handler({'dry_run': False})
    else:
        handler({'dry_run': False})

    assert app.provider_catalog is old_catalog
    assert app.execution_registry is old_registry
    assert app.custom_provider_backends is old_backends
    assert custom_provider_names() == ('aider',)  # wiring 回滚
    assert provider_start_parts('px') == ['px']  # executable 注册回滚，回退同名默认


def test_reload_dry_run_publishes_nothing(monkeypatch, tmp_path):
    sync_custom_provider_wirings(_aider_specs())
    app, old_catalog, old_registry = _reload_app()
    old_backends = app.custom_provider_backends
    _patch_config_load(monkeypatch, tmp_path, _px_specs())
    dry_run_plan = {'status': 'ok', 'plan_class': 'add_agent', 'dry_run': True}
    monkeypatch.setattr(
        project_reload_module,
        'build_reload_dry_run_plan',
        lambda *a, **k: dict(dry_run_plan),
    )

    handler = build_project_reload_config_handler(app, app.current_service_graph)
    payload = handler({'dry_run': True})

    assert payload['dry_run'] is True
    assert app.provider_catalog is old_catalog
    assert app.execution_registry is old_registry
    assert app.custom_provider_backends is old_backends
    assert custom_provider_names() == ('aider',)
    assert provider_start_parts('px') == ['px']
