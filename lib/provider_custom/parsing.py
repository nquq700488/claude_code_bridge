from __future__ import annotations

import re
from typing import Any

from .spec import CustomProviderSpec


class CustomProviderConfigError(ValueError):
    pass


def _reserved_provider_names() -> frozenset[str]:
    # 延迟 import：provider_core/__init__ 会拉起 cli.context -> project.resolver，
    # 而 project.resolver 又依赖配置加载链路——模块级 import 会形成循环。
    from provider_core.registry_runtime.builtin_backends import CORE_PROVIDER_NAMES, OPTIONAL_PROVIDER_NAMES
    from provider_core.registry_runtime.test_double_backends import TEST_DOUBLE_PROVIDER_NAMES

    return frozenset(
        (*CORE_PROVIDER_NAMES, *OPTIONAL_PROVIDER_NAMES, *TEST_DOUBLE_PROVIDER_NAMES)
    )


_PROVIDER_NAME_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,63}$')
_ENV_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

_ALLOWED_KEYS = {
    'description', 'mode', 'command', 'completion', 'marker', 'quiet_secs',
    'prompt_mode', 'timeout_secs', 'env', 'home_env',
    'key', 'url', 'model', 'key_env', 'url_env', 'model_env', 'model_flag',
}
_PANE_COMPLETIONS = {'marker', 'quiet'}
_ONESHOT_COMPLETIONS = {'exit', 'marker'}
_PROMPT_MODES = {'arg', 'stdin'}


def parse_providers_section(raw: object) -> dict[str, CustomProviderSpec]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise CustomProviderConfigError('providers must be a table of [providers.<name>] sections')
    specs: dict[str, CustomProviderSpec] = {}
    for raw_name, raw_table in raw.items():
        name = _parse_name(raw_name)
        specs[name] = _parse_one(name, raw_table)
    return specs


def _parse_name(raw_name: object) -> str:
    name = str(raw_name or '').strip().lower()
    if not name:
        raise CustomProviderConfigError('providers.<name>: name cannot be empty')
    if not _PROVIDER_NAME_RE.match(name):
        raise CustomProviderConfigError(
            f'providers.{name}: name must match {_PROVIDER_NAME_RE.pattern} '
            '(lowercase alnum and dashes, used in file/env names)'
        )
    if name in _reserved_provider_names():
        raise CustomProviderConfigError(
            f'providers.{name}: name is reserved by a builtin provider'
        )
    return name


def _parse_one(name: str, raw_table: object) -> CustomProviderSpec:
    path = f'providers.{name}'
    if not isinstance(raw_table, dict):
        raise CustomProviderConfigError(f'{path}: must be a table')
    unknown = sorted(set(raw_table) - _ALLOWED_KEYS)
    if unknown:
        raise CustomProviderConfigError(f'{path}: unknown fields: {", ".join(unknown)}')
    mode = _required_choice(raw_table, 'mode', {'pane', 'oneshot'}, path)
    command = _required_string(raw_table, 'command', path)
    completion = raw_table.get('completion')
    prompt_mode = raw_table.get('prompt_mode')
    if mode == 'pane':
        completion = _required_choice(raw_table, 'completion', _PANE_COMPLETIONS, path)
        if prompt_mode is not None:
            raise CustomProviderConfigError(f'{path}.prompt_mode: only valid for oneshot mode')
    else:
        prompt_mode = _required_choice(raw_table, 'prompt_mode', _PROMPT_MODES, path)
        completion = _required_choice(raw_table, 'completion', _ONESHOT_COMPLETIONS, path)
        if 'quiet_secs' in raw_table:
            raise CustomProviderConfigError(f'{path}.quiet_secs: only valid for pane mode')
    key = _optional_string(raw_table, 'key', path)
    url = _optional_string(raw_table, 'url', path)
    model = _optional_string(raw_table, 'model', path)
    key_env = _optional_string(raw_table, 'key_env', path)
    url_env = _optional_string(raw_table, 'url_env', path)
    model_env = _optional_string(raw_table, 'model_env', path)
    model_flag = _optional_string(raw_table, 'model_flag', path)
    if key is not None and key_env is None:
        raise CustomProviderConfigError(f'{path}.key: requires key_env to declare wiring')
    if url is not None and url_env is None:
        raise CustomProviderConfigError(f'{path}.url: requires url_env to declare wiring')
    if model is not None and model_env is None and model_flag is None:
        raise CustomProviderConfigError(f'{path}.model: requires model_env or model_flag to declare wiring')
    if model_env is not None and model_flag is not None:
        raise CustomProviderConfigError(f'{path}: model_env and model_flag are mutually exclusive')
    if model_flag is not None and (model_flag != model_flag.strip() or ' ' in model_flag or not model_flag.startswith('-')):
        raise CustomProviderConfigError(f'{path}.model_flag: must be a single CLI flag token (e.g. --model)')
    for env_name, field_name in (
        (key_env, 'key_env'), (url_env, 'url_env'), (model_env, 'model_env'),
        (_optional_string(raw_table, 'home_env', path), 'home_env'),
    ):
        if env_name is not None and not _ENV_NAME_RE.match(env_name):
            raise CustomProviderConfigError(f'{path}.{field_name}: invalid environment variable name: {env_name!r}')
    env = raw_table.get('env') or {}
    if not isinstance(env, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in env.items()):
        raise CustomProviderConfigError(f'{path}.env: must be a string->string table')
    for env_key in env:
        if not _ENV_NAME_RE.match(env_key):
            raise CustomProviderConfigError(f'{path}.env: invalid environment variable name: {env_key!r}')
    return CustomProviderSpec(
        name=name,
        mode=mode,
        command=command,
        description=_optional_string(raw_table, 'description', path),
        completion=completion,
        marker=_optional_string(raw_table, 'marker', path) or 'CCB_DONE:',
        quiet_secs=_optional_positive_float(raw_table, 'quiet_secs', path, default=4.0),
        prompt_mode=prompt_mode,
        timeout_secs=_optional_positive_int(raw_table, 'timeout_secs', path, default=300),
        env={str(k): str(v) for k, v in env.items()},
        home_env=_optional_string(raw_table, 'home_env', path),
        key=key,
        url=url,
        model=model,
        key_env=key_env,
        url_env=url_env,
        model_env=model_env,
        model_flag=model_flag,
    )


def _required_string(table: dict[str, Any], key: str, path: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CustomProviderConfigError(f'{path}.{key}: required non-empty string')
    return value.strip()


def _optional_string(table: dict[str, Any], key: str, path: str) -> str | None:
    value = table.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise CustomProviderConfigError(f'{path}.{key}: must be a non-empty string')
    return value.strip()


def _required_choice(table: dict[str, Any], key: str, choices: set[str], path: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or value.strip().lower() not in choices:
        raise CustomProviderConfigError(
            f'{path}.{key}: must be one of {sorted(choices)}'
        )
    return value.strip().lower()


def _optional_positive_float(table: dict[str, Any], key: str, path: str, *, default: float) -> float:
    value = table.get(key)
    if value is None:
        return float(default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise CustomProviderConfigError(f'{path}.{key}: must be a positive number')
    return float(value)


def _optional_positive_int(table: dict[str, Any], key: str, path: str, *, default: int) -> int:
    value = table.get(key)
    if value is None:
        return int(default)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise CustomProviderConfigError(f'{path}.{key}: must be a positive integer')
    return int(value)


__all__ = ['CustomProviderConfigError', 'parse_providers_section']
