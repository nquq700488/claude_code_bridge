from __future__ import annotations

from pathlib import Path

from provider_core.contracts import ProviderBackend

from .factory import build_custom_backends


def load_project_custom_backends(project_root) -> tuple[list[ProviderBackend], dict[str, str]]:
    from agents.config_loader import load_project_config  # 延迟 import 防循环

    result = load_project_config(Path(project_root))
    return build_custom_backends(result.config.custom_providers)


__all__ = ['load_project_custom_backends']
