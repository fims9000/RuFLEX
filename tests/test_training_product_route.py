from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import time

import pandas as pd
import pytest
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
from ruflex.application import training as training_application
from ruflex.application.training import load_latest_training_run, train_flat_neuro_fuzzy, verify_training_model_artifact
from ruflex.application.project_integrity import inspect_project_integrity
from ruflex.application.datasets import load_transform_pipeline_contract


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


@pytest.mark.parametrize(("mode", "scaler"), [("none", None), ("minmax", "MinMaxScaler")])
def test_selected_train_only_scaling_persists_and_replays_final_test(tmp_path: Path, mode: str, scaler: str | None) -> None:
    client = TestClient(app)
    root = tmp_path / mode
    session_id = client.post("/api/projects", json={"path": str(root), "name": mode}).json()["session_id"]
    confirmed = client.post("/api/projects/dataset/confirm", json={
        "session_id": session_id, "csv_text": _binary_frame(60).to_csv(index=False),
        "target": "target", "task": "binary_classification", "id_columns": [],
    })
    assert confirmed.status_code == 200, confirmed.text
    trained = client.post("/api/projects/training/run", json={
        "session_id": session_id, "model_kind": "logistic_regression", "seed": 31,
        "normalization": mode, "validation_fraction": .2, "test_fraction": .2,
    })
    assert trained.status_code == 201, trained.text
    run = trained.json()
    assert run["normalization"]["mode"] == mode
    assert run["declared_training_config"]["parameters"]["normalization"] == mode
    pipeline = load_transform_pipeline_contract(root, run["transform_pipeline_id"])
    assert [step.step_type for step in pipeline.steps if step.step_type in {"StandardScaler", "MinMaxScaler"}] == ([] if scaler is None else [scaler])
    evaluation = client.post("/api/projects/analyses/evaluations", json={"session_id": session_id, "run_id": run["run_id"]})
    assert evaluation.status_code == 201, evaluation.text
    threshold = client.post("/api/projects/analyses/thresholds", json={
        "session_id": session_id, "evaluation_id": evaluation.json()["evaluation_id"], "objective": "f1",
    })
    assert threshold.status_code == 201, threshold.text
    final = client.post("/api/projects/analyses/final-test", json={
        "session_id": session_id, "evaluation_id": evaluation.json()["evaluation_id"],
        "threshold_id": threshold.json()["threshold_id"],
    })
    assert final.status_code == 201, final.text
    assert final.json()["prediction_rows"]
    assert client.get(f"/api/projects/{session_id}/integrity").json()["status"] == "PASS"
    assert client.post("/api/projects/close", json={"session_id": session_id}).status_code == 204
    reopened = client.post("/api/projects/open", json={"path": str(root), "read_only": True})
    assert reopened.status_code == 200, reopened.text
    reopened_id = reopened.json()["session_id"]
    assert client.get(f"/api/projects/{reopened_id}/training/latest").json()["normalization"]["mode"] == mode
    assert client.get(f"/api/projects/{reopened_id}/integrity").json()["status"] == "PASS"


def test_training_api_rejects_unknown_scaling_before_fit(tmp_path: Path) -> None:
    client = TestClient(app)
    session_id = client.post("/api/projects", json={"path": str(tmp_path / "invalid-scaling"), "name": "Invalid scaling"}).json()["session_id"]
    response = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "normalization": "quantile"})
    assert response.status_code == 422
    assert client.get(f"/api/projects/{session_id}/training/runs").json() == []


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

    response = client.post("/api/projects/training/studies", json={"session_id": session_id, "name": "forest seeds", "model_kind": "random_forest", "seeds": [41, 43, 47], "selection_metric": "f1", "normalization": "minmax", "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert response.status_code == 201, response.text
    study = response.json()
    assert study["model_kind"] == "random_forest"
    assert {run["model_kind"] for run in study["seed_runs"]} == {"random_forest"}
    assert {run["normalization"]["mode"] for run in study["seed_runs"]} == {"minmax"}
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
    started = client.post("/api/projects/training/study-jobs", json={"session_id": session_id, "name": "async forest", "model_kind": "random_forest", "seeds": [51, 53, 59], "selection_metric": "f1", "normalization": "none", "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert started.status_code == 202, started.text
    job = started.json()
    assert job["execution_config"]["normalization"] == "none"
    assert len(job["seed_states"]) == 3
    for _ in range(80):
        job = client.get(f"/api/projects/{session_id}/training/study-jobs/{job['job_id']}").json()
        if job["status"] not in {"QUEUED", "RUNNING"}:
            break
        time.sleep(.05)
    assert job["status"] == "SUCCEEDED"
    assert {state["status"] for state in job["seed_states"]} == {"SUCCEEDED"}
    assert job["study_id"] is not None
    study = client.get(f"/api/projects/{session_id}/training/studies/{job['study_id']}")
    assert study.status_code == 200
    assert (study.json()["adapter_key"], study.json()["adapter_version"]) == ("native_random_forest", "1")
    assert {run["normalization"]["mode"] for run in study.json()["seed_runs"]} == {"none"}
    listed = client.get(f"/api/projects/{session_id}/training/study-jobs")
    assert listed.status_code == 200 and [item["job_id"] for item in listed.json()] == [job["job_id"]]
    assert job["execution_backend"] == "LOCAL"
    assert (job["adapter_key"], job["adapter_version"], job["adapter_provider"]) == (
        "native_random_forest", "1", "ruflex.builtin",
    )
    assert (job["execution_backend_key"], job["execution_backend_version"], job["execution_backend_provider"]) == (
        "local_executor", "1", "ruflex.builtin",
    )
    assert job["execution_config"]["max_epochs"] == 1


@pytest.mark.parametrize("endpoint", ["/api/projects/training/studies", "/api/projects/training/study-jobs"])
def test_study_rejects_duplicate_declared_seeds_before_execution(tmp_path: Path, endpoint: str) -> None:
    client = TestClient(app)
    root = tmp_path / "duplicate-study-seeds"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Duplicate seeds"}).json()["session_id"]
    confirmed = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []})
    assert confirmed.status_code == 200, confirmed.text

    response = client.post(endpoint, json={
        "session_id": session_id, "name": "must preserve declared matrix", "model_kind": "random_forest",
        "seeds": [3, 3, 5, 7], "selection_metric": "f1", "randomness_protocol": "TRAINING_VARIABILITY",
        "split_seed": 42, "max_epochs": 1, "learning_rate": .01, "batch_size": 16,
        "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3,
    })

    assert response.status_code == 422, response.text
    assert "distinct declared seeds" in response.text
    assert not (root / "studies" / "active-study.json").exists()
    assert not list((root / "studies" / "jobs").glob("*.json"))
    assert not list((root / "runs").glob("*.json"))


@pytest.mark.parametrize("endpoint", ["/api/projects/training/studies", "/api/projects/training/study-jobs"])
@pytest.mark.parametrize("selection_metric", ["rmse", "not_a_metric"])
def test_study_rejects_incompatible_selection_metric_before_fitting(tmp_path: Path, endpoint: str, selection_metric: str) -> None:
    client = TestClient(app)
    root = tmp_path / f"invalid-metric-{endpoint.rsplit('/', 1)[-1]}-{selection_metric}"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Invalid Study metric"}).json()["session_id"]
    confirmed = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []})
    assert confirmed.status_code == 200, confirmed.text

    response = client.post(endpoint, json={
        "session_id": session_id, "name": "must not fit", "model_kind": "random_forest",
        "seeds": [3, 5, 7], "selection_metric": selection_metric,
        "randomness_protocol": "TRAINING_VARIABILITY", "split_seed": 42,
    })

    assert response.status_code == 422, response.text
    assert "no Study fits were started" in response.text
    assert not list((root / "runs").glob("*.json"))
    assert not list((root / "studies" / "jobs").glob("*.json"))


