from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from ruflex.api.main import app
from ruflex.application.datasets import (
    DatasetConfirmationError,
    build_dataset_contract,
    create_split_contract,
    inspect_dataset,
    load_split_contract,
    persist_dataset_bytes,
    persist_dataset_contract,
)
from ruflex.application.datasets import run_data_audit
from ruflex.application.lineage import build_project_lineage
from ruflex.application.project_integrity import inspect_project_integrity
from ruflex.data.datasets import DatasetConfig, TabularDataset


def _frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for group in range(15):
        for repeat in range(3):
            rows.append({"patient_id": f"p{group}", "x": float(group * 3 + repeat), "target": group % 2})
    return pd.DataFrame(rows)


def test_group_split_contract_is_persisted_exact_and_never_leaks_groups(tmp_path) -> None:
    frame = _frame()
    artifact = persist_dataset_bytes(tmp_path, frame.to_csv(index=False).encode(), original_name="groups.csv")
    profile = inspect_dataset(frame, source_artifact_sha256=artifact.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification", id_columns=["patient_id"])
    persist_dataset_contract(tmp_path, contract, report=run_data_audit(contract, frame), profile=profile)
    split_contract = create_split_contract(tmp_path, family="GROUP", group_column="patient_id", split_seed=19)
    reopened = load_split_contract(tmp_path, split_contract.split_id)
    assert reopened == split_contract
    groups = {role: set(frame.loc[list(indices), "patient_id"]) for role, indices in reopened.role_source_rows.items()}
    assert not (groups["train"] & groups["validation"])
    assert not (groups["train"] & groups["test"])
    assert not (groups["validation"] & groups["test"])
    split = TabularDataset.from_dataframe(frame).split(DatasetConfig(
        target_column="target", feature_columns=("x",), explicit_split_source_rows=reopened.role_source_rows,
    ))
    assert set(split.train_indices) == set(reopened.role_source_rows["train"])
    assert set(split.validation_indices) == set(reopened.role_source_rows["validation"])
    assert set(split.test_indices) == set(reopened.role_source_rows["test"])


def test_group_split_requires_a_contract_column_and_exact_dataset(tmp_path) -> None:
    frame = _frame()
    artifact = persist_dataset_bytes(tmp_path, frame.to_csv(index=False).encode(), original_name="groups.csv")
    profile = inspect_dataset(frame, source_artifact_sha256=artifact.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification", id_columns=["patient_id"])
    persist_dataset_contract(tmp_path, contract, report=run_data_audit(contract, frame), profile=profile)
    with pytest.raises(DatasetConfirmationError, match="group column"):
        create_split_contract(tmp_path, family="GROUP", group_column="missing", split_seed=19)


def test_split_contract_api_survives_close_reopen_and_training_uses_it(tmp_path) -> None:
    client = TestClient(app)
    root = tmp_path / "group-project"
    created = client.post("/api/projects", json={"path": str(root), "name": "group"}).json()
    session_id = created["session_id"]
    rows = ["patient_id,x,target"] + [f"p{group},{group * 3 + repeat},{group % 2}" for group in range(12) for repeat in range(3)]
    confirmed = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": "\n".join(rows), "target": "target", "task": "binary_classification", "id_columns": ["patient_id"]})
    assert confirmed.status_code == 200, confirmed.text
    made = client.post("/api/projects/dataset/splits", json={"session_id": session_id, "family": "GROUP", "group_column": "patient_id", "split_seed": 7, "validation_fraction": .2, "test_fraction": .2})
    assert made.status_code == 201, made.text
    split_id = made.json()["split_id"]
    assert client.get(f"/api/projects/{session_id}/dataset/splits/{split_id}").status_code == 200
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": 7, "split_contract_id": split_id, "max_epochs": 1, "learning_rate": .01, "batch_size": 8, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert trained.status_code == 201, trained.text
    assert trained.json()["split"]["family"] == "group"
    assert trained.json()["split"]["split_contract_id"] == split_id
    client.post("/api/projects/close", json={"session_id": session_id})
    reopened = client.post("/api/projects/open", json={"path": str(root)}).json()
    latest = client.get(f"/api/projects/{reopened['session_id']}/training/latest")
    assert latest.status_code == 200
    assert latest.json()["split"]["split_contract_id"] == split_id
    pipeline_id = latest.json()["transform_pipeline_id"]
    pipeline = client.get(f"/api/projects/{reopened['session_id']}/dataset/transforms/{pipeline_id}")
    assert pipeline.status_code == 200
    assert all(step["fit_role"] == "TRAIN" for step in pipeline.json()["steps"])
    lineage = build_project_lineage(root)
    assert any(node.kind == "split_contract" for node in lineage.nodes)
    assert inspect_project_integrity(root).status == "PASS"
