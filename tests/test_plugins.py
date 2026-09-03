from __future__ import annotations

import pytest

from ruflex.plugins import PluginContractError, PluginDescriptor, PluginRegistry


class _Plugin:
    key = "fixture_validator"
    version = "1"


def _descriptor(**changes) -> PluginDescriptor:
    payload = {"key": "fixture_validator", "version": "1", "kind": "explanation_validator"}
    payload.update(changes)
    return PluginDescriptor(**payload)


def test_plugin_registry_requires_a_matching_trusted_descriptor() -> None:
    registry = PluginRegistry()
    implementation = _Plugin()
    registry.register(_descriptor(), implementation)

    assert registry.descriptor("fixture_validator").kind == "explanation_validator"
    assert registry.implementation("fixture_validator") is implementation
    with pytest.raises(PluginContractError, match="already registered"):
        registry.register(_descriptor(), implementation)


def test_plugin_registry_fails_closed_for_unregistered_or_mismatched_plugins() -> None:
    registry = PluginRegistry()
    with pytest.raises(PluginContractError, match="unavailable"):
        registry.descriptor("missing_plugin")
    with pytest.raises(PluginContractError, match="does not match"):
        registry.register(_descriptor(version="2"), _Plugin())
