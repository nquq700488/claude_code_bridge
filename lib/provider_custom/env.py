from __future__ import annotations

from pathlib import Path

from provider_profiles.materializer import load_resolved_provider_profile

from .spec import CustomProviderSpec
from .wiring import resolve_env_value


def provider_level_env(spec: CustomProviderSpec) -> dict[str, str]:
    env: dict[str, str] = {}
    key = resolve_env_value(spec.key)
    if key and spec.key_env:
        env[spec.key_env] = key
    url = resolve_env_value(spec.url)
    if url and spec.url_env:
        env[spec.url_env] = url
    model = resolve_env_value(spec.model)
    if model and spec.model_env:
        env[spec.model_env] = model
    env.update(spec.env)
    return env


def build_oneshot_env_builder(spec: CustomProviderSpec):
    base = provider_level_env(spec)
    _model_env = spec.model_env

    def env_builder(request) -> dict[str, str]:
        env = dict(base)
        env.update(_profile_env(request.session_data))
        # agent 级 model_env 覆盖：job.provider_options 中 model_env+model
        # 替代 provider 默认值（Code Review R1 critical #2 — env builder 侧）
        provider_opts = dict(getattr(getattr(request, 'job', None), 'provider_options', None) or {})
        agent_model_env = str(provider_opts.get('model_env') or '').strip()
        agent_model = str(provider_opts.get('model') or '').strip()
        if agent_model_env and agent_model:
            env[agent_model_env] = agent_model
        return env

    return env_builder


def _profile_env(session_data: dict) -> dict[str, str]:
    runtime_dir = str(session_data.get('runtime_dir') or '').strip()
    if not runtime_dir:
        return {}
    try:
        profile = load_resolved_provider_profile(Path(runtime_dir))
    except Exception:
        return {}
    if profile is None:
        return {}
    return dict(getattr(profile, 'env', {}) or {})


__all__ = ['build_oneshot_env_builder', 'provider_level_env']
