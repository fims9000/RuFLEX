from __future__ import annotations

import pytest
import inspect
from fastapi.testclient import TestClient
from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

from ruflex.api.main import app
from ruflex.application.training import train_model
from ruflex.runtime import builtin_runtime_registry
from ruflex.runtime.errors import RuntimeNotFoundError, RuntimeVersionMismatchError
from ruflex.runtime.errors import RuntimeDependencyMissingError, RuntimeUntrustedError
from ruflex.runtime.contracts import (
    ExecutionBackendDescriptor,
    ExplainerDescriptor,
    ExplainerResult,
    RuntimeIdentity,
    ModelAdapterDescriptor,
)
from dataclasses import dataclass


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
    assert [item["identity"]["key"] for item in first["explainers"]] == [
        "gradient_shap", "integrated_gradients", "occlusion", "shap", "tree_shap",
    ]
    assert first["validators"][0]["identity"]["key"] == "native_explanation_validator"
    assert first["backends"][0]["identity"]["key"] == "local_executor"


def test_runtime_resolution_fails_closed() -> None:
    registry = builtin_runtime_registry()
    with pytest.raises(RuntimeNotFoundError) as missing:
        registry.resolve_model_adapter("missing")
    assert missing.value.code == "RUNTIME_NOT_FOUND"
    with pytest.raises(RuntimeVersionMismatchError) as mismatch:
        registry.resolve_model_adapter("sklearn_decision_tree", version="99")
    assert mismatch.value.code == "RUNTIME_VERSION_MISMATCH"
    with pytest.raises(RuntimeNotFoundError):
        registry.resolve_component("explainer", "missing")


def test_runtime_identity_is_immutable() -> None:
    identity = RuntimeIdentity(key="fixture_adapter", version="1", provider="ruflex.fixture", kind="model_adapter")
    with pytest.raises(Exception):
        identity.key = "different"  # type: ignore[misc]


@dataclass(frozen=True)
class _UnavailableDependencyAdapter:
    descriptor = ModelAdapterDescriptor(
        identity=RuntimeIdentity(key="dependency_fixture", version="1", provider="ruflex.tests", kind="model_adapter"),
        family="fixture", training_model_kinds=("dependency_fixture_model",), supported_tasks=("binary_classification",),
        optional_dependencies=("ruflex_dependency_that_cannot_exist",),
    )
    def fit(self, request): raise AssertionError("not reached")
    def predict(self, request): raise AssertionError("not reached")


def test_registry_rejects_missing_dependencies_and_untrusted_adapters() -> None:
    from ruflex.runtime.registry import RuntimeRegistry
    registry = RuntimeRegistry()
    with pytest.raises(RuntimeDependencyMissingError):
        registry.register_model_adapter(_UnavailableDependencyAdapter())
    with pytest.raises(RuntimeUntrustedError):
        registry.register_model_adapter(_UnavailableDependencyAdapter(), trusted=False)


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


def test_posthoc_api_accepts_a_runtime_explainer_key_before_runtime_resolution() -> None:
    client = TestClient(app)
    session_id = client.post("/api/projects", json={"path": f"/tmp/ruflex-runtime-explainer-key-{uuid4()}", "name": "runtime key"}).json()["session_id"]
    response = client.post("/api/projects/evidence/explanations", json={
        "session_id": session_id, "run_id": str(UUID(int=1)), "sample": {"x": 1.0}, "method": "fixture_explainer",
    })
    assert response.status_code == 422
    assert response.json()["detail"] != "Input should be 'occlusion', 'integrated_gradients', 'gradient_shap', 'shap' or 'tree_shap'"


def test_training_entrypoint_has_no_model_name_dispatch() -> None:
    source = inspect.getsource(train_model)
    assert "if model_kind ==" not in source
    assert "elif model_kind" not in source
    assert "resolve_training_model_kind" in source


def test_explanation_and_validator_entrypoints_resolve_typed_runtime_implementations() -> None:
    from ruflex.application.evidence import check_explanation, create_runtime_explanation

    explainer_source = inspect.getsource(create_runtime_explanation)
    validator_source = inspect.getsource(check_explanation)
    assert "resolve_component_implementation" in explainer_source
    assert "builders =" not in explainer_source
    assert "resolve_component_implementation" in validator_source


