from __future__ import annotations

from dataclasses import replace

from agents.models import AgentState
from ccbd.services.runtime_recovery_policy import RUNTIME_RECOVERY_PROBING_HEALTH
from provider_core.session_binding_evidence import session_ref

from .common import drop_explicit_runtime_fields, runtime_fields_from_facts


def rebind_runtime(
    monitor,
    runtime,
    session,
    binding,
    *,
    pane_id_override: str | None = None,
    force_session_ref_update: bool = False,
):
    prior_health = getattr(runtime, 'health', None)
    prior_state = getattr(runtime, 'state', None)
    facts = monitor._provider_runtime_facts(
        runtime,
        session,
        binding,
        pane_id_override=pane_id_override,
    )
    pane_id = _bound_pane_id(facts=facts, pane_id_override=pane_id_override, session=session)
    bound_session_ref = _bound_session_ref(facts=facts, session=session, binding=binding)
    next_session_ref = _next_session_ref(
        runtime=runtime,
        bound_session_ref=bound_session_ref,
        force_session_ref_update=force_session_ref_update,
    )
    updated_fields = _updated_runtime_fields(runtime=runtime, facts=facts)
    if monitor._runtime_service is not None:
        rebound = monitor._runtime_service.mutate_runtime_authority(
            runtime,
            pid=_next_pid(runtime=runtime, facts=facts),
            session_ref=next_session_ref,
            health=_next_health(runtime),
            pane_id=pane_id or runtime.pane_id,
            active_pane_id=pane_id or runtime.active_pane_id,
            pane_state='alive',
            **updated_fields,
        )
        updated = monitor._runtime_service.patch_runtime_state(
            rebound,
            state=_next_state(runtime),
            last_seen_at=monitor._clock(),
        )
    else:
        updated = replace(
            runtime,
            state=_next_state(runtime),
            pid=_next_pid(runtime=runtime, facts=facts),
            session_ref=next_session_ref,
            health=_next_health(runtime),
            pane_id=pane_id or runtime.pane_id,
            active_pane_id=pane_id or runtime.active_pane_id,
            pane_state='alive',
            last_seen_at=monitor._clock(),
            **updated_fields,
        )
        upsert_authority = getattr(monitor._registry, 'upsert_authority', None)
        if callable(upsert_authority):
            updated = upsert_authority(updated)
        else:
            updated = monitor._registry.upsert(updated)
    _maybe_notify_webhook_rebind(monitor, updated, prior_health, prior_state)
    return updated


def _maybe_notify_webhook_rebind(monitor, runtime, prior_health, prior_state):
    webhook = getattr(monitor, '_webhook', None)
    if webhook is None:
        return
    new_health = getattr(runtime, 'health', None)
    new_state = getattr(runtime, 'state', None)
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


def _bound_pane_id(*, facts, pane_id_override: str | None, session) -> str | None:
    if facts is not None:
        return facts.pane_id
    return str(pane_id_override or getattr(session, 'pane_id', '') or '').strip() or None


def _bound_session_ref(*, facts, session, binding) -> str | None:
    if facts is not None:
        return facts.session_ref
    return session_ref(
        session,
        session_id_attr=binding.session_id_attr,
        session_path_attr=binding.session_path_attr,
    )


def _next_session_ref(*, runtime, bound_session_ref: str | None, force_session_ref_update: bool) -> str | None:
    if force_session_ref_update:
        return bound_session_ref
    return runtime.session_ref or bound_session_ref


def _next_state(runtime):
    if _recovery_probe_active(runtime):
        return AgentState.DEGRADED
    return runtime.state if runtime.state is not AgentState.DEGRADED else AgentState.IDLE


def _next_health(runtime) -> str:
    if _recovery_probe_active(runtime):
        return RUNTIME_RECOVERY_PROBING_HEALTH
    if runtime.state is not AgentState.DEGRADED and runtime.health == 'restored':
        return 'restored'
    return 'healthy'


def _recovery_probe_active(runtime) -> bool:
    return str(getattr(runtime, 'reconcile_state', '') or '').strip() == 'probing'


def _next_pid(*, runtime, facts) -> int | None:
    if facts is not None and facts.runtime_pid is not None:
        return facts.runtime_pid
    return runtime.pid


def _updated_runtime_fields(*, runtime, facts) -> dict[str, object]:
    if facts is None:
        return {}
    return drop_explicit_runtime_fields(
        runtime_fields_from_facts(runtime, facts),
        explicit_fields=(
            'active_pane_id',
            'health',
            'last_seen_at',
            'pane_id',
            'pane_state',
            'pid',
            'session_ref',
            'state',
        ),
    )


__all__ = ['rebind_runtime']
