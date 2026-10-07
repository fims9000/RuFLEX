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


def test_ordinary_column_can_be_excluded_without_mislabeling_it_as_id() -> None:
    from ruflex.application.verification_bundle import _validate_relationships
    frame = pd.DataFrame({"entity_id": ["a", "b"], "temperature": [10, 20], "leak_hint": [0, 1], "target": [0, 1]})
    profile = inspect_dataset(frame, source_artifact_sha256="9" * 64)
    contract = build_dataset_contract(
        profile, target="target", task="binary_classification",
        id_columns=["entity_id"], excluded_columns=["leak_hint"],
    )
    assert contract.feature_columns == ["temperature"]
    assert contract.id_columns == ["entity_id"]
    assert contract.excluded_columns == ["leak_hint"]
    assert contract.role_decisions["leak_hint"] == "excluded"
    assert contract.compare_schema(frame).compatible
    assert not contract.compare_schema(frame.drop(columns="leak_hint")).compatible
    assert _validate_relationships([profile, contract]) == []
    altered = contract.model_copy(update={"excluded_columns": [], "feature_columns": ["temperature"]})
    assert any("feature roles" in message for message in _validate_relationships([profile, altered]))


@pytest.mark.parametrize(
    ("excluded_columns", "message"),
    [
        (["missing"], "absent from the dataset"),
        (["target"], "cannot also be excluded"),
        (["entity_id"], "must not overlap"),
        (["mode", "mode"], "must be unique"),
        (["temperature", "mode"], "At least one model feature"),
    ],
)
def test_invalid_feature_exclusions_fail_before_contract_persistence(excluded_columns: list[str], message: str) -> None:
    profile = inspect_dataset(_fixture(), source_artifact_sha256="8" * 64)
    with pytest.raises(DatasetConfirmationError, match=message):
        build_dataset_contract(profile, target="target", task="binary_classification", id_columns=["entity_id"], excluded_columns=excluded_columns)


def test_legacy_dataset_contract_without_exclusions_deserializes() -> None:
    profile = inspect_dataset(_fixture(), source_artifact_sha256="7" * 64)
    contract = build_dataset_contract(profile, target="target", task="binary_classification", id_columns=["entity_id"])
    historical = contract.model_dump(mode="json", exclude={"excluded_columns"})
    restored = type(contract).model_validate(historical)
    assert restored.excluded_columns == []
    assert restored.feature_columns == contract.feature_columns


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


def test_invalid_id_role_declarations_are_rejected_before_dataset_persistence(tmp_path) -> None:
    client = TestClient(app)
    for index, id_columns in enumerate((["missing_id"], ["target"], ["entity_id", "entity_id"])):
        root = tmp_path / f"invalid-id-contract-{index}"
        created = client.post("/api/projects", json={"path": str(root), "name": f"invalid-id-{index}"})
        session_id = created.json()["session_id"]
        response = client.post(
            "/api/projects/dataset/confirm",
            json={
                "session_id": session_id,
                "csv_text": "entity_id,temperature,target\na,10,0\nb,20,1\n",
                "target": "target",
                "task": "binary_classification",
                "id_columns": id_columns,
            },
        )

        assert response.status_code == 422
        assert "Dataset confirmation failed" in response.json()["detail"]
        assert client.get(f"/api/projects/{session_id}/dataset").status_code == 404
        assert client.get(f"/api/projects/{session_id}/artifacts").json() == []


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


def test_excluded_feature_is_persisted_reopened_and_omitted_from_training(tmp_path) -> None:
    client = TestClient(app)
    root = tmp_path / "excluded-feature-project"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Excluded feature"}).json()["session_id"]
    rows = [f"{index},{index % 7},{index % 2},{index % 2}" for index in range(40)]
    csv_text = "entity_id,temperature,leak_hint,target\n" + "\n".join(rows) + "\n"
    confirmed = client.post("/api/projects/dataset/confirm", json={
        "session_id": session_id, "csv_text": csv_text, "target": "target",
        "task": "binary_classification", "id_columns": ["entity_id"], "excluded_columns": ["leak_hint"],
    })
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["contract"]["feature_columns"] == ["temperature"]
    assert client.get(f"/api/projects/{session_id}/integrity").json()["status"] == "PASS"
    trained = client.post("/api/projects/training/run", json={
        "session_id": session_id, "model_kind": "logistic_regression", "seed": 42,
        "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1,
        "validation_fraction": .2, "test_fraction": .2, "max_rules": 3,
    })
    assert trained.status_code == 201, trained.text
    assert trained.json()["feature_columns"] == ["temperature"]
    assert client.post("/api/projects/close", json={"session_id": session_id}).status_code == 204
    reopened = client.post("/api/projects/open", json={"path": str(root), "read_only": True})
    assert reopened.status_code == 200, reopened.text
    reopened_id = reopened.json()["session_id"]
    state = client.get(f"/api/projects/{reopened_id}/dataset").json()
    assert state["contract"]["excluded_columns"] == ["leak_hint"]
    assert state["contract"]["feature_columns"] == ["temperature"]
    assert client.get(f"/api/projects/{reopened_id}/integrity").json()["status"] == "PASS"


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
