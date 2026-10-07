from __future__ import annotations

import json
import time
from pathlib import Path
from uuid import uuid4

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
    analysis_path = root / "analyses" / "stability-analyses" / f"{analysis['analysis_id']}.json"
    analysis_payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    original_run_ids = list(analysis_payload["run_ids"])
    analysis_payload["run_ids"][0] = analysis_payload["run_ids"][1]
    analysis_path.write_text(json.dumps(analysis_payload), encoding="utf-8")
    duplicate_support = client.get(f"/api/projects/{session_id}/integrity").json()
    assert any(issue["code"] == "STABILITY_ANALYSIS_PROVENANCE_MISMATCH" for issue in duplicate_support["issues"])
    analysis_payload["run_ids"] = original_run_ids
    analysis_path.write_text(json.dumps(analysis_payload), encoding="utf-8")
    analysis_payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    original_agreement = analysis_payload["cases"][0]["selected_run_agreement"]
    analysis_payload["cases"][0]["selected_run_agreement"] = 0.0 if original_agreement > 0.0 else 1.0
    analysis_path.write_text(json.dumps(analysis_payload), encoding="utf-8")
    corrupted_case_summary = client.get(f"/api/projects/{session_id}/integrity").json()
    assert any(issue["code"] == "STABILITY_ANALYSIS_PROVENANCE_MISMATCH" for issue in corrupted_case_summary["issues"])
    analysis_payload["cases"][0]["selected_run_agreement"] = original_agreement
    original_f1_mean = analysis_payload["metric_distributions"]["f1"]["mean"]
    analysis_payload["metric_distributions"]["f1"]["mean"] = original_f1_mean + 0.1
    analysis_path.write_text(json.dumps(analysis_payload), encoding="utf-8")
    corrupted_metric_summary = client.get(f"/api/projects/{session_id}/integrity").json()
    assert any(issue["code"] == "STABILITY_ANALYSIS_PROVENANCE_MISMATCH" for issue in corrupted_metric_summary["issues"])
    analysis_payload["metric_distributions"]["f1"]["mean"] = original_f1_mean
    original_training_seeds = list(analysis_payload["training_seeds"])
    analysis_payload["training_seeds"][0] += 1000
    analysis_path.write_text(json.dumps(analysis_payload), encoding="utf-8")
    corrupted_seed_summary = client.get(f"/api/projects/{session_id}/integrity").json()
    assert any(issue["code"] == "STABILITY_ANALYSIS_PROVENANCE_MISMATCH" for issue in corrupted_seed_summary["issues"])
    analysis_payload["training_seeds"] = original_training_seeds
    analysis_path.write_text(json.dumps(analysis_payload), encoding="utf-8")
    policy_path = root / "analyses" / "stability-policies" / f"{policy_response.json()['policy_id']}.json"
    policy_payload = json.loads(policy_path.read_text(encoding="utf-8"))
    original_decision_agreement = policy_payload["decisions"][0]["selected_run_agreement"]
    policy_payload["decisions"][0]["selected_run_agreement"] = 0.0 if original_decision_agreement > 0.0 else 1.0
    policy_path.write_text(json.dumps(policy_payload), encoding="utf-8")
    corrupted_decision = client.get(f"/api/projects/{session_id}/integrity").json()
    assert any(issue["code"] == "STABILITY_GATE_PROVENANCE_MISMATCH" for issue in corrupted_decision["issues"])
    policy_payload["decisions"][0]["selected_run_agreement"] = original_decision_agreement
    original_no_review_risk = policy_payload["risk_coverage"][0]["accepted_risk"]
    policy_payload["risk_coverage"][0]["accepted_risk"] = 0.0 if original_no_review_risk > 0.0 else 1.0
    policy_path.write_text(json.dumps(policy_payload), encoding="utf-8")
    corrupted_risk = client.get(f"/api/projects/{session_id}/integrity").json()
    assert any(issue["code"] == "STABILITY_GATE_PROVENANCE_MISMATCH" for issue in corrupted_risk["issues"])
    policy_payload["risk_coverage"][0]["accepted_risk"] = original_no_review_risk
    policy_path.write_text(json.dumps(policy_payload), encoding="utf-8")
    final_test = client.post("/api/projects/analyses/final-test", json={"session_id": session_id, "evaluation_id": evaluation_id, "threshold_id": threshold_id, "stability_gate_policy_id": policy_response.json()["policy_id"]})
    assert final_test.status_code == 201, final_test.text
    assert client.get(f"/api/projects/{session_id}/integrity").json()["status"] == "PASS"
    threshold_path = root / "analyses" / "thresholds" / f"{threshold_id}.json"
    threshold_payload = json.loads(threshold_path.read_text(encoding="utf-8"))
    original_threshold_created_at = threshold_payload["created_at"]
    threshold_payload["created_at"] = "2099-01-01T00:00:00Z"
    threshold_path.write_text(json.dumps(threshold_payload), encoding="utf-8")
    post_unlock_policy = client.get(f"/api/projects/{session_id}/integrity").json()
    assert any(issue["code"] == "FINAL_TEST_PROVENANCE_MISMATCH" for issue in post_unlock_policy["issues"])
    threshold_payload["created_at"] = original_threshold_created_at
    threshold_path.write_text(json.dumps(threshold_payload), encoding="utf-8")
    supporting_run_ids = [item["run_id"] for item in study["seed_runs"]]
    for run_id in (study["selected_run_id"], next(value for value in supporting_run_ids if value != study["selected_run_id"])):
        run_path = root / "runs" / f"{run_id}.json"
        run_payload = json.loads(run_path.read_text(encoding="utf-8"))
        original_run_created_at = run_payload["created_at"]
        run_payload["created_at"] = "2099-01-01T00:00:00Z"
        run_path.write_text(json.dumps(run_payload), encoding="utf-8")
        late_run = client.get(f"/api/projects/{session_id}/integrity").json()
        assert any(issue["code"] == "FINAL_TEST_PROVENANCE_MISMATCH" for issue in late_run["issues"])
        run_payload["created_at"] = original_run_created_at
        run_path.write_text(json.dumps(run_payload), encoding="utf-8")
    policy_path = root / "analyses" / "stability-policies" / f"{policy_response.json()['policy_id']}.json"
    policy_payload = json.loads(policy_path.read_text(encoding="utf-8"))
    original_policy_created_at = policy_payload["created_at"]
    policy_payload["created_at"] = "2099-01-01T00:00:00Z"
    policy_path.write_text(json.dumps(policy_payload), encoding="utf-8")
    late_gate_creation = client.get(f"/api/projects/{session_id}/integrity").json()
    assert any(issue["code"] == "FINAL_TEST_PROVENANCE_MISMATCH" for issue in late_gate_creation["issues"])
    policy_payload["created_at"] = original_policy_created_at
    policy_path.write_text(json.dumps(policy_payload), encoding="utf-8")
    original_analysis_created_at = analysis_payload["created_at"]
    analysis_payload["created_at"] = "2099-01-01T00:00:00Z"
    analysis_path.write_text(json.dumps(analysis_payload), encoding="utf-8")
    late_analysis_creation = client.get(f"/api/projects/{session_id}/integrity").json()
    assert any(issue["code"] == "FINAL_TEST_PROVENANCE_MISMATCH" for issue in late_analysis_creation["issues"])
    analysis_payload["created_at"] = original_analysis_created_at
    analysis_path.write_text(json.dumps(analysis_payload), encoding="utf-8")
    final_test_path = root / "analyses" / "final-tests" / f"{final_test.json()['final_test_id']}.json"
    final_test_payload = json.loads(final_test_path.read_text(encoding="utf-8"))
    duplicate_final_test = json.loads(json.dumps(final_test_payload))
    duplicate_final_test_id = str(uuid4())
    duplicate_final_test["final_test_id"] = duplicate_final_test_id
    duplicate_final_test["dataset_test_unlock_at"] = "2000-01-01T00:00:00Z"
    duplicate_final_test_path = root / "analyses" / "final-tests" / f"{duplicate_final_test_id}.json"
    duplicate_final_test_path.write_text(json.dumps(duplicate_final_test), encoding="utf-8")
    inconsistent_unlock = client.get(f"/api/projects/{session_id}/integrity").json()
    assert any(issue["code"] == "DATASET_TEST_UNLOCK_INCONSISTENT" for issue in inconsistent_unlock["issues"])
    duplicate_final_test_path.unlink()
    original_policy_frozen_at = final_test_payload["policy_frozen_at"]
    final_test_payload["policy_frozen_at"] = "2000-01-01T00:00:00Z"
    final_test_path.write_text(json.dumps(final_test_payload), encoding="utf-8")
    forged_freeze_time = client.get(f"/api/projects/{session_id}/integrity").json()
    assert any(issue["code"] == "FINAL_TEST_PROVENANCE_MISMATCH" for issue in forged_freeze_time["issues"])
    final_test_payload["policy_frozen_at"] = original_policy_frozen_at
    original_selected_class = final_test_payload["stability_gate_evidence"]["cases"][0]["selected_run_class"]
    final_test_payload["stability_gate_evidence"]["cases"][0]["selected_run_class"] = 1 - original_selected_class
    final_test_path.write_text(json.dumps(final_test_payload), encoding="utf-8")
    bad_stability_case = client.get(f"/api/projects/{session_id}/integrity").json()
    assert any(issue["code"] == "FINAL_TEST_PROVENANCE_MISMATCH" for issue in bad_stability_case["issues"])
    final_test_payload["stability_gate_evidence"]["cases"][0]["selected_run_class"] = original_selected_class
    final_test_path.write_text(json.dumps(final_test_payload), encoding="utf-8")
    original_test_case_identity = final_test_payload["test_case_identity"]
    final_test_payload["test_case_identity"] = "forged-case-identity"
    final_test_path.write_text(json.dumps(final_test_payload), encoding="utf-8")
    bad_case_identity = client.get(f"/api/projects/{session_id}/integrity").json()
    assert any(issue["code"] == "FINAL_TEST_PROVENANCE_MISMATCH" for issue in bad_case_identity["issues"])
    final_test_payload["test_case_identity"] = original_test_case_identity
    final_test_path.write_text(json.dumps(final_test_payload), encoding="utf-8")

    policy_path = root / "analyses" / "stability-policies" / f"{policy_response.json()['policy_id']}.json"
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    payload["policy_id"] = "00000000-0000-0000-0000-000000000002"
    policy_path.write_text(json.dumps(payload), encoding="utf-8")
    mismatched_policy = client.get(f"/api/projects/{session_id}/analyses/stability-policies/{policy_response.json()['policy_id']}")
    assert mismatched_policy.status_code == 422
    payload["policy_id"] = policy_response.json()["policy_id"]
    payload["class_threshold_id"] = "00000000-0000-0000-0000-000000000001"
    policy_path.write_text(json.dumps(payload), encoding="utf-8")
    analysis_payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    analysis_payload["analysis_id"] = "00000000-0000-0000-0000-000000000003"
    analysis_path.write_text(json.dumps(analysis_payload), encoding="utf-8")
    mismatched_analysis = client.get(f"/api/projects/{session_id}/analyses/stability/{analysis['analysis_id']}")
    assert mismatched_analysis.status_code == 422
    report = client.get(f"/api/projects/{session_id}/integrity").json()

    assert report["status"] == "FAIL"
    assert any(issue["code"] == "STABILITY_GATE_PROVENANCE_MISMATCH" for issue in report["issues"])


