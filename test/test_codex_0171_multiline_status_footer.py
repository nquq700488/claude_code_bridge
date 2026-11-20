"""Codex 0.171.0 renders an extra native status row above the shortcut hint.

The composer itself is unchanged (`› Ask Codex to do anything` at the initial
cursor), but the footer block grew from "status row + hint row" to "status row +
status row + hint row", and 0.171.0 also stopped dimming those rows.  The old
recognizer required every row under the first status row to be a shortcut hint,
so a healthy empty composer was reported as `composer_layout_unknown` and every
dispatch to that pane stayed queued.
"""
from __future__ import annotations

import pytest

from provider_execution.draft_observation import inspect_screen

PLACEHOLDER = 'Ask Codex to do anything'


def screen(*, footer, composer=('', PLACEHOLDER), body=('• Worked for 5s',)):
    lines = [*body, '', '› ' + composer[1], composer[0], *footer]
    return {
        'text': '\n'.join(lines) + '\n',
        'cursor_x': 2,
        'cursor_y': len(body) + 1,
    }


THREE_ROW_FOOTER = [
    '  GPT-6.1-Sol xhigh · workspace · feature/winter-correct',
    '  Token usage',
    '  ? for shortcuts                            100% Context left',
]


def test_three_row_status_footer_releases_empty_composer():
    observation = inspect_screen('codex', screen(footer=THREE_ROW_FOOTER), binding='pane')

    assert observation.state == 'empty'
    assert observation.reason == 'codex_placeholder'


def test_two_row_status_footer_still_releases_empty_composer():
    observation = inspect_screen(
        'codex',
        screen(footer=THREE_ROW_FOOTER[:1] + THREE_ROW_FOOTER[2:]),
        binding='pane',
    )

    assert observation.state == 'empty'


def test_single_hint_row_footer_still_releases_empty_composer():
    observation = inspect_screen('codex', screen(footer=['  ? for shortcuts']), binding='pane')

    assert observation.state == 'empty'


def test_extra_status_rows_never_authorize_a_typed_draft():
    # The relaxed rule is only trusted for the untouched native placeholder; a
    # typed draft must stay fail-closed rather than let the footer boundary be
    # inferred from prose.
    observation = inspect_screen(
        'codex',
        screen(footer=THREE_ROW_FOOTER, composer=('', 'refactor the parser')),
        binding='pane',
    )

    assert observation.state == 'unknown'
    assert observation.reason == 'composer_layout_unknown'


def test_extra_status_row_must_be_native_indented_chrome():
    footer = [
        '  GPT-6.1-Sol xhigh · workspace · feature/winter-correct',
        'draft continuation without indentation',
        '  ? for shortcuts',
    ]

    observation = inspect_screen('codex', screen(footer=footer), binding='pane')

    assert observation.state == 'unknown'
    assert observation.reason == 'composer_layout_unknown'


def test_extra_status_rows_require_the_native_hint_anchor():
    # Without the trailing native hint the block boundary is unproven: the last
    # row is an unrecognized status line, so the old strict rule still applies.
    footer = [
        '  GPT-6.1-Sol xhigh · workspace · feature/winter-correct',
        '  Token usage',
        '  something else entirely',
    ]

    observation = inspect_screen('codex', screen(footer=footer), binding='pane')

    assert observation.state == 'unknown'
    assert observation.reason == 'composer_layout_unknown'


def test_status_rows_without_a_field_separator_are_not_trusted():
    footer = [
        '  model and workspace and branch',
        '  Token usage',
        '  ? for shortcuts',
    ]

    observation = inspect_screen('codex', screen(footer=footer), binding='pane')

    assert observation.state == 'unknown'
    assert observation.reason == 'composer_layout_unknown'


@pytest.mark.parametrize('hint', [
    '  ? for shortcuts',
    '  ? for shortcuts                        100% Context left',
    '  ← for agents · ? for shortcuts',
    '  ? for shortcuts                        ⚠ 2 warnings · f2 to view',
])
def test_hint_grammar_variants_stay_accepted(hint):
    footer = [THREE_ROW_FOOTER[0], THREE_ROW_FOOTER[1], hint]

    assert inspect_screen('codex', screen(footer=footer), binding='pane').state == 'empty'