def test_category_specific_explainer_entrypoint_is_registered_as_a_component(monkeypatch) -> None:
    from ruflex.runtime.registry import RuntimeRegistry
    class FixtureExplainer:
        descriptor = ExplainerDescriptor(identity=RuntimeIdentity(key="fixture_explainer", version="1", provider="ruflex.tests", kind="explainer"), supported_tasks=("binary_classification",))
        def supports(self, *, run_capabilities, task, artifact): return True, None
        def explain(self, request): return ExplainerResult(explanation={"fixture": True})
    class Point:
        name = "fixture_explainer"
        def load(self): return FixtureExplainer
    class Points:
        def select(self, *, group): return [Point()] if group == "ruflex.explainers" else []
    monkeypatch.setattr("ruflex.runtime.registry.metadata.entry_points", lambda: Points())
    registry = RuntimeRegistry()
    discovered = registry.discover_entry_points(group="ruflex.explainers")
    assert [item.identity.key for item in discovered] == ["fixture_explainer"]
    assert registry.resolve_component_implementation("explainer", "fixture_explainer").descriptor.identity.kind == "explainer"


def test_category_specific_execution_backend_entrypoint_has_full_lifecycle_contract(monkeypatch) -> None:
    from ruflex.runtime.registry import RuntimeRegistry

    class FixtureExecutionBackend:
        descriptor = ExecutionBackendDescriptor(
            identity=RuntimeIdentity(
                key="fixture_execution_backend", version="1", provider="ruflex.tests", kind="execution_backend",
            ),
            supports_cancel=True,
            supports_resume=True,
        )

        def submit(self, *, project_root: Path, job_id: UUID, operation: Callable[[], None]) -> bool:
            operation()
            return True

        def is_active(self, *, project_root: Path, job_id: UUID) -> bool:
            return False

        def status(self, *, project_root: Path, job_id: UUID) -> str:
            return "IDLE"

        def cancel(self, *, project_root: Path, job_id: UUID) -> bool:
            return True

        def resume(self, *, project_root: Path, job_id: UUID, operation: Callable[[], None]) -> bool:
            return self.submit(project_root=project_root, job_id=job_id, operation=operation)

    class Point:
        name = "fixture_execution_backend"

        def load(self):
            return FixtureExecutionBackend

    class Points:
        def select(self, *, group):
            return [Point()] if group == "ruflex.execution_backends" else []

    monkeypatch.setattr("ruflex.runtime.registry.metadata.entry_points", lambda: Points())
    registry = RuntimeRegistry()
    discovered = registry.discover_entry_points(group="ruflex.execution_backends")
    assert [item.identity.key for item in discovered] == ["fixture_execution_backend"]
    backend = registry.resolve_component_implementation("execution_backend", "fixture_execution_backend")
    completed: list[bool] = []
    assert backend.submit(project_root=Path("/tmp"), job_id=UUID(int=1), operation=lambda: completed.append(True)) is True
    assert completed == [True]
    assert backend.status(project_root=Path("/tmp"), job_id=UUID(int=1)) == "IDLE"
    assert backend.cancel(project_root=Path("/tmp"), job_id=UUID(int=1)) is True
    assert backend.resume(project_root=Path("/tmp"), job_id=UUID(int=1), operation=lambda: completed.append(True)) is True
    assert completed == [True, True]


def test_registry_rejects_directly_registered_partial_execution_backend() -> None:
    from ruflex.runtime.registry import RuntimeRegistry

    class PartialBackend:
        descriptor = ExecutionBackendDescriptor(
            identity=RuntimeIdentity(
                key="partial_execution_backend", version="1", provider="ruflex.tests", kind="execution_backend",
            ),
        )

        def submit(self, *, project_root: Path, job_id: UUID, operation: Callable[[], None]) -> bool:
            return True

    with pytest.raises(TypeError, match="complete ExecutionBackendAdapter contract"):
        RuntimeRegistry().register_component(PartialBackend.descriptor, implementation=PartialBackend())
