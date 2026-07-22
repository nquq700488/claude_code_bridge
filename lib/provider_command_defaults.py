from __future__ import annotations

import os
import shlex


_PROVIDER_START_ENV_VARS = {
    'codex': 'CODEX_START_CMD',
    'claude': 'CLAUDE_START_CMD',
    'gemini': 'GEMINI_START_CMD',
    'opencode': 'OPENCODE_START_CMD',
    'droid': 'DROID_START_CMD',
    'agy': 'AGY_START_CMD',
    'kimi': 'KIMI_START_CMD',
    'mmx': 'MMX_START_CMD',
    'deepseek': 'DEEPSEEK_START_CMD',
    'mimo': 'MIMO_START_CMD',
    'qwen': 'QWEN_START_CMD',
    'cursor': 'CURSOR_START_CMD',
    'copilot': 'COPILOT_START_CMD',
    'crush': 'CRUSH_START_CMD',
    'grok': 'GROK_START_CMD',
    'kiro': 'KIRO_START_CMD',
    'pi': 'PI_START_CMD',
    'omp': 'OMP_START_CMD',
    'zai': 'ZAI_START_CMD',
}

_PROVIDER_DEFAULT_EXECUTABLES = {
    'codex': 'codex',
    'claude': 'claude',
    'gemini': 'gemini',
    'opencode': 'opencode',
    'droid': 'droid',
    'agy': 'agy',
    'kimi': 'kimi',
    'mmx': 'mmx-daemon',
    'deepseek': 'deepcode',
    'mimo': 'mimo',
    'qwen': 'qwen',
    'cursor': 'agent',
    'copilot': 'copilot',
    'crush': 'crush',
    'grok': 'grok',
    'kiro': 'kiro-cli',
    'pi': 'pi',
    'omp': 'omp',
    'zai': 'zai',
}

SUPPORTED_PROVIDER_NAMES = tuple(_PROVIDER_DEFAULT_EXECUTABLES)


def provider_start_env_vars() -> tuple[str, ...]:
    return tuple(_PROVIDER_START_ENV_VARS.values())


def provider_start_parts(provider: str) -> list[str]:
    normalized = str(provider or '').strip().lower()
    env_name = _PROVIDER_START_ENV_VARS.get(normalized)
    raw = str(os.environ.get(env_name or '') or '').strip() if env_name else ''
    if raw:
        try:
            parts = shlex.split(raw)
        except ValueError:
            parts = [raw]
        if parts:
            return [str(part) for part in parts]
    default = _PROVIDER_DEFAULT_EXECUTABLES.get(normalized, normalized)
    return [default]


def provider_executable(provider: str) -> str:
    parts = provider_start_parts(provider)
    return str(parts[0] or provider)


_CUSTOM_EXECUTABLE_NAMES: set[str] = set()


def register_custom_provider_executable(provider: str, executable: str) -> None:
    normalized = str(provider or '').strip().lower()
    executable = str(executable or '').strip()
    if not normalized or not executable:
        return
    if normalized in _PROVIDER_DEFAULT_EXECUTABLES and normalized not in _CUSTOM_EXECUTABLE_NAMES:
        return  # 内置名不可覆盖
    _PROVIDER_DEFAULT_EXECUTABLES[normalized] = executable
    _PROVIDER_START_ENV_VARS.setdefault(
        normalized, f"{normalized.upper().replace('-', '_')}_START_CMD"
    )
    _CUSTOM_EXECUTABLE_NAMES.add(normalized)


def custom_provider_executable_snapshot() -> dict[str, str]:
    return {
        name: _PROVIDER_DEFAULT_EXECUTABLES[name]
        for name in _CUSTOM_EXECUTABLE_NAMES
        if name in _PROVIDER_DEFAULT_EXECUTABLES
    }


def restore_custom_provider_executable_snapshot(snapshot: dict[str, str] | None) -> None:
    for name in tuple(_CUSTOM_EXECUTABLE_NAMES):
        _PROVIDER_DEFAULT_EXECUTABLES.pop(name, None)
        _PROVIDER_START_ENV_VARS.pop(name, None)
    _CUSTOM_EXECUTABLE_NAMES.clear()
    for name, executable in dict(snapshot or {}).items():
        register_custom_provider_executable(name, executable)


__all__ = [
    'SUPPORTED_PROVIDER_NAMES',
    'custom_provider_executable_snapshot',
    'provider_executable',
    'provider_start_env_vars',
    'provider_start_parts',
    'register_custom_provider_executable',
    'restore_custom_provider_executable_snapshot',
]