def test_project_integrity_recomputes_study_selection_from_canonical_runs(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "study-selection-integrity"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Study selection integrity"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _frame(), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    created = client.post("/api/projects/training/studies", json={"session_id": session_id, "name": "frozen study", "model_kind": "random_forest", "seeds": [19, 23, 29], "randomness_protocol": "TRAINING_VARIABILITY", "split_seed": 42, "selection_metric": "f1", "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert created.status_code == 201, created.text
    study_id = created.json()["study_id"]
    study_path = root / "studies" / f"{study_id}.json"
    payload = json.loads(study_path.read_text(encoding="utf-8"))
    assert client.get(f"/api/projects/{session_id}/integrity").json()["status"] == "PASS"
    duplicate = json.loads(json.dumps(payload))
    duplicate["seed_runs"].append(json.loads(json.dumps(payload["seed_runs"][0])))
    duplicate["training_seeds"].append(duplicate["training_seeds"][0])
    study_path.write_text(json.dumps(duplicate), encoding="utf-8")

    duplicate_report = client.get(f"/api/projects/{session_id}/integrity").json()

    assert duplicate_report["status"] == "FAIL"
    assert any(issue["code"] == "STUDY_RUN_SUPPORT_INVALID" for issue in duplicate_report["issues"])
    study_path.write_text(json.dumps(payload), encoding="utf-8")
    payload["seed_runs"][0]["validation_metrics"]["f1"] = 0.123456
    study_path.write_text(json.dumps(payload), encoding="utf-8")
    (root / "studies" / "active-study.json").write_text(json.dumps({"study_id": "00000000-0000-0000-0000-000000000004"}), encoding="utf-8")

    report = client.get(f"/api/projects/{session_id}/integrity").json()

    assert report["status"] == "FAIL"
    assert any(issue["code"] == "ADAPTER_IDENTITY" and "canonical persisted TrainingRun" in issue["detail"] for issue in report["issues"])
    assert any(issue["code"] == "STUDY_ACTIVE_POINTER_INVALID" for issue in report["issues"])


def test_project_integrity_rejects_study_seed_fields_that_contradict_variability_protocol(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "study-randomness-integrity"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Study randomness integrity"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _frame(), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    created = client.post("/api/projects/training/studies", json={"session_id": session_id, "name": "training variability", "model_kind": "random_forest", "seeds": [31, 37, 41], "randomness_protocol": "TRAINING_VARIABILITY", "split_seed": 42, "selection_metric": "f1", "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert created.status_code == 201, created.text
    study_id = created.json()["study_id"]
    study_path = root / "studies" / f"{study_id}.json"
    payload = json.loads(study_path.read_text(encoding="utf-8"))
    payload["randomness_protocol"] = "SPLIT_VARIABILITY"
    payload["split_seed"] = None
    study_path.write_text(json.dumps(payload), encoding="utf-8")

    report = client.get(f"/api/projects/{session_id}/integrity").json()

    assert report["status"] == "FAIL"
    assert any(issue["code"] == "STUDY_RANDOMNESS_PROVENANCE_MISMATCH" for issue in report["issues"])


def test_project_integrity_keeps_legacy_study_schema_readable_without_rewrite(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "legacy-study-integrity"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Legacy Study integrity"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _frame(), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    created = client.post("/api/projects/training/studies", json={"session_id": session_id, "name": "legacy coupled seeds", "model_kind": "random_forest", "seeds": [43, 47, 53], "randomness_protocol": "LEGACY_COMBINED", "selection_metric": "f1", "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert created.status_code == 201, created.text
    study_path = root / "studies" / f"{created.json()['study_id']}.json"
    payload = json.loads(study_path.read_text(encoding="utf-8"))
    payload["schema_version"] = 2
    payload["training_seeds"] = []
    for field in ("adapter_key", "adapter_version", "adapter_provider", "runtime_capability_snapshot_hash"):
        payload.pop(field, None)
    study_path.write_text(json.dumps(payload), encoding="utf-8")
    original = study_path.read_bytes()

    report = client.get(f"/api/projects/{session_id}/integrity").json()

    assert study_path.read_bytes() == original
    assert report["status"] in {"PASS", "WARN"}
    assert not any(issue["code"] in {"ADAPTER_IDENTITY", "STUDY_RANDOMNESS_PROVENANCE_MISMATCH"} and issue["status"] == "FAIL" for issue in report["issues"])


def test_project_integrity_rejects_study_job_detached_from_created_study(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "study-job-integrity"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "StudyJob integrity"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _frame(), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    started = client.post("/api/projects/training/study-jobs", json={"session_id": session_id, "name": "integrity forest", "model_kind": "random_forest", "seeds": [51, 53, 59], "selection_metric": "f1", "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert started.status_code == 202, started.text
    job = started.json()
    for _ in range(100):
        job = client.get(f"/api/projects/{session_id}/training/study-jobs/{job['job_id']}").json()
        if job["status"] not in {"QUEUED", "RUNNING"}:
            break
        time.sleep(.05)
    assert job["status"] == "SUCCEEDED"
    assert client.get(f"/api/projects/{session_id}/integrity").json()["status"] == "PASS"

    job_path = root / "studies" / "jobs" / f"{job['job_id']}.json"
    persisted_job = json.loads(job_path.read_text(encoding="utf-8"))
    payload = dict(persisted_job)
    payload["study_id"] = str(uuid4())
    job_path.write_text(json.dumps(payload), encoding="utf-8")

    report = client.get(f"/api/projects/{session_id}/integrity").json()

    assert report["status"] == "FAIL"
    assert any("TrainingStudy that is not present" in issue["detail"] for issue in report["issues"] if issue["code"] == "ADAPTER_IDENTITY")

    persisted_job["seed_states"][0]["run_id"] = str(uuid4())
    job_path.write_text(json.dumps(persisted_job), encoding="utf-8")
    report = client.get(f"/api/projects/{session_id}/integrity").json()

    assert report["status"] == "FAIL"
    assert any("missing canonical TrainingRun" in issue["detail"] for issue in report["issues"] if issue["code"] == "ADAPTER_IDENTITY")


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