def test_study_metric_preflight_distinguishes_regression_from_classification() -> None:
    from ruflex.application.training import TrainingError

    training_application._validate_study_selection_metric("f1", "binary_classification")
    training_application._validate_study_selection_metric("rmse", "regression")
    with pytest.raises(TrainingError, match="unavailable for 'regression'"):
        training_application._validate_study_selection_metric("f1", "regression")
    with pytest.raises(TrainingError, match="unavailable for 'binary_classification'"):
        training_application._validate_study_selection_metric("rmse", "binary_classification")


@pytest.mark.parametrize("endpoint", ["/api/projects/training/studies", "/api/projects/training/study-jobs"])
@pytest.mark.parametrize("violation", ["varying_splits", "wrong_fixed_seed", "wrong_fractions"])
def test_study_rejects_incompatible_split_contract_before_fitting(tmp_path: Path, endpoint: str, violation: str) -> None:
    client = TestClient(app)
    root = tmp_path / f"bad-study-split-{endpoint.rsplit('/', 1)[-1]}-{violation}"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Study split preflight"}).json()["session_id"]
    confirmed = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []})
    assert confirmed.status_code == 200, confirmed.text
    frozen = client.post("/api/projects/dataset/splits", json={"session_id": session_id, "family": "RANDOM", "split_seed": 42})
    assert frozen.status_code == 201, frozen.text
    split_id = frozen.json()["split_id"]
    training_application._validate_study_split_binding(root, [(42, 3), (42, 5), (42, 7)], {"split_contract_id": split_id, "validation_fraction": .2, "test_fraction": .2})
    payload = {
        "session_id": session_id, "name": "must not fit", "model_kind": "random_forest",
        "seeds": [3, 5, 7], "selection_metric": "f1", "split_contract_id": split_id,
    }
    if violation == "varying_splits":
        payload.update(randomness_protocol="SPLIT_VARIABILITY", training_seed=9)
    elif violation == "wrong_fixed_seed":
        payload.update(randomness_protocol="TRAINING_VARIABILITY", split_seed=99)
    else:
        payload.update(randomness_protocol="TRAINING_VARIABILITY", split_seed=42, validation_fraction=.3)

    response = client.post(endpoint, json=payload)

    assert response.status_code == 422, response.text
    assert "immutable SplitContract" in response.text
    assert not list((root / "runs").glob("*.json"))
    assert not list((root / "studies" / "jobs").glob("*.json"))


def test_study_job_rejects_an_unregistered_execution_backend_with_typed_error(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "unknown-backend-study"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Unknown backend"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    response = client.post("/api/projects/training/study-jobs", json={"session_id": session_id, "name": "invalid backend", "model_kind": "random_forest", "seeds": [51, 53, 59], "selection_metric": "f1", "execution_backend_key": "missing_backend", "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "RUNTIME_NOT_FOUND"


@pytest.mark.parametrize(("task", "model_kind"), [
    ("binary_classification", "linear_regression"),
    ("regression", "logistic_regression"),
])
def test_linear_adapter_rejects_model_kind_incompatible_with_dataset_task(tmp_path: Path, task: str, model_kind: str) -> None:
    client = TestClient(app)
    root = tmp_path / f"linear-kind-task-mismatch-{task}"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Linear kind mismatch"}).json()["session_id"]
    confirmed = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": task, "id_columns": []})
    assert confirmed.status_code == 200, confirmed.text

    response = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": model_kind, "split_seed": 42, "training_seed": 7})

    assert response.status_code == 422, response.text
    assert model_kind in response.text
    assert not list((root / "runs").glob("*.json"))


@pytest.mark.parametrize("endpoint", ["/api/projects/training/studies", "/api/projects/training/study-jobs"])
def test_study_rejects_linear_kind_task_mismatch_before_any_seed_fit(tmp_path: Path, endpoint: str) -> None:
    client = TestClient(app)
    root = tmp_path / endpoint.rsplit("/", 1)[-1]
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Study linear kind mismatch"}).json()["session_id"]
    confirmed = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []})
    assert confirmed.status_code == 200, confirmed.text

    response = client.post(endpoint, json={"session_id": session_id, "model_kind": "linear_regression", "seeds": [3, 5, 7], "selection_metric": "f1"})

    assert response.status_code == 422, response.text
    assert "linear_regression" in response.text
    assert not list((root / "runs").glob("*.json"))
    assert not list((root / "studies" / "jobs").glob("*.json"))


def test_reopen_integrity_rejects_persisted_linear_kind_task_mismatch(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "persisted-linear-kind-mismatch"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Persisted kind mismatch"}).json()["session_id"]
    confirmed = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []})
    assert confirmed.status_code == 200, confirmed.text
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": 7})
    assert trained.status_code == 201, trained.text
    run_path = root / "runs" / f"{trained.json()['run_id']}.json"
    payload = json.loads(run_path.read_text(encoding="utf-8"))
    payload["model_kind"] = "linear_regression"
    run_path.write_text(json.dumps(payload), encoding="utf-8")

    report = inspect_project_integrity(root)

    assert any(issue.code == "ADAPTER_IDENTITY" and issue.status == "FAIL" for issue in report.issues)


