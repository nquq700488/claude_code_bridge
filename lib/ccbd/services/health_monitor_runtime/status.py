from __future__ import annotations

from dataclasses import replace

from agents.models import AgentState, RuntimeBindingSource, normalize_runtime_binding_source
from ccbd.services.runtime_recovery_policy import (
    PROVIDER_RECOVERY_BLOCKED_RUNTIME_HEALTHS,
    normalized_runtime_health,
)
from ccbd.services.project_inspection import load_project_daemon_inspection


def daemon_health(monitor, *, assume_socket_connectable: bool = False):
    lease_inspection = monitor._ownership_guard.inspect(
        assume_mounted_socket_connectable=assume_socket_connectable,
    )
    project_id = str(monitor._project_id or '').strip()
    lifecycle_store = monitor._lifecycle_store
    if not project_id or lifecycle_store is None:
        return lease_inspection
    return load_project_daemon_inspection(
        project_id,
        lease_inspection=lease_inspection,
        lifecycle_store=lifecycle_store,
        occurred_at=monitor._clock(),
    )


def check_all(monitor) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for runtime in monitor._registry.list_all():
        status = monitor._runtime_health(runtime)
        statuses[runtime.agent_name] = status
    return statuses


def collect_orphans(monitor) -> tuple[str, ...]:
    statuses = monitor.check_all()
    return tuple(sorted(name for name, status in statuses.items() if status != 'healthy'))


def runtime_health(monitor, runtime) -> str:
    binding_source = normalize_runtime_binding_source(
        getattr(runtime, 'binding_source', RuntimeBindingSource.PROVIDER_SESSION)
    )
    if runtime.state in {AgentState.STOPPED, AgentState.FAILED}:
        return runtime.health
    if (
        runtime.state is AgentState.DEGRADED
        and normalized_runtime_health(runtime) in PROVIDER_RECOVERY_BLOCKED_RUNTIME_HEALTHS
    ):
        return runtime.health
    pane_status = monitor._pane_health(runtime)
    if pane_status is not None:
        return pane_status
    if runtime.pid is not None and not monitor._pid_exists(runtime.pid):
        updated = _patch_runtime_state(
            monitor,
            runtime,
            state=AgentState.DEGRADED,
            health='orphaned',
            last_seen_at=monitor._clock(),
        )
        return updated.health
    if binding_source is RuntimeBindingSource.EXTERNAL_ATTACH:
        return runtime.health
    if runtime.state is AgentState.DEGRADED:
        return runtime.health
    if runtime.health not in {'healthy', 'restored'}:
        updated = _patch_runtime_state(
            monitor,
            runtime,
            health='healthy',
            last_seen_at=monitor._clock(),
        )
        return updated.health
    return runtime.health


def pane_health(monitor, runtime) -> str | None:
    binding_source = normalize_runtime_binding_source(
        getattr(runtime, 'binding_source', RuntimeBindingSource.PROVIDER_SESSION)
    )
    if binding_source is RuntimeBindingSource.EXTERNAL_ATTACH:
        return None
    return monitor._provider_pane_health(runtime)


def _patch_runtime_state(monitor, runtime, **updates):
    prior_health = getattr(runtime, 'health', None)
    prior_state = getattr(runtime, 'state', None)
    if monitor._runtime_service is not None:
        updated = monitor._runtime_service.patch_runtime_state(runtime, **updates)
    else:
        updated = replace(runtime, **updates)
        updated = monitor._registry.upsert(updated)
    _maybe_notify_webhook_health_change(monitor, updated, prior_health, prior_state)
    return updated


def _maybe_notify_webhook_health_change(monitor, runtime, prior_health, prior_state):
    webhook = getattr(monitor, '_webhook', None)
    if webhook is None:
        return
    new_health = getattr(runtime, 'health', None)
    new_state = getattr(runtime, 'state', None)
    # Notify when agent recovers from degraded/failed to healthy/idle
    if prior_health not in {'healthy', 'restored'} and new_health in {'healthy', 'restored'}:
        webhook.send(
            'agent.recovered',
            {
                'agent_name': runtime.agent_name,
                'prior_state': str(prior_state) if prior_state is not None else None,
                'prior_health': str(prior_health) if prior_health is not None else None,
                'state': str(new_state) if new_state is not None else None,
                'health': str(new_health) if new_health is not None else None,
                'pane_id': getattr(runtime, 'pane_id', None),
                'pane_state': getattr(runtime, 'pane_state', None),
            },
        )


__all__ = [
    'check_all',
    'collect_orphans',
    'daemon_health',
    'pane_health',
    'runtime_health',
]
