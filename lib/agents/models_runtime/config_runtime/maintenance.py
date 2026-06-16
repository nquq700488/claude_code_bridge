from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..names import AgentValidationError, normalize_agent_name

DEFAULT_MAINTENANCE_HEARTBEAT_ASSESSOR = 'ccb_self'
DEFAULT_MAINTENANCE_HEARTBEAT_INTERVAL_S = 3600
DEFAULT_MAINTENANCE_HEARTBEAT_MIN_INTERVAL_S = 300
DEFAULT_MAINTENANCE_HEARTBEAT_UNKNOWN_STREAK_CAP = 3
DEFAULT_MAINTENANCE_HEARTBEAT_ESCALATION_POLICY = 'report_only'
DEFAULT_JOB_HEARTBEAT_SILENCE_START_AFTER_S = 600
DEFAULT_JOB_HEARTBEAT_REPEAT_INTERVAL_S = 300
DEFAULT_JOB_HEARTBEAT_TERMINAL_NOTICE_COUNT = 3
MAINTENANCE_HEARTBEAT_ESCALATION_POLICIES = frozenset({'ask_user', 'report_only'})


@dataclass(frozen=True)
class MaintenanceHeartbeatConfig:
    enabled: bool = False
    assessor: str = DEFAULT_MAINTENANCE_HEARTBEAT_ASSESSOR
    interval_s: int = DEFAULT_MAINTENANCE_HEARTBEAT_INTERVAL_S
    min_interval_s: int = DEFAULT_MAINTENANCE_HEARTBEAT_MIN_INTERVAL_S
    unknown_streak_cap: int = DEFAULT_MAINTENANCE_HEARTBEAT_UNKNOWN_STREAK_CAP
    escalation_policy: str = DEFAULT_MAINTENANCE_HEARTBEAT_ESCALATION_POLICY
    startup_ensure: bool = True
    job_silence_start_after_s: int = DEFAULT_JOB_HEARTBEAT_SILENCE_START_AFTER_S
    job_repeat_interval_s: int = DEFAULT_JOB_HEARTBEAT_REPEAT_INTERVAL_S
    job_terminal_notice_count: int = DEFAULT_JOB_HEARTBEAT_TERMINAL_NOTICE_COUNT

    def __post_init__(self) -> None:
        try:
            assessor = normalize_agent_name(str(self.assessor or '').strip())
        except AgentValidationError as exc:
            raise AgentValidationError(f'maintenance.heartbeat.assessor invalid: {exc}') from exc
        enabled = _bool_value(self.enabled, field_name='maintenance.heartbeat.enabled')
        interval_s = _positive_int(self.interval_s, field_name='maintenance.heartbeat.interval_s')
        min_interval_s = _positive_int(self.min_interval_s, field_name='maintenance.heartbeat.min_interval_s')
        unknown_streak_cap = _positive_int(
            self.unknown_streak_cap,
            field_name='maintenance.heartbeat.unknown_streak_cap',
        )
        if min_interval_s > interval_s:
            raise AgentValidationError('maintenance.heartbeat.min_interval_s cannot exceed interval_s')
        escalation_policy = str(self.escalation_policy or '').strip().lower()
        if escalation_policy not in MAINTENANCE_HEARTBEAT_ESCALATION_POLICIES:
            allowed = ', '.join(sorted(MAINTENANCE_HEARTBEAT_ESCALATION_POLICIES))
            raise AgentValidationError(
                f'maintenance.heartbeat.escalation_policy must be one of: {allowed}'
            )
        startup_ensure = _bool_value(
            self.startup_ensure,
            field_name='maintenance.heartbeat.startup_ensure',
        )
        job_silence_start_after_s = _positive_int(
            self.job_silence_start_after_s,
            field_name='maintenance.heartbeat.job_silence_start_after_s',
        )
        job_repeat_interval_s = _positive_int(
            self.job_repeat_interval_s,
            field_name='maintenance.heartbeat.job_repeat_interval_s',
        )
        job_terminal_notice_count = _positive_int(
            self.job_terminal_notice_count,
            field_name='maintenance.heartbeat.job_terminal_notice_count',
        )
        object.__setattr__(self, 'enabled', enabled)
        object.__setattr__(self, 'assessor', assessor)
        object.__setattr__(self, 'interval_s', interval_s)
        object.__setattr__(self, 'min_interval_s', min_interval_s)
        object.__setattr__(self, 'unknown_streak_cap', unknown_streak_cap)
        object.__setattr__(self, 'escalation_policy', escalation_policy)
        object.__setattr__(self, 'startup_ensure', startup_ensure)
        object.__setattr__(self, 'job_silence_start_after_s', job_silence_start_after_s)
        object.__setattr__(self, 'job_repeat_interval_s', job_repeat_interval_s)
        object.__setattr__(self, 'job_terminal_notice_count', job_terminal_notice_count)

    def to_record(self) -> dict[str, Any]:
        return {
            'enabled': self.enabled,
            'assessor': self.assessor,
            'interval_s': self.interval_s,
            'min_interval_s': self.min_interval_s,
            'unknown_streak_cap': self.unknown_streak_cap,
            'escalation_policy': self.escalation_policy,
            'startup_ensure': self.startup_ensure,
            'job_silence_start_after_s': self.job_silence_start_after_s,
            'job_repeat_interval_s': self.job_repeat_interval_s,
            'job_terminal_notice_count': self.job_terminal_notice_count,
        }


def _bool_value(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise AgentValidationError(f'{field_name} must be a boolean')
    return value


def _positive_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise AgentValidationError(f'{field_name} must be a positive integer')
    if not isinstance(value, int):
        raise AgentValidationError(f'{field_name} must be a positive integer')
    if value <= 0:
        raise AgentValidationError(f'{field_name} must be a positive integer')
    return value


__all__ = [
    'DEFAULT_JOB_HEARTBEAT_REPEAT_INTERVAL_S',
    'DEFAULT_JOB_HEARTBEAT_SILENCE_START_AFTER_S',
    'DEFAULT_JOB_HEARTBEAT_TERMINAL_NOTICE_COUNT',
    'DEFAULT_MAINTENANCE_HEARTBEAT_ASSESSOR',
    'DEFAULT_MAINTENANCE_HEARTBEAT_ESCALATION_POLICY',
    'DEFAULT_MAINTENANCE_HEARTBEAT_INTERVAL_S',
    'DEFAULT_MAINTENANCE_HEARTBEAT_MIN_INTERVAL_S',
    'DEFAULT_MAINTENANCE_HEARTBEAT_UNKNOWN_STREAK_CAP',
    'MAINTENANCE_HEARTBEAT_ESCALATION_POLICIES',
    'MaintenanceHeartbeatConfig',
]
