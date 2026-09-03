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
