from __future__ import annotations

import re
import shlex
from pathlib import Path

from provider_backends.native_cli_support import (
    NativeCliExecutionConfig,
    NativeCliLaunchConfig,
    NativeCliObservation,
    NativeCliSubprocessAdapter,
    build_native_cli_manifest,
    build_native_cli_runtime_launcher,
    build_native_session_binding,
    observe_stdout_output,
)
from provider_command_defaults import register_custom_provider_executable
from provider_core.contracts import ProviderBackend

from .env import build_oneshot_env_builder, provider_level_env
from .spec import CustomProviderSpec
from .wiring import resolve_env_value


def build_custom_oneshot_backend(spec: CustomProviderSpec) -> ProviderBackend:
    argv = shlex.split(spec.command)
    register_custom_provider_executable(spec.name, argv[0])
    prompt_via_stdin = spec.prompt_mode == 'stdin'
    session_filename = f'.{spec.name}-session'
    # provider 级默认 model + model_flag：装配进每次执行的命令行
    # （agent 级 model shortcut 经 startup_args 仍优先生效于 pane 启动；
    #  oneshot 每次执行都是新进程，provider 默认值必须进 command_builder）
    default_model = resolve_env_value(spec.model)
    if spec.model_flag and default_model:
        argv = [*argv, spec.model_flag, default_model]

    def command_builder(request) -> list[str]:
        if prompt_via_stdin:
            return list(argv)
        return [*argv, request.prompt]

    observer = observe_stdout_output
    if spec.completion == 'marker':
        observer = _make_marker_observer(spec.marker)

    return ProviderBackend(
        manifest=build_native_cli_manifest(provider=spec.name),
        execution_adapter=NativeCliSubprocessAdapter(
            NativeCliExecutionConfig(
                provider=spec.name,
                session_filename=session_filename,
                command_builder=command_builder,
                env_builder=build_oneshot_env_builder(spec),
                observer=observer,
                output_kind='text',
                mode=f'{spec.name}_run',
                run_timeout_s=float(spec.timeout_secs),
                prompt_via_stdin=prompt_via_stdin,
            )
        ),
        session_binding=build_native_session_binding(provider=spec.name, session_filename=session_filename),
        runtime_launcher=build_native_cli_runtime_launcher(
            NativeCliLaunchConfig(
                provider=spec.name,
                home_env=spec.home_env,
                visible_args=tuple(argv[1:]),
                visible_env_builder=lambda _context: provider_level_env(spec),
            )
        ),
    )


def _make_marker_observer(marker: str):
    marker_text = str(marker or '').strip() or 'CCB_DONE:'
    done_re = re.compile(rf'^\s*{re.escape(marker_text)}')

    def observe(path: Path) -> NativeCliObservation:
        base = observe_stdout_output(path)
        if base.error or not base.text:
            return base
        lines = base.text.splitlines()
        for index, line in enumerate(lines):
            if done_re.match(line):
                body = '\n'.join(lines[:index]).strip()
                # finish_reason 必须用适配器 _STOP_REASONS 认可的值（execution.py:34
                # 含 'done'）——自定义值会被判为 INCOMPLETE 而非 COMPLETED（评审 R2 核实）
                return NativeCliObservation(text=body, finished=True, finish_reason='done')
        return NativeCliObservation(text=base.text.strip())

    return observe


__all__ = ['build_custom_oneshot_backend']
