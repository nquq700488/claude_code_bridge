from __future__ import annotations

import shlex
from pathlib import Path

from ccbd.api_models import JobRecord
from provider_backends.native_cli_support import (
    NativeCliLaunchConfig,
    build_native_cli_manifest,
    build_native_cli_runtime_launcher,
    build_native_session_binding,
)
from provider_backends.pane_quiet_support import poll_submission, start_submission
from provider_command_defaults import register_custom_provider_executable
from provider_core.contracts import ProviderBackend
from provider_execution.base import ProviderPollResult, ProviderRuntimeContext, ProviderSubmission

from .env import provider_level_env
from .spec import CustomProviderSpec
from .wiring import resolve_env_value


class CustomPaneExecutionAdapter:
    _COMPLETION_MODES = {'marker': 'marker_only', 'quiet': 'quiet_only'}

    def __init__(self, spec: CustomProviderSpec, *, load_project_session_fn) -> None:
        self._spec = spec
        self._load_project_session_fn = load_project_session_fn
        self._completion_mode = self._COMPLETION_MODES[str(spec.completion or 'quiet')]

    def start(self, job: JobRecord, *, context: ProviderRuntimeContext | None, now: str) -> ProviderSubmission:
        return start_submission(
            job,
            context=context,
            now=now,
            provider=self._spec.name,
            load_project_session_fn=self._load_project_session_fn,
            quiet_secs=float(self._spec.quiet_secs),
            done_prefix=self._spec.marker,
            completion_mode=self._completion_mode,
        )

    def poll(self, submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
        return poll_submission(submission, now=now)

    def cancel(self, submission: ProviderSubmission) -> None:
        return None

    def export_runtime_state(self, submission: ProviderSubmission) -> dict[str, object]:
        return dict(submission.runtime_state)

    def resume(self, *args, **kwargs) -> None:
        return None

    def restore_diagnostics(self) -> dict[str, object]:
        return {'resume_supported': False, 'restore_mode': 'resubmit_required'}


def build_custom_pane_backend(spec: CustomProviderSpec) -> ProviderBackend:
    argv = shlex.split(spec.command)
    register_custom_provider_executable(spec.name, argv[0])
    session_filename = f'.{spec.name}-session'
    session_binding = build_native_session_binding(provider=spec.name, session_filename=session_filename)
    # provider 级默认 model + model_flag 进常驻进程启动参数；
    # agent 级 model shortcut（startup_args）在其后追加，CLI 侧通常后写优先 → agent 覆盖 provider 默认
    visible_args = list(argv[1:])
    default_model = resolve_env_value(spec.model)
    if spec.model_flag and default_model:
        visible_args.extend([spec.model_flag, default_model])

    def _load_project_session(work_dir, instance=None):
        return session_binding.load_session(Path(work_dir), instance)

    return ProviderBackend(
        manifest=build_native_cli_manifest(provider=spec.name),
        execution_adapter=CustomPaneExecutionAdapter(spec, load_project_session_fn=_load_project_session),
        session_binding=session_binding,
        runtime_launcher=build_native_cli_runtime_launcher(
            NativeCliLaunchConfig(
                provider=spec.name,
                home_env=spec.home_env,
                visible_args=tuple(visible_args),
                visible_env_builder=lambda _context: provider_level_env(spec),
            )
        ),
    )


__all__ = ['CustomPaneExecutionAdapter', 'build_custom_pane_backend']
