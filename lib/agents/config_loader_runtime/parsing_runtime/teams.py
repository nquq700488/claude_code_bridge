from __future__ import annotations

from typing import Any

from teams.spec import TeamMember, TeamPolicy, TeamSpec


def parse_teams_section(raw_teams: Any) -> dict[str, TeamSpec]:
    if raw_teams is None:
        return {}
    if not isinstance(raw_teams, dict):
        raise ValueError(f'teams must be a mapping, got {type(raw_teams).__name__}')
    teams: dict[str, TeamSpec] = {}
    for name, raw in raw_teams.items():
        if not isinstance(raw, dict):
            raise ValueError(f'teams.{name} must be a mapping')
        raw_members = raw.get('members')
        if not isinstance(raw_members, list) or len(raw_members) < 2:
            raise ValueError(f'teams.{name}.members must be a list with at least 2 entries')
        members = tuple(
            TeamMember(
                name=m['name'],
                provider=m['provider'],
                role=m.get('role'),
                description=m.get('description'),
                model=m.get('model'),
            )
            for m in raw_members
        )
        raw_policy = raw.get('policy')
        policy_dict = raw_policy if isinstance(raw_policy, dict) else {}
        policy = TeamPolicy(
            leader=policy_dict.get('leader'),
            rounds_max=int(policy_dict.get('rounds_max', 3)),
            pass_score=float(policy_dict.get('pass_score', 7.0)),
            synthesizer=policy_dict.get('synthesizer'),
        )
        teams[name] = TeamSpec(
            name=name,
            description=raw.get('description'),
            topology=raw.get('topology', 'mesh'),
            members=members,
            policy=policy,
        )
    return teams


__all__ = ['parse_teams_section']
