from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from ruflex.api.main import app
from ruflex.application.datasets import build_dataset_contract, inspect_dataset, persist_dataset_bytes, persist_dataset_contract, run_data_audit
from ruflex.application.projects import ProjectService
from ruflex.application.training import TrainingError, list_training_runs, train_model


def _confirm(root: Path, frame: pd.DataFrame) -> None:
    ProjectService().create(root, name="Training input preflight")
    source = persist_dataset_bytes(root, frame.to_csv(index=False).encode())
    profile = inspect_dataset(frame, source_artifact_sha256=source.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification")
    persist_dataset_contract(root, contract, run_data_audit(contract, frame), profile)


@pytest.mark.parametrize("model_kind", ["flat_neuro_fuzzy", "logistic_regression", "decision_tree", "random_forest", "gradient_boosting", "mlp"])
def test_single_class_train_is_rejected_before_any_model_fit(tmp_path, monkeypatch, model_kind):
    root = tmp_path / model_kind
    _confirm(root, pd.DataFrame({"x": [10, 20, 30], "target": [0, 1, 1]}))
    fit_calls = []

    def unexpected_fit(*args, **kwargs):
        fit_calls.append(True)
        raise AssertionError("A model fit must not start with a single TRAIN class")

    monkeypatch.setattr("ruflex.runtime.builtins._BuiltinAdapter.fit", unexpected_fit)
    with pytest.raises(TrainingError, match="TRAIN_REQUIRES_BOTH_BINARY_CLASSES"):
        train_model(root, model_kind=model_kind, split_seed=42, training_seed=42)
    assert fit_calls == []
    assert list_training_runs(root) == []


def test_binary_target_is_not_silently_cast_from_other_labels(tmp_path, monkeypatch):
    root = tmp_path / "labels"
    _confirm(root, pd.DataFrame({"x": range(40), "target": [1, 2] * 20}))
    with pytest.raises(TrainingError, match="BINARY_TARGET_LABELS_INVALID"):
        train_model(root, model_kind="decision_tree", seed=42)
    assert list_training_runs(root) == []


def test_tiny_dataset_api_reports_data_problem_not_unavailable_adapter(tmp_path):
    client = TestClient(app)
    created = client.post("/api/projects", json={"path": str(tmp_path / "api"), "name": "Tiny dataset"})
    session_id = created.json()["session_id"]
    confirmed = client.post("/api/projects/dataset/confirm", json={
        "session_id": session_id, "csv_text": "x,target\n10,0\n20,1\n30,1\n",
        "target": "target", "task": "binary_classification", "id_columns": [],
    })
    assert confirmed.status_code == 200
    result = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "decision_tree"})
    assert result.status_code == 422
    assert result.json()["code"] == "VALIDATION_FAILED"
    assert "TRAIN_REQUIRES_BOTH_BINARY_CLASSES" in result.json()["detail"]
    assert "unavailable model adapter" not in result.text


@pytest.mark.parametrize("tiny", [True, False])
def test_decision_tree_study_reports_real_data_error_or_succeeds(tmp_path, monkeypatch, tiny):
    from ruflex.application.training import _execute_study_job, load_study_job, start_study_job

    root = tmp_path / "study"
    frame = pd.DataFrame({"x": [10, 20, 30], "target": [0, 1, 1]}) if tiny else pd.DataFrame({"x": range(80), "target": [0, 1] * 40})
    _confirm(root, frame)
    monkeypatch.setattr("ruflex.application.training._submit_study_job", lambda root, job_id: load_study_job(root, job_id))
    job = start_study_job(root, name="Decision tree input regression", model_kind="decision_tree", seeds=[42, 43, 44], selection_metric="f1", randomness_protocol="TRAINING_VARIABILITY", split_seed=42)
    _execute_study_job(root, job.job_id)
    restored = load_study_job(root, job.job_id)
    if tiny:
        assert restored.status == "FAILED"
        assert all("TRAIN_REQUIRES_BOTH_BINARY_CLASSES" in state.error for state in restored.seed_states)
        assert list_training_runs(root) == []
    else:
        assert restored.status == "SUCCEEDED"
        assert all(state.status == "SUCCEEDED" and state.error is None for state in restored.seed_states)
        assert len(list_training_runs(root)) == 3
