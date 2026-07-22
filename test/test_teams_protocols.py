from __future__ import annotations
import pytest
from teams.protocols import render_team_protocol
from teams.spec import TeamMember, TeamPolicy, TeamSpec


def _team(**kw):
    defaults = dict(name='t', topology='mesh', members=(
        TeamMember(name='a', provider='claude'),
        TeamMember(name='b', provider='codex'),
    ))
    defaults.update(kw)
    return TeamSpec(**defaults)


class TestProtocolRendering:
    def test_all_members_get_protocol(self):
        team = _team()
        protocols = render_team_protocol(team)
        assert set(protocols.keys()) == {'a', 'b'}
        for text in protocols.values():
            assert 'Team: t' in text
            assert 'Topology: mesh' in text
            assert 'Your Role' in text

    def test_mesh_contains_mesh_header(self):
        protocols = render_team_protocol(_team(topology='mesh'))
        for text in protocols.values():
            assert 'Mesh Protocol' in text

    def test_hub_spoke_leader_gets_leader_steps(self):
        team = _team(
            topology='hub-spoke',
            policy=TeamPolicy(leader='a'),
        )
        protocols = render_team_protocol(team)
        assert 'Hub-Spoke Protocol' in protocols['a']
        assert 'leader' in protocols['a']
        assert 'leader' not in protocols['b'].lower() or 'Wait for the leader' in protocols['b']

    def test_review_loop_includes_pass_threshold(self):
        team = _team(
            topology='review-loop',
            members=(
                TeamMember(name='l', provider='claude'),
                TeamMember(name='coder', provider='codex'),
                TeamMember(name='reviewer', provider='gemini'),
            ),
            policy=TeamPolicy(leader='l', pass_score=8.0, rounds_max=5),
        )
        protocols = render_team_protocol(team)
        assert '8.0' in protocols['l']
        assert 'coder' in protocols['coder'].lower() or 'implement' in protocols['coder'].lower()
        assert 'reviewer' in protocols['reviewer'].lower() or 'score' in protocols['reviewer'].lower()

    def test_debate_synthesizer_role(self):
        team = _team(
            topology='debate',
            members=(
                TeamMember(name='s', provider='claude'),
                TeamMember(name='p1', provider='codex'),
            ),
            policy=TeamPolicy(synthesizer='s'),
        )
        protocols = render_team_protocol(team)
        assert 'synthesizer' in protocols['s'].lower()
        assert 'independently' in protocols['p1'].lower()

    def test_roster_lists_all_members(self):
        team = _team(members=(
            TeamMember(name='alice', provider='claude', description='Architect'),
            TeamMember(name='bob', provider='codex', description='Coder'),
        ))
        protocols = render_team_protocol(team)
        for text in protocols.values():
            assert 'alice' in text
            assert 'bob' in text
            assert 'Architect' in text
            assert 'Coder' in text

    def test_communication_section_present(self):
        protocols = render_team_protocol(_team())
        for text in protocols.values():
            assert '/ask' in text
            assert '/pend' in text
