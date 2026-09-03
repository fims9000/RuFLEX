from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from ruflex.api.main import app
from ruflex.sdk.studio import open_studio_project


_MAMDANI = """[System]
Name='integrity-tipper'
Type='mamdani'
AndMethod='min'
OrMethod='max'
ImpMethod='min'
AggMethod='max'
DefuzzMethod='centroid'
[Input1]
Name='service'
Range=[0 10]
MF1='low':'trimf',[0 0 10]
[Output1]
Name='tip'
Range=[0 1]
MF1='low':'trimf',[0 0 1]
[Rules]
1, 1 (1) : 1
"""


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


def test_project_integrity_rejects_tampered_train_only_preprocessing_artifact(tmp_path: Path) -> None:
    client = TestClient(app); root = tmp_path / "preprocessing-integrity"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Preprocessing"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _frame(), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": 42, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3}).json()
    assert trained["preprocessing_artifact_sha256"]
    artifact = root / "artifacts" / "sha256" / trained["preprocessing_artifact_sha256"][:2] / trained["preprocessing_artifact_sha256"]
    artifact.unlink()
    report = client.get(f"/api/projects/{session_id}/integrity").json()
    assert report["status"] == "FAIL"
    assert any(issue["code"] == "PREPROCESSING_ARTIFACT_INVALID" for issue in report["issues"])


def test_project_integrity_checks_imported_matlab_fis_provenance(tmp_path: Path) -> None:
    client = TestClient(app); root = tmp_path / "fis-import-integrity"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "FIS import integrity"}).json()["session_id"]
    imported = client.post("/api/projects/fis/import/matlab", json={"session_id": session_id, "source": _MAMDANI})
    assert imported.status_code == 200, imported.text
    assert client.get(f"/api/projects/{session_id}/integrity").json()["status"] == "PASS"
    receipt_path = root / "models" / "fis" / "imports" / f"{imported.json()['spec']['fis_id']}.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["semantic_hash"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    report = client.get(f"/api/projects/{session_id}/integrity").json()
    assert report["status"] == "FAIL"
    assert any(issue["code"] == "IMPORTED_FIS_SEMANTIC_MISMATCH" for issue in report["issues"])


def test_project_integrity_rejects_detached_persisted_explanation_evidence(tmp_path: Path) -> None:
    client = TestClient(app); root = tmp_path / "explanation-integrity"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Explanation integrity"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _frame(), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    run = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": 42, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3}).json()
    explanation = client.post("/api/projects/evidence/explanations/occlusion", json={"session_id": session_id, "run_id": run["run_id"], "sample": {"temperature": 20.0, "torque": 40.0}}).json()
    path = root / "evidence" / "explanations" / f"{explanation['explanation_id']}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["model_artifact_sha256"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")
    report = client.get(f"/api/projects/{session_id}/integrity").json()
    assert report["status"] == "FAIL"
    assert any(issue["code"] == "EXPLANATION_MODEL_MISMATCH" for issue in report["issues"])
