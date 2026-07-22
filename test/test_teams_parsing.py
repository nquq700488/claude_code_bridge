from __future__ import annotations

import pytest

from teams.spec import TeamMember, TeamPolicy, TeamSpec, TeamValidationError


class TestTeamMember:
    def test_valid_member(self):
        m = TeamMember(name='coder', provider='claude', role='agentroles.general', model='sonnet')
        assert m.name == 'coder'
        assert m.provider == 'claude'
        assert m.role == 'agentroles.general'
        assert m.model == 'sonnet'

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match='name cannot be empty'):
            TeamMember(name='', provider='claude')

    def test_empty_provider_raises(self):
        with pytest.raises(ValueError, match='provider cannot be empty'):
            TeamMember(name='coder', provider='')

    def test_minimal_member(self):
        m = TeamMember(name='coder', provider='codex')
        assert m.role is None
        assert m.description is None
        assert m.model is None


class TestTeamPolicy:
    def test_defaults(self):
        p = TeamPolicy()
        assert p.leader is None
        assert p.rounds_max == 3
        assert p.pass_score == 7.0

    def test_rounds_max_validation(self):
        with pytest.raises(ValueError, match='rounds_max'):
            TeamPolicy(rounds_max=0)

    def test_pass_score_validation(self):
        with pytest.raises(ValueError, match='pass_score'):
            TeamPolicy(pass_score=0)
        with pytest.raises(ValueError, match='pass_score'):
            TeamPolicy(pass_score=11)


class TestTeamSpec:
    def _members(self, *names):
        return tuple(TeamMember(name=n, provider='claude') for n in names)

    def test_valid_spec(self):
        spec = TeamSpec(
            name='review-squad',
            topology='review-loop',
            members=self._members('leader', 'coder', 'reviewer'),
            description='Code review team',
            policy=TeamPolicy(leader='leader', rounds_max=3, pass_score=7.0),
        )
        assert spec.name == 'review-squad'
        assert spec.topology == 'review-loop'
        assert len(spec.members) == 3

    def test_min_members(self):
        with pytest.raises(TeamValidationError, match='at least 2 members'):
            TeamSpec(name='solo', topology='mesh', members=(TeamMember(name='x', provider='claude'),))

    def test_invalid_topology(self):
        with pytest.raises(TeamValidationError, match='invalid topology'):
            TeamSpec(name='t', topology='unknown', members=self._members('a', 'b'))

    def test_valid_topologies(self):
        for t in ('hub-spoke', 'review-loop', 'mesh', 'debate'):
            spec = TeamSpec(name='t', topology=t, members=self._members('a', 'b'))
            assert spec.topology == t

    def test_leader_must_be_member(self):
        with pytest.raises(TeamValidationError, match='not a member'):
            TeamSpec(
                name='t', topology='hub-spoke',
                members=self._members('a', 'b'),
                policy=TeamPolicy(leader='c'),
            )

    def test_synthesizer_must_be_member(self):
        with pytest.raises(TeamValidationError, match='not a member'):
            TeamSpec(
                name='t', topology='debate',
                members=self._members('a', 'b'),
                policy=TeamPolicy(synthesizer='c'),
            )

    def test_duplicate_member_names(self):
        with pytest.raises(TeamValidationError, match='duplicate member names'):
            TeamSpec(
                name='t', topology='mesh',
                members=(
                    TeamMember(name='a', provider='claude'),
                    TeamMember(name='a', provider='codex'),
                    TeamMember(name='b', provider='claude'),
                ),
            )

    def test_empty_name_raises(self):
        with pytest.raises(TeamValidationError, match='name cannot be empty'):
            TeamSpec(name='', topology='mesh', members=self._members('a', 'b'))

    def test_to_record(self):
        spec = TeamSpec(
            name='rs', topology='review-loop',
            members=(TeamMember(name='l', provider='claude', description='leader'), TeamMember(name='c', provider='codex')),
            policy=TeamPolicy(leader='l'),
        )
        rec = spec.to_record()
        assert rec['name'] == 'rs'
        assert rec['topology'] == 'review-loop'
        assert len(rec['members']) == 2
        assert rec['members'][0]['name'] == 'l'
        assert rec['policy']['leader'] == 'l'


from agents.config_loader_runtime.parsing_runtime.teams import parse_teams_section
from teams.spec import TeamSpec


def test_parse_teams_section_minimal():
    result = parse_teams_section({
        'myteam': {
            'topology': 'mesh',
            'members': [
                {'name': 'a', 'provider': 'claude'},
                {'name': 'b', 'provider': 'codex'},
            ],
        }
    })
    assert 'myteam' in result
    assert result['myteam'].topology == 'mesh'
    assert len(result['myteam'].members) == 2


def test_parse_teams_section_with_policy():
    result = parse_teams_section({
        't': {
            'topology': 'hub-spoke',
            'members': [{'name': 'l', 'provider': 'claude'}, {'name': 'w', 'provider': 'codex'}],
            'policy': {'leader': 'l', 'rounds_max': 5},
        }
    })
    assert result['t'].policy.leader == 'l'
    assert result['t'].policy.rounds_max == 5


def test_parse_teams_section_none_returns_empty():
    assert parse_teams_section(None) == {}
