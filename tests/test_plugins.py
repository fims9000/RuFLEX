from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ruflex.api.main import app
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


def test_studio_exposes_only_registered_plugin_descriptors() -> None:
    response = TestClient(app).get("/api/plugins")

    assert response.status_code == 200
    assert response.json() == [{
        "key": "native_explanation_validator",
        "version": "1",
        "kind": "explanation_validator",
        "capabilities": {"provenance_identity": True, "replay_integrity": True, "quantitative_quality": True},
        "config_schema": {"type": "object", "additionalProperties": False},
        "input_schema": {"explanation_id": "UUID", "project_root": "canonical_project_root"},
        "output_schema": {"ExplanationCheck": "schema_version=2"},
        "trusted": True,
        "scientific_note": "Registered plugins are inspected product integrations, not arbitrary executable uploads.",
    }]
