import base64
import hashlib
import json
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from ruflex.application.datasets import DatasetConfirmationError, build_dataset_contract, inspect_dataset, load_dataset_contract, persist_dataset_contract, row_identity, run_data_audit
from ruflex.api.main import app


def _fixture() -> pd.DataFrame:
    return pd.DataFrame({"entity_id": ["a", "b", "b"], "temperature": [10.0, None, None], "mode": ["normal", "normal", "normal"], "target": [0, 1, 1]})


def test_profile_surfaces_id_duplicates_missing_constant_and_deterministic_audit() -> None:
    profile = inspect_dataset(_fixture(), source_artifact_sha256="a" * 64)
    assert "entity_id" in profile.id_candidates
    entity = next(column for column in profile.columns if column.name == "entity_id")
    assert entity.proposed_role == "id_candidate"
    assert "Explicit identifier token" in entity.role_reason
    contract = build_dataset_contract(profile, target="target", task="binary_classification", id_columns=["entity_id"])
    first, second = run_data_audit(contract, _fixture()), run_data_audit(contract, _fixture())
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert {finding.code for finding in first.findings} >= {"DUPLICATE_ROWS", "MISSING_VALUES", "CONSTANT_COLUMN"}
    assert "entity_id" not in contract.feature_columns
    assert contract.role_decisions == {"entity_id": "id", "temperature": "feature", "mode": "feature", "target": "target"}


def test_id_candidate_is_excluded_only_when_user_confirms_id_role() -> None:
    profile = inspect_dataset(_fixture(), source_artifact_sha256="f" * 64)
    kept_as_feature = build_dataset_contract(profile, target="target", task="binary_classification", id_columns=[])
    confirmed_as_id = build_dataset_contract(profile, target="target", task="binary_classification", id_columns=["entity_id"])

    assert "entity_id" in kept_as_feature.feature_columns
    assert kept_as_feature.role_decisions["entity_id"] == "feature"
    assert "entity_id" not in confirmed_as_id.feature_columns
    assert confirmed_as_id.role_decisions["entity_id"] == "id"


@pytest.mark.parametrize(
    ("id_columns", "message"),
    [
        (["missing_id"], "absent from the dataset"),
        (["target"], "cannot also be declared as an ID"),
        (["entity_id", "entity_id"], "must be unique"),
    ],
)
def test_invalid_id_role_declarations_fail_at_contract_confirmation(id_columns: list[str], message: str) -> None:
    profile = inspect_dataset(_fixture(), source_artifact_sha256="0" * 64)
    with pytest.raises(DatasetConfirmationError, match=message):
        build_dataset_contract(profile, target="target", task="binary_classification", id_columns=id_columns)


def test_id_candidate_heuristic_requires_explicit_id_token() -> None:
    frame = pd.DataFrame({
        "id": [1, 2], "row_id": [11, 12], "customer_id": [21, 22],
        "job_housemaid": [0, 1], "valid": [1.0, 2.0], "paid": [3.0, 4.0], "target": [0, 1],
    })
    profile = inspect_dataset(frame, source_artifact_sha256="d" * 64)
    assert set(profile.id_candidates) == {"id", "row_id", "customer_id"}
    assert next(column for column in profile.columns if column.name == "job_housemaid").proposed_role == "feature"
    assert all(next(column for column in profile.columns if column.name == name).semantic_type != "id" for name in ("job_housemaid", "valid", "paid"))


def test_bank_marketing_frozen_contract_keeps_job_housemaid() -> None:
    root = Path(__file__).resolve().parents[1]
    specification = json.loads((root / "research/a01_stability_aware_review/config/dataset_specs.json").read_text(encoding="utf-8"))
    bank = next(item for item in specification["datasets"] if item["canonical_dataset_id"] == "uci_bank_marketing")
    frame = pd.DataFrame({column: [0.0, 1.0] for column in bank["feature_columns"]} | {"source_row_id": [0, 1], "y": [0, 1]})
    profile = inspect_dataset(frame, source_artifact_sha256="e" * 64)
    contract = build_dataset_contract(profile, target="y", task="binary_classification", id_columns=["source_row_id"])
    assert len(contract.feature_columns) == 62
    assert "job_housemaid" in contract.feature_columns


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