def test_study_job_list_exposes_legacy_model_runtime_identity_without_rewrite(tmp_path: Path) -> None:
    from ruflex.domain.training import StudyJob, StudySeedState

    client = TestClient(app)
    root = tmp_path / "legacy-study-job-list"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Legacy job list"}).json()["session_id"]
    legacy = StudyJob(
        schema_version=4,
        name="legacy random forest",
        model_kind="random_forest",
        selection_metric="f1",
        seed_states=[StudySeedState(seed=7, split_seed=42, training_seed=7)],
    )
    job_path = root / "studies" / "jobs" / f"{legacy.job_id}.json"
    job_path.parent.mkdir(parents=True, exist_ok=True)
    job_path.write_text(legacy.model_dump_json(indent=2), encoding="utf-8")
    original_bytes = job_path.read_bytes()

    response = client.get(f"/api/projects/{session_id}/training/study-jobs")

    assert response.status_code == 200, response.text
    listed = next(item for item in response.json() if item["job_id"] == str(legacy.job_id))
    assert (listed["adapter_key"], listed["adapter_version"]) == ("native_random_forest", "1")
    assert job_path.read_bytes() == original_bytes


def test_study_job_resume_rejects_changed_dataset_revision(tmp_path: Path) -> None:
    from ruflex.domain.training import StudyJob, StudySeedState

    client = TestClient(app)
    root = tmp_path / "study-job-dataset-binding"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Study dataset binding"}).json()["session_id"]
    first = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame(36).to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []})
    assert first.status_code == 200, first.text
    old_fingerprint = first.json()["contract"]["dataset_fingerprint"]
    job = StudyJob(
        name="bound to old data",
        model_kind="random_forest",
        selection_metric="f1",
        dataset_fingerprint=old_fingerprint,
        randomness_protocol="TRAINING_VARIABILITY",
        split_seed=42,
        seed_states=[StudySeedState(seed=seed, split_seed=42, training_seed=seed) for seed in [31, 37, 41]],
        execution_config={"max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3},
    )
    path = root / "studies" / "jobs" / f"{job.job_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(job.model_dump_json(), encoding="utf-8")

    second = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame(40).to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []})
    assert second.status_code == 200, second.text
    resumed = client.post(f"/api/projects/{session_id}/training/study-jobs/{job.job_id}/resume")
    assert resumed.status_code == 422
    assert "DatasetContract changed" in resumed.text
    persisted = client.get(f"/api/projects/{session_id}/training/study-jobs/{job.job_id}")
    assert persisted.status_code == 200
    assert persisted.json()["status"] == "QUEUED"


def test_persisted_study_job_rejects_incompatible_metric_before_resume_fits(tmp_path: Path) -> None:
    from ruflex.domain.training import StudyJob, StudySeedState

    root = tmp_path / "invalid-resume-metric"
    ProjectService().create(root, name="Invalid resume metric")
    _confirm_dataset(root, _binary_frame())
    contract = training_application.load_dataset_contract(root)
    job = StudyJob(
        name="old invalid request", model_kind="random_forest", selection_metric="rmse",
        dataset_fingerprint=contract.dataset_fingerprint,
        randomness_protocol="TRAINING_VARIABILITY", split_seed=42,
        seed_states=[StudySeedState(seed=seed, split_seed=42, training_seed=seed) for seed in (3, 5, 7)],
    )
    training_application._persist_study_job(root, job)

    training_application._execute_study_job(root, job.job_id)

    restored = training_application.load_study_job(root, job.job_id)
    assert restored.status == "FAILED"
    assert "no Study fits were started" in (restored.error or "")
    assert restored.study_id is None
    assert not list((root / "runs").glob("*.json"))


def test_persisted_study_job_rejects_incompatible_split_before_resume_fits(tmp_path: Path) -> None:
    from ruflex.domain.training import StudyJob, StudySeedState

    client = TestClient(app)
    root = tmp_path / "invalid-resume-split"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Invalid resume split"}).json()["session_id"]
    confirmed = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []})
    assert confirmed.status_code == 200, confirmed.text
    frozen = client.post("/api/projects/dataset/splits", json={"session_id": session_id, "family": "RANDOM", "split_seed": 42})
    assert frozen.status_code == 201, frozen.text
    contract = training_application.load_dataset_contract(root)
    job = StudyJob(
        name="old incompatible split request", model_kind="random_forest", selection_metric="f1",
        dataset_fingerprint=contract.dataset_fingerprint, randomness_protocol="SPLIT_VARIABILITY",
        seed_states=[StudySeedState(seed=9, split_seed=split_seed, training_seed=9) for split_seed in (11, 13, 17)],
        execution_config={"split_contract_id": frozen.json()["split_id"], "validation_fraction": .2, "test_fraction": .2},
    )
    training_application._persist_study_job(root, job)

    training_application._execute_study_job(root, job.job_id)

    restored = training_application.load_study_job(root, job.job_id)
    assert restored.status == "FAILED"
    assert "immutable SplitContract" in (restored.error or "")
    assert restored.study_id is None
    assert not list((root / "runs").glob("*.json"))


def test_study_job_aborts_if_dataset_revision_changes_during_seed_training(tmp_path: Path, monkeypatch) -> None:
    from ruflex.domain.training import StudyJob, StudySeedState

    root = tmp_path / "study-job-mid-run-dataset-change"
    ProjectService().create(root, name="Mid-run dataset change")
    _confirm_dataset(root, _binary_frame(36))
    original_contract = training_application.load_dataset_contract(root)
    job = StudyJob(
        schema_version=7,
        name="must not mix revisions",
        model_kind="random_forest",
        selection_metric="f1",
        dataset_fingerprint=original_contract.dataset_fingerprint,
        randomness_protocol="TRAINING_VARIABILITY",
        split_seed=42,
        adapter_key="native_random_forest",
        adapter_version="1",
        adapter_provider="ruflex.builtin",
        execution_backend_key="local_executor",
        execution_backend_version="1",
        execution_backend_provider="ruflex.builtin",
        seed_states=[StudySeedState(seed=seed, split_seed=42, training_seed=seed) for seed in (31, 37, 41)],
        execution_config={"n_estimators": 5, "max_depth": 3, "validation_fraction": .2, "test_fraction": .2},
    )
    training_application._persist_study_job(root, job)
    real_train_model = training_application.train_model
    calls = 0

    def train_then_replace_dataset(*args, **kwargs):
        nonlocal calls
        run = real_train_model(*args, **kwargs)
        calls += 1
        if calls == 1:
            _confirm_dataset(root, _binary_frame(40))
        return run

    monkeypatch.setattr(training_application, "train_model", train_then_replace_dataset)
    training_application._execute_study_job(root, job.job_id)

    persisted = training_application.load_study_job(root, job.job_id)
    assert calls == 1
    assert persisted.status == "FAILED"
    assert "changed during StudyJob execution" in (persisted.error or "")
    assert persisted.study_id is None
    assert [state.status for state in persisted.seed_states] == ["FAILED", "FAILED", "FAILED"]
    assert not (root / "studies" / "active-study.json").exists()


