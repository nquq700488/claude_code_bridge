from __future__ import annotations

from provider_core.contracts import ProviderBackend

from .oneshot import build_custom_oneshot_backend
from .pane import build_custom_pane_backend
from .spec import CustomProviderSpec


def build_custom_backends(
    providers: dict[str, CustomProviderSpec],
) -> tuple[list[ProviderBackend], dict[str, str]]:
    backends: list[ProviderBackend] = []
    errors: dict[str, str] = {}
    for name, spec in providers.items():
        try:
            if spec.mode == 'oneshot':
                backends.append(build_custom_oneshot_backend(spec))
            else:
                backends.append(build_custom_pane_backend(spec))
        except Exception as exc:  # 单个 provider 组装失败不拖垮其余
            errors[name] = f'{type(exc).__name__}: {exc}'
    return backends, errors


__all__ = ['build_custom_backends']
