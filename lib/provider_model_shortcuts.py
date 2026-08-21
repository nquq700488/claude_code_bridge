from __future__ import annotations

from provider_custom.wiring import custom_provider_names, custom_provider_wiring

_PROVIDER_MODEL_FLAGS = {
    'codex': ('-m', '--model'),
    'claude': ('--model',),
    'gemini': ('-m', '--model'),
    'opencode': ('-m', '--model'),
    'mimo': ('--model',),
}

_PROVIDER_MODEL_STARTUP_FLAGS = {
    'codex': '-m',
    'claude': '--model',
    'gemini': '-m',
    'opencode': '-m',
    'mimo': '--model',
}

_PROVIDER_MODEL_RUNTIME_ENV = {
    'deepseek': 'DEEPCODE_MODEL',
}

# These providers select the model through their structured control plane
# after startup rather than exposing a stable startup flag or environment key.
_PROVIDER_MODEL_CONTROL_PLANE = {'dsh'}


def supported_provider_model_shortcuts() -> tuple[str, ...]:
    names = (
        set(_PROVIDER_MODEL_FLAGS)
        | set(_PROVIDER_MODEL_RUNTIME_ENV)
        | set(_PROVIDER_MODEL_CONTROL_PLANE)
    )
    for name in custom_provider_names():
        wiring = custom_provider_wiring(name)
        if wiring is not None and (wiring.model_env or wiring.model_flag):
            names.add(name)
    return tuple(sorted(names))


def provider_model_flag_tokens(provider: str) -> tuple[str, ...]:
    wiring = custom_provider_wiring(provider)
    if wiring is not None:
        return (wiring.model_flag,) if wiring.model_flag else ()
    return _PROVIDER_MODEL_FLAGS.get(str(provider or '').strip().lower(), ())


def provider_model_startup_args(provider: str, *, model: str) -> tuple[str, ...]:
    normalized = str(provider or '').strip().lower()
    wiring = custom_provider_wiring(normalized)
    if wiring is not None:
        resolved_custom_model = str(model or '').strip()
        if not resolved_custom_model:
            raise ValueError('model cannot be empty')
        if wiring.model_flag:
            return (wiring.model_flag, resolved_custom_model)
        if wiring.model_env:
            return ()
        raise ValueError(f'custom provider {normalized} does not declare model wiring')
    flag = _PROVIDER_MODEL_STARTUP_FLAGS.get(normalized)
    if (
        flag is None
        and normalized not in _PROVIDER_MODEL_RUNTIME_ENV
        and normalized not in _PROVIDER_MODEL_CONTROL_PLANE
    ):
        supported = ', '.join(supported_provider_model_shortcuts())
        raise ValueError(f'model shortcut is supported only for providers: {supported}')
    resolved_model = str(model or '').strip()
    if not resolved_model:
        raise ValueError('model cannot be empty')
    if flag is None:
        return ()
    return (flag, resolved_model)


def provider_model_runtime_env(provider: str, *, model: str | None) -> dict[str, str]:
    normalized = str(provider or '').strip().lower()
    wiring = custom_provider_wiring(normalized)
    if wiring is not None:
        if model is None:
            return {}
        resolved_custom_model = str(model).strip()
        if not resolved_custom_model:
            raise ValueError('model cannot be empty')
        return {wiring.model_env: resolved_custom_model} if wiring.model_env else {}
    key = _PROVIDER_MODEL_RUNTIME_ENV.get(normalized)
    if key is None or model is None:
        return {}
    resolved_model = str(model).strip()
    if not resolved_model:
        raise ValueError('model cannot be empty')
    return {key: resolved_model}


def provider_model_runtime_env_keys(provider: str) -> set[str]:
    wiring = custom_provider_wiring(provider)
    if wiring is not None:
        return {wiring.model_env} if wiring.model_env else set()
    key = _PROVIDER_MODEL_RUNTIME_ENV.get(str(provider or '').strip().lower())
    return {key} if key is not None else set()


def startup_args_contain_model_flag(provider: str, startup_args: tuple[str, ...] | list[str]) -> bool:
    flags = set(provider_model_flag_tokens(provider))
    if not flags:
        return False
    for raw_arg in startup_args:
        arg = str(raw_arg)
        if arg in flags or arg.startswith('--model='):
            return True
    return False


def strip_provider_model_startup_args(
    provider: str,
    startup_args: tuple[str, ...] | list[str],
    *,
    model: str,
) -> tuple[str, ...]:
    compiled_prefix = provider_model_startup_args(provider, model=model)
    normalized_args = tuple(str(arg) for arg in startup_args)
    if not compiled_prefix:
        return normalized_args
    if normalized_args[: len(compiled_prefix)] == compiled_prefix:
        return normalized_args[len(compiled_prefix) :]
    return normalized_args


__all__ = [
    'provider_model_flag_tokens',
    'provider_model_startup_args',
    'provider_model_runtime_env',
    'provider_model_runtime_env_keys',
    'startup_args_contain_model_flag',
    'strip_provider_model_startup_args',
    'supported_provider_model_shortcuts',
]
