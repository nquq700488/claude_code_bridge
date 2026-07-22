from __future__ import annotations

from dataclasses import dataclass, field

_VALID_TOPOLOGIES = frozenset({'hub-spoke', 'review-loop', 'mesh', 'debate'})


@dataclass(frozen=True)
class TeamMember:
    name: str
    provider: str
    role: str | None = None
    description: str | None = None
    model: str | None = None

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError('team member name cannot be empty')
        if not str(self.provider).strip():
            raise ValueError('team member provider cannot be empty')
        object.__setattr__(self, 'name', str(self.name).strip())
        object.__setattr__(self, 'provider', str(self.provider).strip().lower())
        if self.role is not None:
            object.__setattr__(self, 'role', str(self.role).strip() or None)
        if self.description is not None:
            object.__setattr__(self, 'description', str(self.description).strip() or None)
        if self.model is not None:
            object.__setattr__(self, 'model', str(self.model).strip() or None)


@dataclass(frozen=True)
class TeamPolicy:
    leader: str | None = None
    rounds_max: int = 3
    pass_score: float = 7.0
    synthesizer: str | None = None

    def __post_init__(self) -> None:
        if self.rounds_max < 1:
            raise ValueError('rounds_max must be >= 1')
        if not (0 < self.pass_score <= 10):
            raise ValueError('pass_score must be > 0 and <= 10')


class TeamValidationError(ValueError):
    pass


@dataclass(frozen=True)
class TeamSpec:
    name: str
    topology: str
    members: tuple[TeamMember, ...]
    description: str | None = None
    policy: TeamPolicy = field(default_factory=TeamPolicy)

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise TeamValidationError('team name cannot be empty')
        object.__setattr__(self, 'name', str(self.name).strip())

        topology = str(self.topology or '').strip().lower()
        if topology not in _VALID_TOPOLOGIES:
            raise TeamValidationError(
                f'invalid topology: {topology!r} (expected one of: '
                f'{", ".join(sorted(_VALID_TOPOLOGIES))})'
            )
        object.__setattr__(self, 'topology', topology)

        if len(self.members) < 2:
            raise TeamValidationError(f'team {self.name!r} requires at least 2 members')

        member_names = {m.name for m in self.members}
        if len(member_names) != len(self.members):
            raise TeamValidationError(f'team {self.name!r} has duplicate member names')

        if self.policy.leader is not None:
            leader = str(self.policy.leader).strip()
            if leader not in member_names:
                raise TeamValidationError(
                    f'team {self.name!r}: policy.leader {leader!r} is not a member'
                )

        if self.policy.synthesizer is not None:
            synthesizer = str(self.policy.synthesizer).strip()
            if synthesizer not in member_names:
                raise TeamValidationError(
                    f'team {self.name!r}: policy.synthesizer {synthesizer!r} is not a member'
                )

    def to_record(self) -> dict[str, object]:
        return {
            'name': self.name,
            'topology': self.topology,
            'description': self.description,
            'members': [
                {
                    'name': m.name,
                    'provider': m.provider,
                    'role': m.role,
                    'description': m.description,
                    'model': m.model,
                }
                for m in self.members
            ],
            'policy': {
                'leader': self.policy.leader,
                'rounds_max': self.policy.rounds_max,
                'pass_score': self.policy.pass_score,
                'synthesizer': self.policy.synthesizer,
            },
        }


__all__ = [
    'TeamMember',
    'TeamPolicy',
    'TeamSpec',
    'TeamValidationError',
]