def test_persisted_study_job_resumes_without_replacing_declared_seeds(tmp_path: Path) -> None:
    from ruflex.domain.training import StudyJob, StudySeedState

    client = TestClient(app); root = tmp_path / "resumable-study"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Resumable study"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    dataset_fingerprint = client.get(f"/api/projects/{session_id}/dataset").json()["contract"]["dataset_fingerprint"]
    interrupted = StudyJob(
        schema_version=7, name="interrupted forest", model_kind="random_forest", selection_metric="f1", dataset_fingerprint=dataset_fingerprint, randomness_protocol="TRAINING_VARIABILITY", split_seed=42,
        adapter_key="native_random_forest", adapter_version="1", adapter_provider="ruflex.builtin",
        execution_backend_key="local_executor", execution_backend_version="1", execution_backend_provider="ruflex.builtin",
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
    assert (job["adapter_key"], job["adapter_version"]) == ("native_random_forest", "1")
    assert job["adapter_provider"] == "ruflex.builtin"
    assert [state["seed"] for state in job["seed_states"]] == [71, 73, 79]
    assert {state["status"] for state in job["seed_states"]} == {"SUCCEEDED"}


@pytest.mark.parametrize("corruption", ["seed_pair", "artifact_hash"])
def test_study_job_rejects_mismatched_completed_run_on_resume(tmp_path: Path, corruption: str) -> None:
    from ruflex.domain.training import StudyJob, StudySeedState

    root = tmp_path / corruption
    ProjectService().create(root, name="Completed run binding")
    _confirm_dataset(root, _binary_frame())
    run = training_application.train_model(
        root, model_kind="random_forest", split_seed=42, training_seed=5,
        n_estimators=5, max_depth=3,
    )
    run.randomness_protocol = "TRAINING_VARIABILITY"
    if corruption == "artifact_hash":
        run.model_artifact_sha256 = "0" * 64
    training_application.persist_training_run(root, run)
    declared_seed = 7 if corruption == "seed_pair" else 5
    job = StudyJob(
        name="resume frozen work", model_kind="random_forest", selection_metric="f1",
        dataset_fingerprint=run.dataset_fingerprint,
        randomness_protocol="TRAINING_VARIABILITY", split_seed=42,
        adapter_key=run.adapter_key, adapter_version=run.adapter_version,
        adapter_provider=run.adapter_provider,
        seed_states=[
            StudySeedState(seed=declared_seed, split_seed=42, training_seed=declared_seed, status="SUCCEEDED", run_id=run.run_id),
            StudySeedState(seed=11, split_seed=42, training_seed=11, status="FAILED", error="historical fit failure"),
            StudySeedState(seed=13, split_seed=42, training_seed=13, status="FAILED", error="historical fit failure"),
        ],
    )
    training_application._persist_study_job(root, job)

    training_application._execute_study_job(root, job.job_id)

    restored = training_application.load_study_job(root, job.job_id)
    assert restored.status == "FAILED"
    assert restored.study_id is None
    assert restored.seed_states[0].status == "FAILED"
    expected_error = "split_seed/training_seed pair" if corruption == "seed_pair" else "artifact is missing or invalid"
    assert expected_error in (restored.seed_states[0].error or "")
    assert not (root / "studies" / "active-study.json").exists()


def test_study_job_resume_accepts_legacy_seed_alias_without_rewriting_run(tmp_path: Path) -> None:
    from ruflex.domain.training import StudyJob, StudySeedState

    root = tmp_path / "legacy-completed-seed"
    ProjectService().create(root, name="Legacy completed seed")
    _confirm_dataset(root, _binary_frame())
    run = training_application.train_model(root, model_kind="random_forest", seed=5, n_estimators=5, max_depth=3)
    run_path = root / "runs" / f"{run.run_id}.json"
    original_run_bytes = run_path.read_bytes()
    job = StudyJob(
        schema_version=4, name="legacy resume", model_kind="random_forest", selection_metric="f1",
        dataset_fingerprint=run.dataset_fingerprint,
        seed_states=[
            StudySeedState(seed=5, status="SUCCEEDED", run_id=run.run_id),
            StudySeedState(seed=7, status="FAILED", error="historical failure"),
            StudySeedState(seed=9, status="FAILED", error="historical failure"),
        ],
    )
    training_application._persist_study_job(root, job)

    training_application._execute_study_job(root, job.job_id)

    restored = training_application.load_study_job(root, job.job_id)
    assert restored.status == "FAILED"  # one valid fit cannot produce a Study
    assert restored.seed_states[0].status == "SUCCEEDED"
    assert restored.seed_states[0].error is None
    assert run_path.read_bytes() == original_run_bytes


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
    assert evaluation["roc_curve"]
    assert evaluation["precision_recall_curve"]
    assert evaluation["roc_curve"][0]["x"] == 0.0
    assert evaluation["roc_curve"][-1]["x"] == 1.0

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


def test_validation_evaluation_recovers_after_active_pointer_write_failure(tmp_path: Path, monkeypatch) -> None:
    client = TestClient(app)
    root = tmp_path / "evaluation-recovery"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Evaluation recovery"}).json()["session_id"]
    confirmed = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []})
    assert confirmed.status_code == 200, confirmed.text
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": 31, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert trained.status_code == 201, trained.text

    original_write = training_application._atomic_write_text

    def fail_active_pointer(path, text):
        if Path(path).name == "active-evaluation.json":
            raise OSError("simulated active pointer failure")
        return original_write(path, text)

    monkeypatch.setattr(training_application, "_atomic_write_text", fail_active_pointer)
    created = client.post("/api/projects/analyses/evaluations", json={"session_id": session_id, "run_id": trained.json()["run_id"]})
    assert created.status_code == 500
    assert "look up the selected run" in created.json()["detail"]

    recovered = client.get(f"/api/projects/{session_id}/analyses/evaluations/by-run/{trained.json()['run_id']}/latest")
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["run_id"] == trained.json()["run_id"]
    assert recovered.json()["test_status"] == "LOCKED_NOT_EVALUATED"
    assert client.get(f"/api/projects/{session_id}/analyses/evaluations/latest").status_code == 404


