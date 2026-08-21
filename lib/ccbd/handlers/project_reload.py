from __future__ import annotations

from time import monotonic

from agents.config_loader import load_project_config, project_config_path
from ccbd.reload_apply import run_additive_reload_apply
from ccbd.reload_apply_results import status_of
from ccbd.reload_drain_status import reload_drain_status_payload
from ccbd.reload_plan import build_invalid_reload_dry_run_plan, build_reload_dry_run_plan
from project_command_trust import require_project_command_approval
from provider_core.catalog import build_default_provider_catalog
from provider_custom.factory import build_custom_backends
from provider_custom.wiring import (
    restore_custom_provider_state,
    snapshot_custom_provider_state,
)
from provider_execution.registry import build_default_execution_registry
from .project_reload_metrics import metrics_fields
from .project_reload_payload import (
    apply_reload_payload,
    non_dry_run_invalid_config_payload,
)


def build_project_reload_config_handler(app, current_graph_fn):
    def handle(payload: dict) -> dict:
        dry_run = _truthy(payload.get('dry_run'))
        started = monotonic()
        plan_class = 'error'
        error_text = None
        published = False
        # load_project_config 期间会 sync 进程级 wiring/executable 注册，先快照；
        # 非 published 的所有路径（dry-run / 配置非法 / blocked / no_change /
        # 各 stage failed / 异常）在 finally 中恢复，保证 reload 对 provider
        # 状态是完整事务。
        provider_state_snapshot = snapshot_custom_provider_state()
        try:
            graph = current_graph_fn()
            try:
                config_path = project_config_path(app.project_root)
                if not config_path.is_file():
                    raise FileNotFoundError(f'project config not found: {config_path}')
                new_config = load_project_config(app.project_root).config
                require_project_command_approval(app.project_root)
            except Exception as exc:
                plan = build_invalid_reload_dry_run_plan(
                    graph.config,
                    exc,
                    current_config_identity=graph.config_identity,
                )
                if not dry_run:
                    plan = non_dry_run_invalid_config_payload(plan)
            else:
                if dry_run:
                    plan = build_reload_dry_run_plan(
                        graph.config,
                        new_config,
                        current_config_identity=graph.config_identity,
                        project_id=getattr(app, 'project_id', None),
                        current_namespace=_current_namespace(app),
                    )
                else:
                    # 候选先构建、后发布：纯构建，不触碰 app 字段
                    candidates = _build_provider_candidates(new_config)
                    result = run_additive_reload_apply(
                        app,
                        new_config,
                        reload_provider_candidates=candidates,
                    )
                    published = status_of(result) == 'published'
                    plan = apply_reload_payload(result, app=app)
            payload = _with_reload_drains(app, plan)
            plan_class, error_text = metrics_fields(payload, fallback_plan_class=plan_class)
            return payload
        except Exception as exc:
            error_text = str(exc)
            raise
        finally:
            if not published:
                # dry-run / 配置非法 / blocked / no_change / 各 stage failed / 异常：
                # 恢复 load 期间 sync 的 wiring 与 executable 注册（validators 失败
                # 已回滚，此处 restore 幂等；配置非法路径走同一 finally 也无害）。
                restore_custom_provider_state(provider_state_snapshot)
            metrics = getattr(app, 'control_plane_metrics', None)
            if metrics is not None:
                metrics.last_reload_duration_s = max(0.0, monotonic() - started)
                metrics.last_reload_plan_class = plan_class
                metrics.last_reload_error = error_text

    return handle


def _build_provider_candidates(new_config) -> dict:
    """从 new_config 纯构建候选 provider 注册表，不触碰 app 字段与 pane/tmux 状态。

    安全性论证：catalog/execution registry 是纯数据查找表，候选构建不触碰
    pane/tmux/session 状态；namespace diff 由 config 决定，custom_providers 不进
    topology signature（Task 1），因此 provider 定义新增不会触发运行中 agent 的
    namespace 替换。app 字段提交与 graph 发布同锁同边界（reload_apply_service
    在 maintenance lock 内、publish 成功后提交）；wiring 在 published 之外的
    所有路径由 handler finally 回滚——reload 对 provider 状态是完整事务。
    """
    backends, errors = build_custom_backends(new_config.custom_providers)
    return {
        'backends': backends,
        'errors': errors,
        'provider_catalog': build_default_provider_catalog(extra_backends=backends),
        'execution_registry': build_default_execution_registry(extra_backends=backends),
    }


def _truthy(value) -> bool:
    if value is True:
        return True
    if value is False or value is None:
        return False
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _current_namespace(app):
    namespace_controller = getattr(app, 'project_namespace', None)
    load = getattr(namespace_controller, 'load', None)
    if not callable(load):
        return None
    try:
        return load()
    except Exception:
        return None


def _with_reload_drains(app, payload: dict[str, object]) -> dict[str, object]:
    result = dict(payload)
    result['reload_drains'] = reload_drain_status_payload(app)
    return result


__all__ = ['build_project_reload_config_handler']
