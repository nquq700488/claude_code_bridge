from __future__ import annotations

import pytest

from agents.config_loader import load_project_config
from agents.config_loader_runtime.common import ConfigValidationError


_V2_BASE = '''version = 2
default_agents = ["main"]

[agents.main]
provider = "claude"
target = "main"
workspace_mode = "inplace"
restore = "auto"
permission = "manual"
'''


def _write_project(tmp_path, text: str):
    root = tmp_path / 'proj'
    (root / '.ccb').mkdir(parents=True)
    (root / '.ccb' / 'ccb.config').write_text(text, encoding='utf-8')
    return root


def test_providers_section_parses_pane_and_oneshot(tmp_path):
    root = _write_project(tmp_path, _V2_BASE + '''
[providers.aider]
mode = "pane"
command = "aider --no-auto-commits"
completion = "marker"
quiet_secs = 6
env = { AIDER_TELEMETRY = "0" }
home_env = "AIDER_HOME"
key = "$AIDER_API_KEY"
key_env = "OPENAI_API_KEY"
model = "gpt-5"
model_env = "AIDER_MODEL"

[providers.px]
mode = "oneshot"
command = "px run --format text"
prompt_mode = "arg"
completion = "exit"
timeout_secs = 120
''')
    config = load_project_config(root, include_loop_overlays=False).config
    aider = config.custom_providers['aider']
    assert aider.mode == 'pane'
    assert aider.completion == 'marker'
    assert aider.quiet_secs == 6.0
    assert aider.marker == 'CCB_DONE:'
    assert aider.env == {'AIDER_TELEMETRY': '0'}
    assert aider.key == '$AIDER_API_KEY'
    assert aider.key_env == 'OPENAI_API_KEY'
    px = config.custom_providers['px']
    assert px.mode == 'oneshot'
    assert px.prompt_mode == 'arg'
    assert px.timeout_secs == 120


def test_no_providers_section_loads_identically(tmp_path):
    root = _write_project(tmp_path, _V2_BASE)
    config = load_project_config(root, include_loop_overlays=False).config
    assert config.custom_providers == {}
    assert 'providers' not in config.to_record()


@pytest.mark.parametrize('extra, fragment', [
    ('[providers.claude]\nmode = "pane"\ncommand = "x"\ncompletion = "marker"\n', 'reserved'),
    ('[providers.aider]\nmode = "bogus"\ncommand = "x"\n', 'mode'),
    ('[providers.aider]\nmode = "pane"\ncompletion = "marker"\n', 'command'),
    ('[providers.aider]\nmode = "pane"\ncommand = "x"\n', 'completion'),
    ('[providers.aider]\nmode = "pane"\ncommand = "x"\ncompletion = "marker"\nprompt_mode = "arg"\n', 'prompt_mode'),
    ('[providers.aider]\nmode = "oneshot"\ncommand = "x"\ncompletion = "exit"\n', 'prompt_mode'),
    ('[providers.aider]\nmode = "oneshot"\ncommand = "x"\nprompt_mode = "arg"\ncompletion = "bogus"\n', 'completion'),
    ('[providers.aider]\nmode = "pane"\ncommand = "x"\ncompletion = "marker"\nkey = "sk-1"\n', 'key_env'),
    ('[providers.aider]\nmode = "pane"\ncommand = "x"\ncompletion = "marker"\nmodel = "m1"\n', 'model_env'),
    ('[providers.aider]\nmode = "pane"\ncommand = "x"\ncompletion = "marker"\nmodel_env = "M"\nmodel_flag = "--model"\n', 'model_env'),
    ('[providers.aider]\nmode = "pane"\ncommand = "x"\ncompletion = "marker"\nthinking = "high"\n', 'unknown'),
    ('[providers."bad name"]\nmode = "pane"\ncommand = "x"\ncompletion = "marker"\n', 'name must match'),
    ('[providers.aider]\nmode = "pane"\ncommand = "x"\ncompletion = "marker"\nkey_env = "1BAD"\nkey = "k"\n', 'environment variable name'),
    ('[providers.aider]\nmode = "pane"\ncommand = "x"\ncompletion = "marker"\nmodel = "m"\nmodel_flag = "--model x"\n', 'model_flag'),
    ('[providers.aider]\nmode = "pane"\ncommand = "x"\ncompletion = "marker"\nenv = { "BAD-NAME" = "1" }\n', 'environment variable name'),
])
def test_providers_section_validation_errors(tmp_path, extra, fragment):
    root = _write_project(tmp_path, _V2_BASE + extra)
    with pytest.raises(ConfigValidationError) as exc_info:
        load_project_config(root, include_loop_overlays=False)
    assert 'providers.' in str(exc_info.value)
    assert fragment in str(exc_info.value)