def test_validation_evaluation_reopen_fails_closed_on_identity_or_pointer_corruption(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "evaluation-integrity"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Evaluation integrity"}).json()["session_id"]
    confirmed = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []})
    assert confirmed.status_code == 200, confirmed.text
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": 43, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert trained.status_code == 201, trained.text
    created = client.post("/api/projects/analyses/evaluations", json={"session_id": session_id, "run_id": trained.json()["run_id"]})
    assert created.status_code == 201, created.text
    evaluation = created.json()
    path = root / "analyses" / "evaluations" / f"{evaluation['evaluation_id']}.json"

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["evaluation_id"] = "00000000-0000-0000-0000-000000000001"
    path.write_text(json.dumps(payload), encoding="utf-8")
    exact = client.get(f"/api/projects/{session_id}/analyses/evaluations/{evaluation['evaluation_id']}")
    assert exact.status_code == 422
    assert "does not match" in exact.text
    latest = client.get(f"/api/projects/{session_id}/analyses/evaluations/latest")
    assert latest.status_code == 422
    assert "does not match" in latest.text

    (root / "analyses" / "evaluations" / "active-evaluation.json").write_text("{ malformed", encoding="utf-8")
    malformed_pointer = client.get(f"/api/projects/{session_id}/analyses/evaluations/latest")
    assert malformed_pointer.status_code == 422
    assert "pointer is malformed" in malformed_pointer.text


def test_validation_calibration_and_threshold_reopen_validate_persisted_identity(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "policy-object-integrity"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Policy object integrity"}).json()["session_id"]
    confirmed = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []})
    assert confirmed.status_code == 200, confirmed.text
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": 47, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert trained.status_code == 201, trained.text
    evaluation = client.post("/api/projects/analyses/evaluations", json={"session_id": session_id, "run_id": trained.json()["run_id"]})
    assert evaluation.status_code == 201, evaluation.text
    evaluation_id = evaluation.json()["evaluation_id"]
    calibration = client.post("/api/projects/analyses/calibrations", json={"session_id": session_id, "evaluation_id": evaluation_id})
    assert calibration.status_code == 201, calibration.text
    calibration_id = calibration.json()["calibration_id"]
    threshold = client.post("/api/projects/analyses/thresholds", json={"session_id": session_id, "evaluation_id": evaluation_id, "calibration_id": None, "objective": "f1"})
    assert threshold.status_code == 201, threshold.text
    threshold_id = threshold.json()["threshold_id"]
    selective = client.post("/api/projects/analyses/selective-policies", json={"session_id": session_id, "evaluation_id": evaluation_id, "confidence_cutoff": .7, "calibration_id": None, "threshold_id": threshold_id})
    assert selective.status_code == 201, selective.text
    selective_id = selective.json()["policy_id"]

    selective_path = root / "analyses" / "selective-policies" / f"{selective_id}.json"
    selective_payload = json.loads(selective_path.read_text(encoding="utf-8"))
    selective_payload["policy_id"] = "00000000-0000-0000-0000-000000000003"
    selective_path.write_text(json.dumps(selective_payload), encoding="utf-8")
    exact_selective = client.get(f"/api/projects/{session_id}/analyses/selective-policies/{selective_id}")
    latest_selective = client.get(f"/api/projects/{session_id}/analyses/selective-policies/latest")
    assert exact_selective.status_code == latest_selective.status_code == 422
    assert "identity does not match" in exact_selective.text

    calibration_path = root / "analyses" / "calibrations" / f"{calibration_id}.json"
    calibration_payload = json.loads(calibration_path.read_text(encoding="utf-8"))
    calibration_payload["calibration_id"] = "00000000-0000-0000-0000-000000000001"
    calibration_path.write_text(json.dumps(calibration_payload), encoding="utf-8")
    exact_calibration = client.get(f"/api/projects/{session_id}/analyses/calibrations/{calibration_id}")
    latest_calibration = client.get(f"/api/projects/{session_id}/analyses/calibrations/latest")
    assert exact_calibration.status_code == latest_calibration.status_code == 422
    assert "identity does not match" in exact_calibration.text

    threshold_path = root / "analyses" / "thresholds" / f"{threshold_id}.json"
    threshold_payload = json.loads(threshold_path.read_text(encoding="utf-8"))
    threshold_payload["threshold_id"] = "00000000-0000-0000-0000-000000000002"
    threshold_path.write_text(json.dumps(threshold_payload), encoding="utf-8")
    exact_threshold = client.get(f"/api/projects/{session_id}/analyses/thresholds/{threshold_id}")
    latest_threshold = client.get(f"/api/projects/{session_id}/analyses/thresholds/latest")
    assert exact_threshold.status_code == latest_threshold.status_code == 422
    assert "identity does not match" in exact_threshold.text

    (root / "analyses" / "thresholds" / "active-threshold.json").write_text("{ malformed", encoding="utf-8")
    malformed_pointer = client.get(f"/api/projects/{session_id}/analyses/thresholds/latest")
    assert malformed_pointer.status_code == 422
    assert "pointer is malformed" in malformed_pointer.text


def test_validation_threshold_recovers_by_evaluation_after_active_pointer_write_failure(tmp_path: Path, monkeypatch) -> None:
    client = TestClient(app)
    root = tmp_path / "threshold-recovery"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Threshold recovery"}).json()["session_id"]
    confirmed = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []})
    assert confirmed.status_code == 200, confirmed.text
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": 32, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert trained.status_code == 201, trained.text
    evaluation = client.post("/api/projects/analyses/evaluations", json={"session_id": session_id, "run_id": trained.json()["run_id"]})
    assert evaluation.status_code == 201, evaluation.text

    original_write = training_application._atomic_write_text

    def fail_active_pointer(path, text):
        if Path(path).name == "active-threshold.json":
            raise OSError("simulated active threshold pointer failure")
        return original_write(path, text)

    monkeypatch.setattr(training_application, "_atomic_write_text", fail_active_pointer)
    selected = client.post("/api/projects/analyses/thresholds", json={"session_id": session_id, "evaluation_id": evaluation.json()["evaluation_id"], "calibration_id": None, "objective": "f1"})
    assert selected.status_code == 500
    assert "look up the exact Evaluation" in selected.json()["detail"]

    recovered = client.get(f"/api/projects/{session_id}/analyses/thresholds/by-evaluation/{evaluation.json()['evaluation_id']}/latest", params={"calibration_source": "raw"})
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["evaluation_id"] == evaluation.json()["evaluation_id"]
    assert recovered.json()["calibration_id"] is None
    assert recovered.json()["probability_source"] == "raw"
    assert client.get(f"/api/projects/{session_id}/analyses/thresholds/latest").status_code == 404


