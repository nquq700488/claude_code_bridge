from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CustomProviderSpec:
    name: str
    mode: str  # 'pane' | 'oneshot'
    command: str
    description: str | None = None
    completion: str | None = None  # pane: 'marker'|'quiet'; oneshot: 'exit'|'marker'
    marker: str = 'CCB_DONE:'
    quiet_secs: float = 4.0
    prompt_mode: str | None = None  # oneshot: 'arg'|'stdin'
    timeout_secs: int = 300
    env: dict[str, str] = field(default_factory=dict)
    home_env: str | None = None
    key: str | None = None
    url: str | None = None
    model: str | None = None
    key_env: str | None = None
    url_env: str | None = None
    model_env: str | None = None
    model_flag: str | None = None

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            'name': self.name,
            'mode': self.mode,
            'command': self.command,
            'completion': self.completion,
            'marker': self.marker,
            'quiet_secs': self.quiet_secs,
            'timeout_secs': self.timeout_secs,
            'env': dict(self.env),
        }
        for field_name in (
            'description', 'prompt_mode', 'home_env',
            'key', 'url', 'model', 'key_env', 'url_env', 'model_env', 'model_flag',
        ):
            value = getattr(self, field_name)
            if value is not None:
                record[field_name] = value
        return record


__all__ = ['CustomProviderSpec']
