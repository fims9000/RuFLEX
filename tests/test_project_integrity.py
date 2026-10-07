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


def test_project_integrity_rejects_validation_evaluation_detached_from_frozen_run(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "validation-evaluation-integrity"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Validation Evaluation integrity"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _frame(), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": 48, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert trained.status_code == 201, trained.text
    evaluation = client.post("/api/projects/analyses/evaluations", json={"session_id": session_id, "run_id": trained.json()["run_id"]})
    assert evaluation.status_code == 201, evaluation.text
    evaluation_id = evaluation.json()["evaluation_id"]
    calibration = client.post("/api/projects/analyses/calibrations", json={"session_id": session_id, "evaluation_id": evaluation_id})
    assert calibration.status_code == 201, calibration.text
    threshold = client.post("/api/projects/analyses/thresholds", json={"session_id": session_id, "evaluation_id": evaluation_id, "calibration_id": None, "objective": "f1"})
    assert threshold.status_code == 201, threshold.text
    selective = client.post("/api/projects/analyses/selective-policies", json={"session_id": session_id, "evaluation_id": evaluation_id, "confidence_cutoff": .7, "calibration_id": None, "threshold_id": threshold.json()["threshold_id"]})
    assert selective.status_code == 201, selective.text
    assert client.get(f"/api/projects/{session_id}/integrity").json()["status"] == "PASS"
    path = root / "analyses" / "evaluations" / f"{evaluation_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["model_artifact_sha256"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")

    report = client.get(f"/api/projects/{session_id}/integrity").json()

    assert report["status"] == "FAIL"
    assert any(issue["code"] == "VALIDATION_EVALUATION_PROVENANCE_MISMATCH" for issue in report["issues"])


def test_project_integrity_validates_frozen_stability_analysis_and_gate_chain(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "stability-chain-integrity"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Stability chain integrity"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _frame(), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    study_response = client.post("/api/projects/training/studies", json={"session_id": session_id, "name": "fixed split", "model_kind": "random_forest", "seeds": [11, 13, 17], "randomness_protocol": "TRAINING_VARIABILITY", "split_seed": 42, "selection_metric": "f1", "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert study_response.status_code == 201, study_response.text
    study = study_response.json()
    evaluation_response = client.post("/api/projects/analyses/evaluations", json={"session_id": session_id, "run_id": study["selected_run_id"]})
    assert evaluation_response.status_code == 201, evaluation_response.text
    evaluation_id = evaluation_response.json()["evaluation_id"]
    threshold_response = client.post("/api/projects/analyses/thresholds", json={"session_id": session_id, "evaluation_id": evaluation_id, "calibration_id": None, "objective": "f1"})
    assert threshold_response.status_code == 201, threshold_response.text
    threshold_id = threshold_response.json()["threshold_id"]
    analysis_response = client.post("/api/projects/analyses/stability", json={"session_id": session_id, "study_id": study["study_id"], "evaluation_id": evaluation_id, "threshold_id": threshold_id, "high_confidence_threshold": .9, "unstable_agreement_threshold": .8})
    assert analysis_response.status_code == 201, analysis_response.text
    analysis = analysis_response.json()
    policy_response = client.post("/api/projects/analyses/stability-policies", json={"session_id": session_id, "analysis_id": analysis["analysis_id"], "evaluation_id": evaluation_id, "min_confidence": .9, "min_class_agreement": .8, "max_probability_std": .15})
    assert policy_response.status_code == 201, policy_response.text
    assert client.get(f"/api/projects/{session_id}/integrity").json()["status"] == "PASS"
    final_test = client.post("/api/projects/analyses/final-test", json={"session_id": session_id, "evaluation_id": evaluation_id, "threshold_id": threshold_id, "stability_gate_policy_id": policy_response.json()["policy_id"]})
    assert final_test.status_code == 201, final_test.text
    assert client.get(f"/api/projects/{session_id}/integrity").json()["status"] == "PASS"

    policy_path = root / "analyses" / "stability-policies" / f"{policy_response.json()['policy_id']}.json"
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    payload["class_threshold_id"] = "00000000-0000-0000-0000-000000000001"
    policy_path.write_text(json.dumps(payload), encoding="utf-8")
    report = client.get(f"/api/projects/{session_id}/integrity").json()

    assert report["status"] == "FAIL"
    assert any(issue["code"] == "STABILITY_GATE_PROVENANCE_MISMATCH" for issue in report["issues"])


def test_project_integrity_fails_closed_for_unknown_persisted_model_adapter(tmp_path: Path) -> None:
    client = TestClient(app); root = tmp_path / "unknown-adapter-integrity"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Unknown adapter"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _frame(), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "decision_tree", "seed": 42, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3}).json()
    run_path = root / "runs" / f"{trained['run_id']}.json"
    payload = json.loads(run_path.read_text(encoding="utf-8"))
    payload["adapter_key"] = "missing_adapter"
    run_path.write_text(json.dumps(payload), encoding="utf-8")

    report = client.get(f"/api/projects/{session_id}/integrity").json()

    assert report["status"] == "FAIL"
    assert any(item["code"] == "ADAPTER_IDENTITY" and item["status"] == "FAIL" for item in report["issues"])


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


def test_project_integrity_rejects_tampered_transform_pipeline(tmp_path: Path) -> None:
    client = TestClient(app); root = tmp_path / "transform-pipeline-integrity"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Transform pipeline"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _frame(), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": 42, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3}).json()
    pipeline_id = trained["transform_pipeline_id"]
    path = root / "data" / "transforms" / f"{pipeline_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8")); payload["feature_order"] = ["tampered"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    report = client.get(f"/api/projects/{session_id}/integrity").json()
    assert report["status"] == "FAIL"
    assert any(issue["code"] == "TRANSFORM_PIPELINE_EVIDENCE_MALFORMED" for issue in report["issues"])


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


def test_project_integrity_checks_persisted_fis_semantic_identity(tmp_path: Path) -> None:
    client = TestClient(app); root = tmp_path / "fis-semantic-integrity"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "FIS semantic integrity"}).json()["session_id"]
    imported = client.post("/api/projects/fis/import/matlab", json={"session_id": session_id, "source": _MAMDANI})
    assert imported.status_code == 200, imported.text
    fis_path = root / "models" / "fis" / f"{imported.json()['spec']['fis_id']}.json"
    payload = json.loads(fis_path.read_text(encoding="utf-8"))
    payload["semantic_hash"] = "0" * 64
    fis_path.write_text(json.dumps(payload), encoding="utf-8")
    report = client.get(f"/api/projects/{session_id}/integrity").json()
    assert report["status"] == "FAIL"
    assert any(issue["code"] == "FIS_EVIDENCE_MALFORMED" for issue in report["issues"])


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


def test_project_integrity_rejects_tampered_runtime_component_provenance(tmp_path: Path) -> None:
    client = TestClient(app); root = tmp_path / "runtime-component-integrity"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Runtime component integrity"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _frame(), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    run = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": 42, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3}).json()
    explanation = client.post("/api/projects/evidence/explanations/occlusion", json={"session_id": session_id, "run_id": run["run_id"], "sample": {"temperature": 20.0, "torque": 40.0}}).json()
    path = root / "evidence" / "explanations" / f"{explanation['explanation_id']}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["explainer_provider"] = "ruflex.tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")
    report = client.get(f"/api/projects/{session_id}/integrity").json()
    assert report["status"] == "FAIL"
    assert any(issue["code"] == "EXPLAINER_RUNTIME_PROVIDER_MISMATCH" for issue in report["issues"])
