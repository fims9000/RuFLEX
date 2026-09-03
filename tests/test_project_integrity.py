from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from ruflex.api.main import app
from ruflex.sdk.studio import open_studio_project


def _frame() -> str:
    rows = [{"temperature": 10 + index, "torque": 20 + 3 * index, "target": int(index > 8)} for index in range(32)]
    return pd.DataFrame(rows).to_csv(index=False)


def test_project_integrity_survives_reopen_and_reports_missing_frozen_model_artifact(tmp_path: Path) -> None:
    client = TestClient(app); root = tmp_path / "integrity"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Integrity"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _frame(), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": 42, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert trained.status_code == 201, trained.text
    assert client.get(f"/api/projects/{session_id}/integrity").json()["status"] == "PASS"
    assert client.post("/api/projects/close", json={"session_id": session_id}).status_code == 204
    reopened = client.post("/api/projects/open", json={"path": str(root), "read_only": True}).json()["session_id"]
    assert client.get(f"/api/projects/{reopened}/integrity").json()["status"] == "PASS"
    run = trained.json(); artifact = root / "artifacts" / "sha256" / run["model_artifact_sha256"][:2] / run["model_artifact_sha256"]
    artifact.unlink()
    report = client.get(f"/api/projects/{reopened}/integrity").json()
    assert report["status"] == "FAIL"
    assert any(issue["code"] == "MODEL_ARTIFACT_INVALID" for issue in report["issues"])
    assert open_studio_project(root).integrity().status == "FAIL"
