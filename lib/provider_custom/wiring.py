from __future__ import annotations

import os
from dataclasses import dataclass

# 模块级 import 安全：provider_command_defaults 只依赖 os/shlex，无循环。
from provider_command_defaults import (
    custom_provider_executable_snapshot,
    restore_custom_provider_executable_snapshot,
)

from .spec import CustomProviderSpec


@dataclass(frozen=True)
class CustomProviderWiring:
    provider: str
    key_env: str | None = None
    url_env: str | None = None
    model_env: str | None = None
    model_flag: str | None = None
    default_key: str | None = None
    default_url: str | None = None
    default_model: str | None = None


# 全局状态纪律（计划 Task 2 评审 R1 修订）：
# 1. 失败不留痕——配置校验入口在 parse 前 snapshot，失败时 restore。
# 2. 只读校验必还原——"只为验证而加载"的路径在 finally 中还原 snapshot。
# 3. 单项目假设——daemon 单项目单配置，publish-on-success 安全；CLI 多项目
#    交错加载以"最后一次成功 load 的项目"为准，需隔离的调用方自行 snapshot/restore。
# 4. 并发纪律——daemon 侧 mutate（sync/restore）只发生于 maintenance lock 持有期间；
#    CLI 进程单线程，无需额外锁。
_WIRINGS: dict[str, CustomProviderWiring] = {}


def sync_custom_provider_wirings(specs: dict[str, CustomProviderSpec]) -> None:
    _WIRINGS.clear()
    for name, spec in specs.items():
        _WIRINGS[name] = CustomProviderWiring(
            provider=name,
            key_env=spec.key_env,
            url_env=spec.url_env,
            model_env=spec.model_env,
            model_flag=spec.model_flag,
            default_key=spec.key,
            default_url=spec.url,
            default_model=spec.model,
        )


def custom_provider_wiring(provider: str) -> CustomProviderWiring | None:
    return _WIRINGS.get(str(provider or '').strip().lower())


def custom_provider_names() -> tuple[str, ...]:
    return tuple(sorted(_WIRINGS))


def snapshot_custom_provider_state() -> dict[str, object]:
    """捕获全部进程级自定义 provider 状态（wiring + 已注册 executable）。"""
    return {
        'wirings': dict(_WIRINGS),
        'executables': custom_provider_executable_snapshot(),
    }


def restore_custom_provider_state(snapshot: dict[str, object]) -> None:
    """恢复到 snapshot 时的状态；用于校验失败回滚与只读校验隔离。"""
    _WIRINGS.clear()
    _WIRINGS.update(snapshot.get('wirings') or {})
    restore_custom_provider_executable_snapshot(snapshot.get('executables'))


def resolve_env_value(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.startswith('$'):
        resolved = os.environ.get(text[1:], '')
        return resolved or None
    return text


__all__ = [
    'CustomProviderWiring',
    'custom_provider_names',
    'custom_provider_wiring',
    'resolve_env_value',
    'restore_custom_provider_state',
    'snapshot_custom_provider_state',
    'sync_custom_provider_wirings',
]
