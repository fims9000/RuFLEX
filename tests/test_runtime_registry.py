from __future__ import annotations

import pytest
import inspect
from fastapi.testclient import TestClient

from ruflex.api.main import app
from ruflex.application.training import train_model
from ruflex.runtime import builtin_runtime_registry
from ruflex.runtime.contracts import RuntimeIdentity
from ruflex.runtime.errors import RuntimeNotFoundError, RuntimeVersionMismatchError


def test_builtin_runtime_snapshot_is_frozen_and_deterministic() -> None:
    registry = builtin_runtime_registry()
    first = registry.snapshot()
    assert first["frozen"] is True
    assert [entry["identity"]["key"] for entry in first["models"]] == [
        "ruflex_flat_neuro_fuzzy",
        "sklearn_decision_tree",
        "sklearn_gradient_boosting",
        "sklearn_linear",
        "sklearn_random_forest",
    ]
    assert first == registry.snapshot()


def test_runtime_resolution_fails_closed() -> None:
    registry = builtin_runtime_registry()
    with pytest.raises(RuntimeNotFoundError) as missing:
        registry.resolve_model_adapter("missing")
    assert missing.value.code == "RUNTIME_NOT_FOUND"
    with pytest.raises(RuntimeVersionMismatchError) as mismatch:
        registry.resolve_model_adapter("sklearn_decision_tree", version="99")
    assert mismatch.value.code == "RUNTIME_VERSION_MISMATCH"


def test_runtime_identity_is_immutable() -> None:
    identity = RuntimeIdentity(key="fixture_adapter", version="1", provider="ruflex.fixture", kind="model_adapter")
    with pytest.raises(Exception):
        identity.key = "different"  # type: ignore[misc]


def test_runtime_api_exposes_frozen_snapshot_and_typed_lookup() -> None:
    client = TestClient(app)
    snapshot = client.get("/api/runtime")
    assert snapshot.status_code == 200
    assert snapshot.json()["frozen"] is True
    models = client.get("/api/runtime/models")
    assert models.status_code == 200
    assert {item["identity"]["key"] for item in models.json()} >= {"sklearn_decision_tree", "sklearn_linear"}
    assert client.get("/api/runtime/models/sklearn_decision_tree").status_code == 200
    assert client.get("/api/runtime/explainers/occlusion").status_code == 200
    assert client.get("/api/runtime/validators/native_explanation_validator").status_code == 200
    missing = client.get("/api/runtime/models/missing")
    assert missing.status_code == 422
    assert missing.json()["detail"]["code"] == "RUNTIME_NOT_FOUND"


def test_runtime_api_declares_explainers_validator_and_backend() -> None:
    client = TestClient(app)
    assert {item["identity"]["key"] for item in client.get("/api/runtime/explainers").json()} >= {"occlusion", "tree_shap", "integrated_gradients"}
    assert client.get("/api/runtime/validators").json()[0]["identity"]["key"] == "native_explanation_validator"
    assert client.get("/api/runtime/backends").json()[0]["identity"]["key"] == "local_executor"


def test_training_entrypoint_has_no_model_name_dispatch() -> None:
    source = inspect.getsource(train_model)
    assert "if model_kind ==" not in source
    assert "elif model_kind" not in source
    assert "resolve_training_model_kind" in source