def test_row_identity_is_deterministic_and_bound_to_dataset_revision() -> None:
    first = row_identity("a" * 64, 7)
    assert first == row_identity("a" * 64, 7)
    assert first != row_identity("b" * 64, 7)
    assert first != row_identity("a" * 64, 8)
    assert first.startswith("row:")


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


def test_xlsx_file_inspection_is_read_only_until_explicit_import(tmp_path) -> None:
    workbook = BytesIO()
    pd.DataFrame({"temperature": [10, 20], "target": [0, 1]}).to_excel(workbook, index=False)
    raw = workbook.getvalue()
    root = tmp_path / "inspect-only-project"
    client = TestClient(app)
    created = client.post("/api/projects", json={"path": str(root), "name": "inspect-only"})
    session_id = created.json()["session_id"]

    inspected = client.post(
        "/api/projects/dataset/import/inspect",
        json={"session_id": session_id, "filename": "measurements.xlsx", "content_base64": base64.b64encode(raw).decode()},
    )

    assert inspected.status_code == 200, inspected.text
    profile = inspected.json()["profile"]
    assert profile["row_count"] == 2
    assert [column["name"] for column in profile["columns"]] == ["temperature", "target"]
    assert profile["source_artifact_sha256"] == hashlib.sha256(raw).hexdigest()
    assert not (root / "data" / "dataset-contract.json").exists()
    assert client.get(f"/api/projects/{session_id}/artifacts").json() == []
    assert client.get(f"/api/projects/{session_id}/dataset").status_code == 404

    malformed = client.post(
        "/api/projects/dataset/import/inspect",
        json={"session_id": session_id, "filename": "broken.xlsx", "content_base64": base64.b64encode(b"not a workbook").decode()},
    )
    assert malformed.status_code == 422
    assert "mismatch" in malformed.json()["detail"]
    assert not (root / "data" / "dataset-contract.json").exists()


def test_csv_file_inspection_is_read_only(tmp_path) -> None:
    raw = b"temperature,target\n10,0\n20,1\n"
    root = tmp_path / "csv-inspection-project"
    client = TestClient(app)
    created = client.post("/api/projects", json={"path": str(root), "name": "csv-inspection"})
    session_id = created.json()["session_id"]

    inspected = client.post(
        "/api/projects/dataset/import/inspect",
        json={"session_id": session_id, "filename": "measurements.csv", "content_base64": base64.b64encode(raw).decode()},
    )

    assert inspected.status_code == 200, inspected.text
    assert inspected.json()["profile"]["row_count"] == 2
    assert [column["name"] for column in inspected.json()["profile"]["columns"]] == ["temperature", "target"]
    assert client.get(f"/api/projects/{session_id}/artifacts").json() == []
    assert client.get(f"/api/projects/{session_id}/dataset").status_code == 404


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


def test_invalid_replacement_target_preserves_confirmed_dataset_and_artifact_set(tmp_path) -> None:
    client = TestClient(app)
    root = tmp_path / "replacement-project"
    created = client.post("/api/projects", json={"path": str(root), "name": "replacement"})
    session_id = created.json()["session_id"]
    initial = client.post(
        "/api/projects/dataset/confirm",
        json={"session_id": session_id, "csv_text": "temperature,target\n10,0\n20,1\n", "target": "target", "task": "binary_classification", "id_columns": []},
    )
    assert initial.status_code == 200, initial.text
    before_contract = initial.json()["contract"]
    before_artifacts = client.get(f"/api/projects/{session_id}/artifacts").json()

    replacement = BytesIO()
    pd.DataFrame({"temperature": [99, 100], "other_target": [0, 1]}).to_excel(replacement, index=False)
    rejected = client.post(
        "/api/projects/dataset/import",
        json={
            "session_id": session_id,
            "filename": "replacement.xlsx",
            "content_base64": base64.b64encode(replacement.getvalue()).decode(),
            "target": "missing_target",
            "task": "binary_classification",
            "id_columns": [],
        },
    )

    assert rejected.status_code == 422
    assert "Target column is absent" in rejected.json()["detail"]
    assert client.get(f"/api/projects/{session_id}/artifacts").json() == before_artifacts
    assert client.get(f"/api/projects/{session_id}/dataset").json()["contract"] == before_contract