def test_calibration_and_selective_policy_recover_by_exact_binding_after_pointer_failure(tmp_path: Path, monkeypatch) -> None:
    client = TestClient(app)
    root = tmp_path / "validation-policy-recovery"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Validation policy recovery"}).json()["session_id"]
    confirmed = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []})
    assert confirmed.status_code == 200, confirmed.text
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": 33, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert trained.status_code == 201, trained.text
    evaluation = client.post("/api/projects/analyses/evaluations", json={"session_id": session_id, "run_id": trained.json()["run_id"]})
    assert evaluation.status_code == 201, evaluation.text
    evaluation_id = evaluation.json()["evaluation_id"]

    original_training_write = training_application._atomic_write_text

    def fail_calibration_pointer(path, text):
        if Path(path).name == "active-calibration.json":
            raise OSError("simulated active calibration pointer failure")
        return original_training_write(path, text)

    monkeypatch.setattr(training_application, "_atomic_write_text", fail_calibration_pointer)
    calibration_response = client.post("/api/projects/analyses/calibrations", json={"session_id": session_id, "evaluation_id": evaluation_id})
    assert calibration_response.status_code == 500
    assert "exact Evaluation" in calibration_response.json()["detail"]
    calibration_lookup = f"/api/projects/{session_id}/analyses/calibrations/by-evaluation/{evaluation_id}/latest"
    recovered_calibration = client.get(calibration_lookup)
    assert recovered_calibration.status_code == 200, recovered_calibration.text
    calibration_id = recovered_calibration.json()["calibration_id"]
    assert recovered_calibration.json()["evaluation_id"] == evaluation_id
    assert recovered_calibration.json()["source_split"] == "validation"
    assert client.get(f"/api/projects/{session_id}/analyses/calibrations/latest").status_code == 404
    other_evaluation = "00000000-0000-4000-8000-000000000001"
    assert client.get(f"/api/projects/{session_id}/analyses/calibrations/by-evaluation/{other_evaluation}/latest").status_code == 404

    threshold = client.post("/api/projects/analyses/thresholds", json={"session_id": session_id, "evaluation_id": evaluation_id, "calibration_id": calibration_id, "objective": "f1"})
    assert threshold.status_code == 201, threshold.text
    threshold_id = threshold.json()["threshold_id"]

    from ruflex.application import selective as selective_application
    original_selective_write = selective_application._atomic_write_text

    def fail_selective_pointer(path, text):
        if Path(path).name == "active-policy.json":
            raise OSError("simulated active selective policy pointer failure")
        return original_selective_write(path, text)

    monkeypatch.setattr(selective_application, "_atomic_write_text", fail_selective_pointer)
    policy_request = {"session_id": session_id, "evaluation_id": evaluation_id, "confidence_cutoff": .8, "calibration_id": calibration_id, "threshold_id": threshold_id}
    policy_response = client.post("/api/projects/analyses/selective-policies", json=policy_request)
    assert policy_response.status_code == 500
    assert "exact request binding" in policy_response.json()["detail"]
    lookup = f"/api/projects/{session_id}/analyses/selective-policies/by-binding/latest"
    recovered_policy = client.get(lookup, params={key: value for key, value in policy_request.items() if key != "session_id"})
    assert recovered_policy.status_code == 200, recovered_policy.text
    assert recovered_policy.json()["evaluation_id"] == evaluation_id
    assert recovered_policy.json()["calibration_id"] == calibration_id
    assert recovered_policy.json()["class_threshold_id"] == threshold_id
    assert recovered_policy.json()["confidence_cutoff"] == .8
    assert client.get(f"/api/projects/{session_id}/analyses/selective-policies/latest").status_code == 404
    mismatched = client.get(lookup, params={"evaluation_id": evaluation_id, "confidence_cutoff": .85, "calibration_id": calibration_id, "threshold_id": threshold_id})
    assert mismatched.status_code == 404


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
    assert inspect_project_integrity(root).status == "PASS"
    comparison_path = root / "analyses" / "comparisons" / f"{comparison['comparison_id']}.json"
    comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
    original_f1 = comparison_payload["metric_rows"][0]["f1"]
    comparison_payload["metric_rows"][0]["f1"] = 0.0 if original_f1 > 0.0 else 1.0
    comparison_path.write_text(json.dumps(comparison_payload), encoding="utf-8")
    corrupted_comparison = inspect_project_integrity(root)
    assert any(issue.code == "ANALYSIS_COMPARISON_PROVENANCE_MISMATCH" for issue in corrupted_comparison.issues)
    comparison_payload["metric_rows"][0]["f1"] = original_f1
    comparison_path.write_text(json.dumps(comparison_payload), encoding="utf-8")

    reopened = client.get(f"/api/projects/{session_id}/analyses/comparisons/latest")
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["comparison_id"] == comparison["comparison_id"]

    duplicate = client.post("/api/projects/analyses/comparisons", json={"session_id": session_id, "run_ids": [run_ids[0], run_ids[0]]})
    assert duplicate.status_code == 422


