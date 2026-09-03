from __future__ import annotations

from pathlib import Path
import time

import pandas as pd
from fastapi.testclient import TestClient

from ruflex.api.main import app
from ruflex.application.datasets import (
    build_dataset_contract,
    inspect_dataset,
    persist_dataset_bytes,
    persist_dataset_contract,
    run_data_audit,
)
from ruflex.application.projects import ProjectService
from ruflex.application.training import load_latest_training_run, train_flat_neuro_fuzzy, verify_training_model_artifact


def _binary_frame(rows: int = 36) -> pd.DataFrame:
    values = []
    for index in range(rows):
        temperature = 10.0 + index * 0.7
        torque = 20.0 + (index * 11) % 60
        target = 1 if temperature + torque > 60.0 else 0
        values.append({"temperature": temperature, "torque": torque, "target": target})
    return pd.DataFrame(values)


def _confirm_dataset(root: Path, frame: pd.DataFrame) -> None:
    raw = frame.to_csv(index=False).encode("utf-8")
    reference = persist_dataset_bytes(root, raw)
    profile = inspect_dataset(frame, source_artifact_sha256=reference.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification")
    audit = run_data_audit(contract, frame)
    persist_dataset_contract(root, contract, audit, profile)


def test_real_training_persists_epoch_zero_validation_and_model_artifact(tmp_path: Path) -> None:
    root = tmp_path / "training"
    ProjectService().create(root, name="Training")
    _confirm_dataset(root, _binary_frame())

    run = train_flat_neuro_fuzzy(root, max_epochs=3, batch_size=16, patience=3, seed=7)
    restored = load_latest_training_run(root)

    assert run.trajectory[0].epoch == 0
    assert run.trajectory[-1].epoch >= 1
    assert run.validation_metrics
    assert run.evaluation_split == "validation"
    assert run.split.test_status == "LOCKED_NOT_EVALUATED"
    assert "test_metrics" not in run.model_dump()
    assert run.confusion_matrix is not None
    assert verify_training_model_artifact(root, run)
    assert restored.run_id == run.run_id


def test_training_api_runs_and_reopens_latest_result(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "api-training"
    created = client.post("/api/projects", json={"path": str(root), "name": "API training"})
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    frame = _binary_frame()
    confirmed = client.post(
        "/api/projects/dataset/confirm",
        json={
            "session_id": session_id,
            "csv_text": frame.to_csv(index=False),
            "target": "target",
            "task": "binary_classification",
            "id_columns": [],
        },
    )
    assert confirmed.status_code == 200, confirmed.text

    trained = client.post(
        "/api/projects/training/run",
        json={
            "session_id": session_id,
            "seed": 11,
            "max_epochs": 2,
            "learning_rate": 0.01,
            "batch_size": 16,
            "patience": 2,
            "validation_fraction": 0.2,
            "test_fraction": 0.2,
            "max_rules": 4,
        },
    )
    assert trained.status_code == 201, trained.text
    assert trained.json()["trajectory"][0]["epoch"] == 0
    assert trained.json()["validation_metrics"]

    latest = client.get(f"/api/projects/{session_id}/training/latest")
    assert latest.status_code == 200
    assert latest.json()["run_id"] == trained.json()["run_id"]


def test_read_only_training_is_rejected(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "read-only-training"
    created = client.post("/api/projects", json={"path": str(root), "name": "Read only training"})
    session_id = created.json()["session_id"]
    frame = _binary_frame()
    assert client.post(
        "/api/projects/dataset/confirm",
        json={"session_id": session_id, "csv_text": frame.to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []},
    ).status_code == 200

    opened = client.post("/api/projects/open", json={"path": str(root), "read_only": True})
    read_only_session = opened.json()["session_id"]
    response = client.post("/api/projects/training/run", json={"session_id": read_only_session, "max_epochs": 1})
    assert response.status_code == 403


def test_multi_seed_study_persists_validation_selection(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "study"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Study"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    response = client.post("/api/projects/training/studies", json={"session_id": session_id, "name": "three seeds", "seeds": [7, 8, 9], "selection_metric": "f1", "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert response.status_code == 201, response.text
    study = response.json()
    assert len(study["seed_runs"]) == 3
    assert study["selection_split"] == "validation"
    assert "locked test was not used" in study["selection_reason"]
    assert client.get(f"/api/projects/{session_id}/training/studies/latest").json()["study_id"] == study["study_id"]


def test_multi_seed_study_uses_selected_catalog_adapter_and_compare_rows(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "forest-study"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Forest study"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200

    response = client.post("/api/projects/training/studies", json={"session_id": session_id, "name": "forest seeds", "model_kind": "random_forest", "seeds": [41, 43, 47], "selection_metric": "f1", "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert response.status_code == 201, response.text
    study = response.json()
    assert study["model_kind"] == "random_forest"
    assert {run["model_kind"] for run in study["seed_runs"]} == {"random_forest"}
    assert all(run["runtime_seconds"] >= 0 for run in study["seed_runs"])

    comparison = client.post("/api/projects/analyses/comparisons", json={"session_id": session_id, "run_ids": [run["run_id"] for run in study["seed_runs"]]})
    assert comparison.status_code == 201, comparison.text
    row = comparison.json()["metric_rows"][0]
    assert row["model_kind"] == "random_forest"
    assert "runtime_seconds" in row
    assert row["node_count"] >= row["leaf_count"]
    assert "structural_trace" in row["capabilities"]
    assert "ece" in row
    assert "pr_auc" in row


def test_study_job_returns_immediately_and_persists_seed_lifecycle(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "study-job"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Study job"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    started = client.post("/api/projects/training/study-jobs", json={"session_id": session_id, "name": "async forest", "model_kind": "random_forest", "seeds": [51, 53, 59], "selection_metric": "f1", "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert started.status_code == 202, started.text
    job = started.json()
    assert len(job["seed_states"]) == 3
    for _ in range(80):
        job = client.get(f"/api/projects/{session_id}/training/study-jobs/{job['job_id']}").json()
        if job["status"] not in {"QUEUED", "RUNNING"}:
            break
        time.sleep(.05)
    assert job["status"] == "SUCCEEDED"
    assert {state["status"] for state in job["seed_states"]} == {"SUCCEEDED"}
    assert job["study_id"] is not None
    listed = client.get(f"/api/projects/{session_id}/training/study-jobs")
    assert listed.status_code == 200 and [item["job_id"] for item in listed.json()] == [job["job_id"]]
    assert job["execution_backend"] == "LOCAL"
    assert job["execution_config"]["max_epochs"] == 1


def test_persisted_study_job_resumes_without_replacing_declared_seeds(tmp_path: Path) -> None:
    from ruflex.domain.training import StudyJob, StudySeedState

    client = TestClient(app); root = tmp_path / "resumable-study"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Resumable study"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    interrupted = StudyJob(
        name="interrupted forest", model_kind="random_forest", selection_metric="f1", randomness_protocol="TRAINING_VARIABILITY", split_seed=42,
        seed_states=[StudySeedState(seed=seed, split_seed=42, training_seed=seed, status="RUNNING" if seed == 71 else "QUEUED") for seed in [71, 73, 79]],
        execution_config={"max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3},
    )
    destination = root / "studies" / "jobs" / f"{interrupted.job_id}.json"; destination.parent.mkdir(parents=True, exist_ok=True); destination.write_text(interrupted.model_dump_json(), encoding="utf-8")
    resumed = client.post(f"/api/projects/{session_id}/training/study-jobs/{interrupted.job_id}/resume")
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["recovery_count"] == 1
    for _ in range(80):
        job = client.get(f"/api/projects/{session_id}/training/study-jobs/{interrupted.job_id}").json()
        if job["status"] not in {"QUEUED", "RUNNING"}: break
        time.sleep(.05)
    assert job["status"] == "SUCCEEDED"
    assert [state["seed"] for state in job["seed_states"]] == [71, 73, 79]
    assert {state["status"] for state in job["seed_states"]} == {"SUCCEEDED"}


def test_validation_evaluation_is_a_persistent_run_bound_analysis_object(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "evaluation"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Evaluation"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "seed": 13, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert trained.status_code == 201, trained.text

    created = client.post("/api/projects/analyses/evaluations", json={"session_id": session_id, "run_id": trained.json()["run_id"]})
    assert created.status_code == 201, created.text
    evaluation = created.json()
    assert evaluation["run_id"] == trained.json()["run_id"]
    assert evaluation["split"] == "validation"
    assert evaluation["test_status"] == "LOCKED_NOT_EVALUATED"
    assert evaluation["metrics"] == trained.json()["validation_metrics"]
    assert evaluation["calibration"]["fit_scope"] == "not_fitted"
    assert evaluation["calibration"]["method"] == "validation_reliability_bins"
    assert evaluation["threshold"] is None
    assert evaluation["validation_row_count"] == trained.json()["split"]["validation_count"]
    assert evaluation["model_artifact_sha256"] == trained.json()["model_artifact_sha256"]
    assert evaluation["dataset_artifact_sha256"]
    assert evaluation["preprocessing_identity"].startswith("preprocessing:")
    assert evaluation["preprocessing_artifact_sha256"] == trained.json()["preprocessing_artifact_sha256"]
    assert evaluation["preprocessing_artifact_sha256"]
    assert all(row["calibrated_probability"] is None for row in evaluation["prediction_preview"])

    reopened = client.get(f"/api/projects/{session_id}/analyses/evaluations/latest")
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["evaluation_id"] == evaluation["evaluation_id"]

    calibrated = client.post(
        "/api/projects/analyses/calibrations",
        json={"session_id": session_id, "evaluation_id": evaluation["evaluation_id"]},
    )
    assert calibrated.status_code == 201, calibrated.text
    calibration = calibrated.json()
    assert calibration["evaluation_id"] == evaluation["evaluation_id"]
    assert calibration["run_id"] == evaluation["run_id"]
    assert calibration["source_split"] == "validation"
    assert calibration["test_status"] == "LOCKED_NOT_EVALUATED"
    assert calibration["method"] == "platt_scaling"
    assert calibration["fit_sample_count"] == evaluation["validation_row_count"]
    assert len(calibration["predictions"]) == evaluation["validation_row_count"]
    assert all(prediction["row_identity"] for prediction in calibration["predictions"])
    assert all(prediction["source_row"] is not None for prediction in calibration["predictions"])
    assert len({prediction["row_identity"] for prediction in calibration["predictions"]}) == evaluation["validation_row_count"]
    assert calibration["fit_sample_identity"].startswith("validation-calibration:")

    reopened_calibration = client.get(f"/api/projects/{session_id}/analyses/calibrations/latest")
    assert reopened_calibration.status_code == 200, reopened_calibration.text
    assert reopened_calibration.json()["calibration_id"] == calibration["calibration_id"]

    selected = client.post(
        "/api/projects/analyses/thresholds",
        json={
            "session_id": session_id,
            "evaluation_id": evaluation["evaluation_id"],
            "calibration_id": calibration["calibration_id"],
            "objective": "f1",
        },
    )
    assert selected.status_code == 201, selected.text
    threshold = selected.json()
    assert threshold["evaluation_id"] == evaluation["evaluation_id"]
    assert threshold["run_id"] == evaluation["run_id"]
    assert threshold["calibration_id"] == calibration["calibration_id"]
    assert threshold["source_split"] == "validation"
    assert threshold["test_status"] == "LOCKED_NOT_EVALUATED"
    assert threshold["probability_source"] == "calibrated"
    assert 0.01 <= threshold["selected_threshold"] <= 0.99
    assert len(threshold["decisions"]) == evaluation["validation_row_count"]

    reopened_threshold = client.get(f"/api/projects/{session_id}/analyses/thresholds/latest")
    assert reopened_threshold.status_code == 200, reopened_threshold.text
    assert reopened_threshold.json()["threshold_id"] == threshold["threshold_id"]

    selective = client.post(
        "/api/projects/analyses/selective-policies",
        json={"session_id": session_id, "evaluation_id": evaluation["evaluation_id"], "calibration_id": calibration["calibration_id"], "threshold_id": threshold["threshold_id"], "confidence_cutoff": 0.8},
    )
    assert selective.status_code == 201, selective.text
    assert selective.json()["class_threshold_id"] == threshold["threshold_id"]
    policy = selective.json()
    assert policy["confidence_cutoff"] == 0.8
    assert policy["probability_source"] == "calibrated"
    assert policy["test_status"] == "LOCKED_NOT_EVALUATED"
    assert len(policy["risk_coverage"]) == 10
    reopened_policy = client.get(f"/api/projects/{session_id}/analyses/selective-policies/latest")
    assert reopened_policy.status_code == 200 and reopened_policy.json()["policy_id"] == policy["policy_id"]


def test_validation_comparison_persists_compatible_seed_runs_and_rejects_duplicates(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "comparison"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Comparison"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    study = client.post("/api/projects/training/studies", json={"session_id": session_id, "name": "three seeds", "seeds": [17, 19, 23], "selection_metric": "f1", "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert study.status_code == 201, study.text
    run_ids = [seed_run["run_id"] for seed_run in study.json()["seed_runs"]]

    created = client.post("/api/projects/analyses/comparisons", json={"session_id": session_id, "run_ids": run_ids})
    assert created.status_code == 201, created.text
    comparison = created.json()
    assert comparison["split"] == "validation"
    assert len(comparison["metric_rows"]) == 3
    assert comparison["run_ids"] == run_ids
    assert comparison["dataset_fingerprint"]
    assert comparison["validation_alignment"] == "mixed_cases"
    assert len(comparison["validation_sample_identities"]) == 3
    assert len(set(comparison["validation_sample_identities"].values())) > 1
    assert "not a paired same-case" in comparison["scientific_note"].lower()
    assert "locked" in comparison["scientific_note"].lower()

    reopened = client.get(f"/api/projects/{session_id}/analyses/comparisons/latest")
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["comparison_id"] == comparison["comparison_id"]

    duplicate = client.post("/api/projects/analyses/comparisons", json={"session_id": session_id, "run_ids": [run_ids[0], run_ids[0]]})
    assert duplicate.status_code == 422



def test_validation_comparison_marks_same_cases_for_same_seed_cross_model_runs(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "same-case-comparison"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Same cases"}).json()["session_id"]
    assert client.post(
        "/api/projects/dataset/confirm",
        json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []},
    ).status_code == 200

    common = {
        "session_id": session_id,
        "seed": 31,
        "max_epochs": 1,
        "learning_rate": .01,
        "batch_size": 16,
        "patience": 1,
        "validation_fraction": .2,
        "test_fraction": .2,
        "max_rules": 3,
    }
    logistic = client.post("/api/projects/training/run", json={**common, "model_kind": "logistic_regression"})
    tree = client.post("/api/projects/training/run", json={**common, "model_kind": "decision_tree"})
    assert logistic.status_code == 201, logistic.text
    assert tree.status_code == 201, tree.text

    comparison = client.post(
        "/api/projects/analyses/comparisons",
        json={"session_id": session_id, "run_ids": [logistic.json()["run_id"], tree.json()["run_id"]]},
    )
    assert comparison.status_code == 201, comparison.text
    payload = comparison.json()
    assert payload["validation_alignment"] == "same_cases"
    assert len(set(payload["validation_sample_identities"].values())) == 1
    assert "same persisted validation cases" in payload["scientific_note"].lower()



def test_manual_fis_can_join_same_case_validation_comparison_without_probability_overclaim(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "manual-fis-comparison"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Manual FIS compare"}).json()["session_id"]
    frame = _binary_frame()
    assert client.post(
        "/api/projects/dataset/confirm",
        json={"session_id": session_id, "csv_text": frame.to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []},
    ).status_code == 200
    fis = client.post(
        "/api/projects/fis/default",
        json={"session_id": session_id, "name": "Manual risk FIS", "input_columns": ["temperature"]},
    )
    assert fis.status_code == 201, fis.text

    common = {
        "session_id": session_id,
        "seed": 37,
        "max_epochs": 1,
        "learning_rate": .01,
        "batch_size": 16,
        "patience": 1,
        "validation_fraction": .2,
        "test_fraction": .2,
        "max_rules": 3,
    }
    logistic = client.post("/api/projects/training/run", json={**common, "model_kind": "logistic_regression"})
    tree = client.post("/api/projects/training/run", json={**common, "model_kind": "decision_tree"})
    assert logistic.status_code == 201, logistic.text
    assert tree.status_code == 201, tree.text

    compared = client.post(
        "/api/projects/analyses/comparisons",
        json={
            "session_id": session_id,
            "run_ids": [logistic.json()["run_id"], tree.json()["run_id"]],
            "include_active_fis": True,
        },
    )
    assert compared.status_code == 201, compared.text
    comparison = compared.json()
    assert comparison["validation_alignment"] == "same_cases"
    assert comparison["fis_id"] == fis.json()["fis_id"]
    assert comparison["fis_semantic_hash"] == fis.json()["semantic_hash"]
    assert len(comparison["metric_rows"]) == 3
    fis_row = next(row for row in comparison["metric_rows"] if row["subject_type"] == "manual_fis")
    assert fis_row["model_kind"] == "mamdani"
    assert fis_row["validation_sample_identity"] in comparison["validation_sample_identities"].values()
    assert fis_row["score_semantics"] == "bounded_0_1_score_not_calibrated_probability"
    assert fis_row["calibration_status"] == "not_fitted_probability_semantics_not_claimed"
    assert "brier" not in fis_row
    assert "ece" not in fis_row
    assert "manual fis outputs are not labeled calibrated probabilities" in comparison["scientific_note"].lower()


def test_logistic_baseline_uses_train_only_split_and_safe_declarative_artifact(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "logistic"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Logistic"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": 23, "max_epochs": 12, "learning_rate": .01, "batch_size": 16, "patience": 2, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert trained.status_code == 201, trained.text
    run = trained.json()
    assert run["model_kind"] == "logistic_regression"
    assert run["split"]["preprocessing_fit_scope"] == "train_only"
    assert run["split"]["test_status"] == "LOCKED_NOT_EVALUATED"
    assert run["trajectory"][0]["epoch"] == 0
    artifact = client.get(f"/api/projects/{session_id}/artifacts")
    assert artifact.status_code == 200
    assert any(record["media_type"] == "application/vnd.ruflex.declarative-linear-model+json" for record in artifact.json())


def test_decision_tree_persists_declarative_structure_and_exact_path_evidence(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "tree"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Tree"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "decision_tree", "seed": 29, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert trained.status_code == 201, trained.text
    run = trained.json()
    assert run["model_kind"] == "decision_tree"
    assert run["model_spec"]["node_count"] >= 1
    assert run["model_spec"]["leaf_count"] >= 1
    evidence = client.post("/api/projects/training/tree-path", json={"session_id": session_id, "run_id": run["run_id"], "sample": {"temperature": 30.0, "torque": 40.0}})
    assert evidence.status_code == 201, evidence.text
    assert evidence.json()["label"] == "EXACT TREE EXECUTION PATH"
    assert evidence.json()["model_artifact_sha256"] == run["model_artifact_sha256"]
    assert evidence.json()["leaf_id"] >= 0
    restored = client.get(f"/api/projects/{session_id}/evidence/tree-path/latest")
    assert restored.status_code == 200, restored.text
    assert restored.json()["evidence_id"] == evidence.json()["evidence_id"]
    artifacts = client.get(f"/api/projects/{session_id}/artifacts")
    assert any(record["media_type"] == "application/vnd.ruflex.declarative-decision-tree+json" for record in artifacts.json())


def test_random_forest_persists_all_trees_without_claiming_one_exact_ensemble_path(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "forest"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Forest"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "random_forest", "seed": 31, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert trained.status_code == 201, trained.text
    run = trained.json()
    assert run["model_kind"] == "random_forest"
    assert run["model_spec"]["tree_count"] == 25
    assert run["model_spec"]["node_count"] >= run["model_spec"]["tree_count"]
    assert run["split"]["test_status"] == "LOCKED_NOT_EVALUATED"
    artifacts = client.get(f"/api/projects/{session_id}/artifacts")
    assert any(record["media_type"] == "application/vnd.ruflex.declarative-random-forest+json" for record in artifacts.json())


def test_gradient_boosting_persists_stagewise_trees_as_ensemble_artifact(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "boosting"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Boosting"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "gradient_boosting", "seed": 37, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert trained.status_code == 201, trained.text
    run = trained.json()
    assert run["model_kind"] == "gradient_boosting"
    assert run["model_spec"]["tree_count"] == 50
    assert run["split"]["test_status"] == "LOCKED_NOT_EVALUATED"
    artifacts = client.get(f"/api/projects/{session_id}/artifacts")
    assert any(record["media_type"] == "application/vnd.ruflex.declarative-gradient-boosting+json" for record in artifacts.json())


def test_final_test_requires_frozen_validation_policy_and_persists_separate_evidence(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "final-test"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Final test"}).json()["session_id"]
    assert client.post(
        "/api/projects/dataset/confirm",
        json={"session_id": session_id, "csv_text": _binary_frame(60).to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []},
    ).status_code == 200

    trained = client.post(
        "/api/projects/training/run",
        json={
            "session_id": session_id,
            "model_kind": "logistic_regression",
            "seed": 71,
            "max_epochs": 1,
            "learning_rate": .01,
            "batch_size": 16,
            "patience": 1,
            "validation_fraction": .2,
            "test_fraction": .2,
            "max_rules": 3,
        },
    )
    assert trained.status_code == 201, trained.text
    run = trained.json()
    assert run["split"]["test_status"] == "LOCKED_NOT_EVALUATED"

    evaluation = client.post(
        "/api/projects/analyses/evaluations",
        json={"session_id": session_id, "run_id": run["run_id"]},
    ).json()

    blocked = client.post(
        "/api/projects/analyses/final-test",
        json={"session_id": session_id, "evaluation_id": evaluation["evaluation_id"]},
    )
    assert blocked.status_code == 422
    assert "threshold" in blocked.text.lower()

    calibration = client.post(
        "/api/projects/analyses/calibrations",
        json={"session_id": session_id, "evaluation_id": evaluation["evaluation_id"]},
    ).json()
    threshold = client.post(
        "/api/projects/analyses/thresholds",
        json={
            "session_id": session_id,
            "evaluation_id": evaluation["evaluation_id"],
            "calibration_id": calibration["calibration_id"],
            "objective": "f1",
        },
    ).json()

    # A second baseline can be frozen before the first final-test access. This
    # permits a legitimate pre-specified final comparison while keeping later
    # policy creation blocked after the holdout has been seen. The same seed is
    # used here so both frozen runs reconstruct exactly the same holdout rows.
    second_run_response = client.post(
        "/api/projects/training/run",
        json={
            "session_id": session_id,
            "model_kind": "decision_tree",
            "seed": 71,
            "max_epochs": 1,
            "learning_rate": .01,
            "batch_size": 16,
            "patience": 1,
            "validation_fraction": .2,
            "test_fraction": .2,
            "max_rules": 3,
        },
    )
    assert second_run_response.status_code == 201, second_run_response.text
    second_run = second_run_response.json()
    second_evaluation = client.post(
        "/api/projects/analyses/evaluations",
        json={"session_id": session_id, "run_id": second_run["run_id"]},
    ).json()
    second_calibration = client.post(
        "/api/projects/analyses/calibrations",
        json={"session_id": session_id, "evaluation_id": second_evaluation["evaluation_id"]},
    ).json()
    second_threshold = client.post(
        "/api/projects/analyses/thresholds",
        json={
            "session_id": session_id,
            "evaluation_id": second_evaluation["evaluation_id"],
            "calibration_id": second_calibration["calibration_id"],
            "objective": "f1",
        },
    ).json()

    final_response = client.post(
        "/api/projects/analyses/final-test",
        json={
            "session_id": session_id,
            "evaluation_id": evaluation["evaluation_id"],
            "calibration_id": calibration["calibration_id"],
            "threshold_id": threshold["threshold_id"],
        },
    )
    assert final_response.status_code == 201, final_response.text
    final_test = final_response.json()
    assert final_test["split"] == "test"
    assert final_test["status"] == "FINAL_TEST_EVALUATED"
    assert final_test["run_id"] == run["run_id"]
    assert final_test["evaluation_id"] == evaluation["evaluation_id"]
    assert final_test["calibration_id"] == calibration["calibration_id"]
    assert final_test["threshold_id"] == threshold["threshold_id"]
    assert final_test["probability_source"] == "calibrated"
    assert final_test["decision_threshold"] == threshold["selected_threshold"]
    assert final_test["test_row_count"] == run["split"]["test_count"]
    assert len(final_test["prediction_rows"]) == run["split"]["test_count"]
    assert all(row["source_row"] is not None for row in final_test["prediction_rows"])
    assert final_test["test_sample_identity"].startswith("final-test-samples:")
    assert final_test["policy_identity"].startswith("final-test-policy:")
    assert final_test["test_case_identity"].startswith("final-test-cases:")
    assert final_test["policy_frozen_at"] is not None
    assert final_test["dataset_test_unlock_at"] is not None
    assert "f1" in final_test["metrics"]
    assert "brier" in final_test["metrics"]
    assert "ece" in final_test["metrics"]

    reopened = client.get(f"/api/projects/{session_id}/analyses/final-test/latest")
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["final_test_id"] == final_test["final_test_id"]

    # Repeating the exact frozen policy is idempotent, not a second peek.
    repeated = client.post(
        "/api/projects/analyses/final-test",
        json={
            "session_id": session_id,
            "evaluation_id": evaluation["evaluation_id"],
            "calibration_id": calibration["calibration_id"],
            "threshold_id": threshold["threshold_id"],
        },
    )
    assert repeated.status_code == 201
    assert repeated.json()["final_test_id"] == final_test["final_test_id"]

    second_final_response = client.post(
        "/api/projects/analyses/final-test",
        json={
            "session_id": session_id,
            "evaluation_id": second_evaluation["evaluation_id"],
            "calibration_id": second_calibration["calibration_id"],
            "threshold_id": second_threshold["threshold_id"],
        },
    )
    assert second_final_response.status_code == 201, second_final_response.text
    second_final = second_final_response.json()
    assert second_final["run_id"] == second_run["run_id"]
    assert second_final["test_case_identity"] == final_test["test_case_identity"]
    assert second_final["dataset_test_unlock_at"] == final_test["dataset_test_unlock_at"]

    alternate_threshold = client.post(
        "/api/projects/analyses/thresholds",
        json={"session_id": session_id, "evaluation_id": evaluation["evaluation_id"], "objective": "f1"},
    )
    assert alternate_threshold.status_code == 201
    blocked_second_policy = client.post(
        "/api/projects/analyses/final-test",
        json={
            "session_id": session_id,
            "evaluation_id": evaluation["evaluation_id"],
            "threshold_id": alternate_threshold.json()["threshold_id"],
        },
    )
    assert blocked_second_policy.status_code == 422
    assert "already been opened" in blocked_second_policy.text

    # The immutable TrainingRun remains explicitly validation-oriented; final-test
    # evidence exists only in its separate, explicit analysis object.
    run_after = client.get(f"/api/projects/{session_id}/training/runs/{run['run_id']}").json()
    assert run_after["split"]["test_status"] == "LOCKED_NOT_EVALUATED"
