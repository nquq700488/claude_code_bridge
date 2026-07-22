from __future__ import annotations

import pytest

from provider_core.registry import build_default_backend_registry
from provider_core.catalog import build_default_provider_catalog
from provider_custom.factory import build_custom_backends
from provider_custom.parsing import parse_providers_section
from provider_custom.wiring import restore_custom_provider_state


@pytest.fixture(autouse=True)
def _clean():
    yield
    restore_custom_provider_state({'wirings': {}, 'executables': {}})


def _specs():
    return parse_providers_section({
        'aider': {'mode': 'pane', 'command': 'aider', 'completion': 'quiet'},
        'px': {'mode': 'oneshot', 'command': 'px run', 'prompt_mode': 'arg', 'completion': 'exit'},
    })


def test_build_custom_backends_both_modes():
    backends, errors = build_custom_backends(_specs())
    assert errors == {}
    assert {b.provider for b in backends} == {'aider', 'px'}


def test_registry_accepts_extra_backends():
    backends, _ = build_custom_backends(_specs())
    registry = build_default_backend_registry(extra_backends=backends)
    assert registry.get('aider') is not None
    assert registry.get('px') is not None
    assert registry.get('claude') is not None  # 内置仍在


def test_catalog_lookup_custom_provider():
    backends, _ = build_custom_backends(_specs())
    catalog = build_default_provider_catalog(extra_backends=backends)
    assert catalog.get('aider').provider == 'aider'
    with pytest.raises(KeyError):
        catalog.get('nonexistent')


def test_duplicate_name_rejected():
    backends, _ = build_custom_backends(_specs())
    with pytest.raises(ValueError, match='duplicate'):
        build_default_backend_registry(extra_backends=[*backends, *backends])