def test_validation_comparison_fails_closed_on_malformed_policy_evidence(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "comparison-policy-integrity"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Comparison policy integrity"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    runs = []
    for seed in [61, 62]:
        trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": seed, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
        assert trained.status_code == 201, trained.text
        runs.append(trained.json())
    evaluation = client.post("/api/projects/analyses/evaluations", json={"session_id": session_id, "run_id": runs[0]["run_id"]})
    assert evaluation.status_code == 201, evaluation.text
    threshold = client.post("/api/projects/analyses/thresholds", json={"session_id": session_id, "evaluation_id": evaluation.json()["evaluation_id"], "objective": "f1"})
    assert threshold.status_code == 201, threshold.text
    (root / "analyses" / "thresholds" / f"{threshold.json()['threshold_id']}.json").write_text("{ malformed", encoding="utf-8")

    comparison = client.post("/api/projects/analyses/comparisons", json={"session_id": session_id, "run_ids": [run["run_id"] for run in runs]})
    assert comparison.status_code == 422
    assert "threshold evidence is malformed" in comparison.text



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

    single_run_only = client.post(
        "/api/projects/analyses/comparisons",
        json={"session_id": session_id, "run_ids": [logistic.json()["run_id"]]},
    )
    assert single_run_only.status_code == 422
    single_with_fis = client.post(
        "/api/projects/analyses/comparisons",
        json={"session_id": session_id, "run_ids": [logistic.json()["run_id"]], "include_active_fis": True,
              "expected_fis_id": fis.json()["fis_id"], "expected_fis_semantic_hash": fis.json()["semantic_hash"]},
    )
    assert single_with_fis.status_code == 201, single_with_fis.text
    assert single_with_fis.json()["run_ids"] == [logistic.json()["run_id"]]
    assert len(single_with_fis.json()["metric_rows"]) == 2
    assert single_with_fis.json()["fis_semantic_hash"] == fis.json()["semantic_hash"]
    assert inspect_project_integrity(root).status == "PASS"
    assert client.post("/api/projects/evidence/assurance-cases", json={"session_id": session_id}).status_code == 201
    bundle_response = client.post("/api/projects/evidence/verification-bundles", json={"session_id": session_id})
    assert bundle_response.status_code == 201, bundle_response.text
    from ruflex.application.verification_bundle import validate_verification_bundle
    assert validate_verification_bundle(bundle_response.json()["path"]).status == "PASS"

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
    revised_fis = fis.json()
    revised_fis["operators"]["centroid_resolution"] += 1
    saved_revision = client.post("/api/projects/fis/save", json={"session_id": session_id, "spec": revised_fis})
    assert saved_revision.status_code == 200, saved_revision.text
    assert saved_revision.json()["semantic_hash"] != fis.json()["semantic_hash"]
    assert inspect_project_integrity(root).status == "PASS"
    refreshed_bundle = client.post("/api/projects/evidence/verification-bundles", json={"session_id": session_id})
    assert refreshed_bundle.status_code == 201, refreshed_bundle.text
    assert validate_verification_bundle(refreshed_bundle.json()["path"]).status == "PASS"
    stale_revision_request = client.post(
        "/api/projects/analyses/comparisons",
        json={"session_id": session_id, "run_ids": [logistic.json()["run_id"]], "include_active_fis": True,
              "expected_fis_id": fis.json()["fis_id"], "expected_fis_semantic_hash": fis.json()["semantic_hash"]},
    )
    assert stale_revision_request.status_code == 422
    assert "exact saved revision" in stale_revision_request.text

    comparison_relative = Path("analyses/comparisons") / f"{comparison['comparison_id']}.json"
    comparison_path = root / comparison_relative
    original_comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    altered_comparison = json.loads(json.dumps(original_comparison))
    next(row for row in altered_comparison["metric_rows"] if row["subject_type"] == "manual_fis")["model_artifact"] = "wrong-hash"
    comparison_path.write_text(json.dumps(altered_comparison), encoding="utf-8")
    assert any(issue.code == "ANALYSIS_COMPARISON_PROVENANCE_MISMATCH" for issue in inspect_project_integrity(root).issues)
    damaged_assurance = client.post("/api/projects/evidence/assurance-cases", json={"session_id": session_id})
    assert damaged_assurance.status_code == 201
    assert next(gate for gate in damaged_assurance.json()["gates"] if gate["key"] == "project_integrity")["status"] == "FAIL"
    comparison_path.write_text(json.dumps(original_comparison), encoding="utf-8")
    assert inspect_project_integrity(root).status == "PASS"
    missing_fis_row = json.loads(json.dumps(original_comparison))
    missing_fis_row["metric_rows"] = [row for row in missing_fis_row["metric_rows"] if row["subject_type"] != "manual_fis"]
    comparison_path.write_text(json.dumps(missing_fis_row), encoding="utf-8")
    assert any(issue.code == "ANALYSIS_COMPARISON_PROVENANCE_MISMATCH" for issue in inspect_project_integrity(root).issues)
    comparison_path.write_text(json.dumps(original_comparison), encoding="utf-8")

    extracted = tmp_path / "manual-fis-comparison-bundle"
    shutil.unpack_archive(refreshed_bundle.json()["path"], extracted, "zip")
    bundled_comparison = extracted / comparison_relative
    bundled_comparison.write_text(json.dumps(altered_comparison), encoding="utf-8")
    manifest_path = extracted / "verification-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checksums"][comparison_relative.as_posix()] = hashlib.sha256(bundled_comparison.read_bytes()).hexdigest()
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode()
    manifest_path.write_bytes(manifest_bytes)
    (extracted / "verification-manifest.sha256").write_text(f"{hashlib.sha256(manifest_bytes).hexdigest()}  verification-manifest.json\n", encoding="utf-8")
    assert validate_verification_bundle(extracted).status == "FAIL"


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
    assert run["trajectory"] == []
    assert "train_loss" not in run["training_summary"]
    assert "best_epoch" not in run["training_summary"]
    assert run["training_summary"]["validation_metrics"] == run["validation_metrics"]
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
    assert run["trajectory"] == []
    assert "train_loss" not in run["training_summary"]
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
    assert inspect_project_integrity(root).status == "PASS"
    assert client.post("/api/projects/evidence/assurance-cases", json={"session_id": session_id}).status_code == 201
    bundle_response = client.post("/api/projects/evidence/verification-bundles", json={"session_id": session_id})
    assert bundle_response.status_code == 201, bundle_response.text
    from ruflex.application.verification_bundle import validate_verification_bundle
    bundle_validation = validate_verification_bundle(bundle_response.json()["path"])
    assert bundle_validation.status == "PASS", bundle_validation.errors
    assert any("exact path replay is unavailable" in warning for warning in bundle_validation.warnings)
    evidence_path = root / "evidence" / "tree-paths" / f"{evidence.json()['evidence_id']}.json"
    tampered = json.loads(evidence_path.read_text(encoding="utf-8"))
    tampered["prediction"] += 1.0
    evidence_path.write_text(json.dumps(tampered), encoding="utf-8")
    report = inspect_project_integrity(root)
    assert any(issue.code == "TREE_PATH_PROVENANCE_MISMATCH" for issue in report.issues)


