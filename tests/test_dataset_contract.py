import base64
from io import BytesIO

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from ruflex.application.datasets import DatasetConfirmationError, build_dataset_contract, inspect_dataset, load_dataset_contract, persist_dataset_contract, run_data_audit
from ruflex.api.main import app


def _fixture() -> pd.DataFrame:
    return pd.DataFrame({"entity_id": ["a", "b", "b"], "temperature": [10.0, None, None], "mode": ["normal", "normal", "normal"], "target": [0, 1, 1]})


def test_profile_surfaces_id_duplicates_missing_constant_and_deterministic_audit() -> None:
    profile = inspect_dataset(_fixture(), source_artifact_sha256="a" * 64)
    assert "entity_id" in profile.id_candidates
    contract = build_dataset_contract(profile, target="target", task="binary_classification", id_columns=["entity_id"])
    first, second = run_data_audit(contract, _fixture()), run_data_audit(contract, _fixture())
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert {finding.code for finding in first.findings} >= {"DUPLICATE_ROWS", "MISSING_VALUES", "CONSTANT_COLUMN"}
    assert "entity_id" not in contract.feature_columns


def test_target_requires_explicit_confirmation_and_schema_mismatch_is_detected() -> None:
    profile = inspect_dataset(_fixture(), source_artifact_sha256="b" * 64)
    with pytest.raises(DatasetConfirmationError, match="Target"):
        build_dataset_contract(profile, target=None, task="binary_classification")
    contract = build_dataset_contract(profile, target="target", task="binary_classification", id_columns=["entity_id"])
    comparison = contract.compare_schema(pd.DataFrame({"entity_id": ["x"], "temperature": [1], "target": [0], "new": [1]}))
    assert not comparison.compatible
    assert "mode" in comparison.missing_columns


def test_contract_and_audit_persist_without_mutating_source_frame(tmp_path) -> None:
    frame = _fixture(); before = frame.copy(deep=True); profile = inspect_dataset(frame, source_artifact_sha256="c" * 64)
    contract = build_dataset_contract(profile, target="target", task="binary_classification", id_columns=["entity_id"])
    persist_dataset_contract(tmp_path, contract, run_data_audit(contract, frame))
    assert load_dataset_contract(tmp_path) == contract
    assert frame.equals(before)


def test_csv_inspect_confirm_and_reopen_contract_through_api(tmp_path) -> None:
    client = TestClient(app); root = tmp_path / "project"; created = client.post("/api/projects", json={"path": str(root), "name": "Dataset"}).json()
    csv_text = "entity_id,temperature,target\na,10,0\nb,,1\nb,,1\n"
    inspected = client.post("/api/projects/dataset/inspect", json={"session_id": created["session_id"], "csv_text": csv_text})
    confirmed = client.post("/api/projects/dataset/confirm", json={"session_id": created["session_id"], "csv_text": csv_text, "target": "target", "task": "binary_classification", "id_columns": ["entity_id"]})
    assert inspected.status_code == 200 and "entity_id" in inspected.json()["profile"]["id_candidates"]
    assert confirmed.status_code == 200 and (root / "data" / "dataset-contract.json").is_file()
    assert load_dataset_contract(root).target == "target"


def test_xlsx_import_is_persisted_as_an_artifact_and_reopens(tmp_path) -> None:
    workbook = BytesIO()
    pd.DataFrame({"temperature": [10, 20], "target": [0, 1]}).to_excel(workbook, index=False)
    client = TestClient(app)
    created = client.post("/api/projects", json={"path": str(tmp_path / "xlsx-project"), "name": "xlsx"})
    session_id = created.json()["session_id"]
    imported = client.post(
        "/api/projects/dataset/import",
        json={
            "session_id": session_id,
            "filename": "measurements.xlsx",
            "content_base64": base64.b64encode(workbook.getvalue()).decode(),
            "target": "target",
            "task": "binary_classification",
            "id_columns": [],
        },
    )
    assert imported.status_code == 200, imported.text
    state = client.get(f"/api/projects/{session_id}/dataset")
    assert state.status_code == 200, state.text
    assert state.json()["contract"]["source_format"] == "xlsx"


def test_dataset_upload_rejects_extension_content_mismatch_before_persistence(tmp_path) -> None:
    client = TestClient(app)
    created = client.post("/api/projects", json={"path": str(tmp_path / "invalid-project"), "name": "invalid"})
    response = client.post(
        "/api/projects/dataset/import",
        json={
            "session_id": created.json()["session_id"],
            "filename": "not-a-workbook.xlsx",
            "content_base64": base64.b64encode(b"temperature,target\n10,0\n").decode(),
            "target": "target",
            "task": "binary_classification",
            "id_columns": [],
        },
    )
    assert response.status_code == 422
    assert "mismatch" in response.json()["detail"]
