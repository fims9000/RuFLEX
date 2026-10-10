from fastapi.testclient import TestClient
from pathlib import Path

import pandas as pd

from ruflex.api.main import app


def test_model_catalog_exposes_capabilities_without_claiming_unavailable_adapters() -> None:
    response = TestClient(app).get("/api/model-catalog")
    assert response.status_code == 200
    entries = {entry["key"]: entry for entry in response.json()}
    assert entries["mamdani"]["available"] is True
    assert entries["mamdani"]["capabilities"]["exact_semantic_trace"] is True
    assert entries["decision_tree"]["available"] is True
    assert entries["decision_tree"]["capabilities"]["exact_tree_path"] is True
    assert entries["decision_tree"]["capabilities"]["exact_semantic_trace"] is False
    assert entries["linear"]["available"] is True
    assert entries["linear"]["capabilities"]["fit"] is True


def test_model_runtime_contract_exposes_explicit_xai_and_task_support() -> None:
    response = TestClient(app).get("/api/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == 1
    entries = {entry["key"]: entry for entry in payload["models"]}
    tree = entries["decision_tree"]
    assert tree["available"] is True
    assert tree["capabilities"]["exact_tree_path"] is True
    assert "tree_shap" in tree["supported_explainers"]
    assert "integrated_gradients" not in tree["supported_explainers"]
    assert "binary_classification" in tree["supported_tasks"]
    assert "multiclass_classification" not in tree["supported_tasks"]
    assert tree["defaults"]["max_depth"] is None
    assert tree["parameter_constraints"]["max_depth"]["nullable"] is True
    assert entries["linear"]["training_model_kinds"] == ["logistic_regression", "linear_regression"]
    assert entries["linear"]["model_kind_tasks"] == {
        "logistic_regression": ["binary_classification"],
        "linear_regression": ["regression"],
    }
    neuro_fuzzy = entries["flat_neuro_fuzzy"]
    assert neuro_fuzzy["defaults"]["max_rules"] == 8
    assert neuro_fuzzy["optional_dependencies"] == ["torch"]


def test_plugin_lookup_fails_closed() -> None:
    client = TestClient(app)
    assert client.get("/api/plugins/native_explanation_validator").status_code == 200
    missing = client.get("/api/plugins/not_registered")
    assert missing.status_code == 404
    assert missing.json()["code"] == "CAPABILITY_UNAVAILABLE"


def test_model_lookup_resolves_concrete_training_keys_and_rejects_unknown() -> None:
    client = TestClient(app)
    linear = client.get("/api/models/logistic_regression")
    assert linear.status_code == 200
    assert linear.json()["key"] == "linear"
    missing = client.get("/api/models/no_such_model")
    assert missing.status_code == 404
    assert missing.json()["code"] == "CAPABILITY_UNAVAILABLE"


def test_training_rejects_unknown_model_through_runtime_capability_contract(tmp_path: Path) -> None:
    client = TestClient(app)
    session_id = client.post("/api/projects", json={"path": str(tmp_path / "unknown"), "name": "Unknown"}).json()["session_id"]
    response = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "not_a_model"})
    assert response.status_code == 422
    assert response.json()["code"] == "CAPABILITY_UNAVAILABLE"


def test_training_rejects_adapter_key_incompatible_with_concrete_model(tmp_path: Path) -> None:
    client = TestClient(app)
    session_id = client.post("/api/projects", json={"path": str(tmp_path / "incompatible"), "name": "Incompatible"}).json()["session_id"]
    response = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "decision_tree", "adapter_key": "native_linear"})
    assert response.status_code == 422
    assert response.json()["code"] == "RUNTIME_INCOMPATIBLE"
    assert response.json()["detail"]["code"] == "RUNTIME_INCOMPATIBLE"


def test_run_capability_negotiation_is_bound_to_the_persisted_model_artifact(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "capabilities"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Capabilities"}).json()["session_id"]
    frame = pd.DataFrame({"x": range(30), "y": [index % 3 for index in range(30)], "target": [index % 2 for index in range(30)]})
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": frame.to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": 42, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert trained.status_code == 201, trained.text

    response = client.get(f"/api/projects/{session_id}/training/runs/{trained.json()['run_id']}/capabilities")

    assert response.status_code == 200, response.text
    payload = response.json()
    decisions = {decision["capability"]: decision for decision in payload["decisions"]}
    assert payload["model_artifact_sha256"] == trained.json()["model_artifact_sha256"]
    assert decisions["occlusion"]["status"] == "AVAILABLE"
    assert decisions["tree_shap"]["reason_code"] == "CAPABILITY_UNAVAILABLE"
    assert decisions["exact_tree_path"]["status"] == "NOT_APPLICABLE"


def test_runtime_tree_parameters_reach_the_canonical_training_adapter(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "tree-runtime"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Tree runtime"}).json()["session_id"]
    frame = pd.DataFrame({"x": range(40), "y": [index % 5 for index in range(40)], "target": [index % 2 for index in range(40)]})
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": frame.to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    response = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "decision_tree", "seed": 42, "max_depth": 1})
    assert response.status_code == 201, response.text
    assert response.json()["model_spec"]["max_depth"] <= 1