def test_random_forest_persists_all_trees_without_claiming_one_exact_ensemble_path(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "forest"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Forest"}).json()["session_id"]
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _binary_frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "random_forest", "seed": 31, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert trained.status_code == 201, trained.text
    run = trained.json()
    assert run["model_kind"] == "random_forest"
    assert run["trajectory"] == []
    assert "train_loss" not in run["training_summary"]
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
    assert run["trajectory"] == []
    assert "train_loss" not in run["training_summary"]
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
    assert final_test["roc_curve"]
    assert final_test["precision_recall_curve"]

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

    late_calibration = client.post(
        "/api/projects/analyses/calibrations",
        json={"session_id": session_id, "evaluation_id": evaluation["evaluation_id"]},
    )
    assert late_calibration.status_code == 422
    assert "Final-test evidence already exists" in late_calibration.text
    alternate_threshold = client.post(
        "/api/projects/analyses/thresholds",
        json={"session_id": session_id, "evaluation_id": evaluation["evaluation_id"], "objective": "f1"},
    )
    assert alternate_threshold.status_code == 422
    assert "Final-test evidence already exists" in alternate_threshold.text

    late_fit = client.post(
        "/api/projects/training/run",
        json={
            "session_id": session_id,
            "model_kind": "logistic_regression",
            "seed": 99,
            "max_epochs": 1,
            "learning_rate": .01,
            "batch_size": 16,
            "patience": 1,
            "validation_fraction": .2,
            "test_fraction": .2,
            "max_rules": 3,
        },
    )
    assert late_fit.status_code == 422
    assert "Final-test evidence already exists" in late_fit.text
    late_study = client.post(
        "/api/projects/training/studies",
        json={
            "session_id": session_id,
            "name": "late study must not start",
            "model_kind": "logistic_regression",
            "seeds": [101, 102, 103],
            "selection_metric": "f1",
            "randomness_protocol": "TRAINING_VARIABILITY",
            "split_seed": 71,
            "max_epochs": 1,
            "learning_rate": .01,
            "batch_size": 16,
            "patience": 1,
            "validation_fraction": .2,
            "test_fraction": .2,
            "max_rules": 3,
        },
    )
    assert late_study.status_code == 422
    assert "Final-test evidence already exists" in late_study.text
    late_study_job = client.post(
        "/api/projects/training/study-jobs",
        json={
            "session_id": session_id,
            "name": "late queued study must not start",
            "model_kind": "logistic_regression",
            "seeds": [201, 202, 203],
            "selection_metric": "f1",
            "randomness_protocol": "TRAINING_VARIABILITY",
            "split_seed": 71,
            "max_epochs": 1,
            "learning_rate": .01,
            "batch_size": 16,
            "patience": 1,
            "validation_fraction": .2,
            "test_fraction": .2,
            "max_rules": 3,
        },
    )
    assert late_study_job.status_code == 422
    assert "Final-test evidence already exists" in late_study_job.text

    # A damaged immutable holdout record must fail closed, not be skipped and
    # treated as permission to perform another final-test opening.
    final_test_path = root / "analyses" / "final-tests" / f"{final_test['final_test_id']}.json"
    final_test_path.write_text("{ malformed", encoding="utf-8")
    corrupted_reopen = client.post(
        "/api/projects/analyses/final-test",
        json={
            "session_id": session_id,
            "evaluation_id": evaluation["evaluation_id"],
            "calibration_id": calibration["calibration_id"],
            "threshold_id": threshold["threshold_id"],
        },
    )
    assert corrupted_reopen.status_code == 422
    assert "unreadable" in corrupted_reopen.text.lower()
    exact_corrupt_read = client.get(f"/api/projects/{session_id}/analyses/final-test/{final_test['final_test_id']}")
    assert exact_corrupt_read.status_code == 422
    assert "malformed" in exact_corrupt_read.text.lower()
    (root / "analyses" / "final-tests" / "active-final-test.json").write_text("{ malformed", encoding="utf-8")
    corrupt_pointer_read = client.get(f"/api/projects/{session_id}/analyses/final-test/latest")
    assert corrupt_pointer_read.status_code == 422
    assert "malformed" in corrupt_pointer_read.text.lower()

    # The immutable TrainingRun remains explicitly validation-oriented; final-test
    # evidence exists only in its separate, explicit analysis object.
    run_after = client.get(f"/api/projects/{session_id}/training/runs/{run['run_id']}").json()
    assert run_after["split"]["test_status"] == "LOCKED_NOT_EVALUATED"


def test_new_dataset_revision_gets_an_independent_validation_policy_boundary(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "revision-policy-boundary"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Revision boundary"}).json()["session_id"]
    first = _binary_frame(36)
    assert client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": first.to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []}).status_code == 200
    run = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": 51, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert run.status_code == 201, run.text
    evaluation = client.post("/api/projects/analyses/evaluations", json={"session_id": session_id, "run_id": run.json()["run_id"]})
    assert evaluation.status_code == 201, evaluation.text
    threshold = client.post("/api/projects/analyses/thresholds", json={"session_id": session_id, "evaluation_id": evaluation.json()["evaluation_id"], "objective": "f1"})
    assert threshold.status_code == 201, threshold.text
    final_test = client.post("/api/projects/analyses/final-test", json={"session_id": session_id, "evaluation_id": evaluation.json()["evaluation_id"], "threshold_id": threshold.json()["threshold_id"]})
    assert final_test.status_code == 201, final_test.text

    second = _binary_frame(40)
    confirmed = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": second.to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []})
    assert confirmed.status_code == 200, confirmed.text
    new_run = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "decision_tree", "seed": 52, "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert new_run.status_code == 201, new_run.text
    new_evaluation = client.post("/api/projects/analyses/evaluations", json={"session_id": session_id, "run_id": new_run.json()["run_id"]})
    assert new_evaluation.status_code == 201, new_evaluation.text
    new_threshold = client.post("/api/projects/analyses/thresholds", json={"session_id": session_id, "evaluation_id": new_evaluation.json()["evaluation_id"], "objective": "f1"})
    assert new_threshold.status_code == 201, new_threshold.text
    assert new_run.json()["dataset_fingerprint"] == confirmed.json()["contract"]["dataset_fingerprint"]
    assert new_run.json()["dataset_fingerprint"] != run.json()["dataset_fingerprint"]
