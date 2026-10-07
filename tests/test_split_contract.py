from __future__ import annotations

import json

import pandas as pd
import pytest
import zipfile
from fastapi.testclient import TestClient

from ruflex.api.main import app
from ruflex.application.datasets import (
    DatasetConfirmationError,
    build_dataset_contract,
    create_transform_pipeline_contract,
    create_split_contract,
    inspect_dataset,
    load_split_contract,
    list_split_contracts,
    list_transform_pipeline_contracts,
    list_leakage_audits,
    persist_dataset_bytes,
    persist_dataset_contract,
    run_leakage_audit,
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


def test_temporal_and_site_contracts_materialize_exact_nonrandom_roles(tmp_path) -> None:
    frame = _frame().assign(event_time=list(range(45)), site=[f"s{index // 9}" for index in range(45)])
    artifact = persist_dataset_bytes(tmp_path, frame.to_csv(index=False).encode(), original_name="governed.csv")
    profile = inspect_dataset(frame, source_artifact_sha256=artifact.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification", id_columns=["patient_id"])
    persist_dataset_contract(tmp_path, contract, report=run_data_audit(contract, frame), profile=profile)
    temporal = create_split_contract(tmp_path, family="TEMPORAL", time_column="event_time", split_seed=19)
    assert max(temporal.role_source_rows["train"]) < min(temporal.role_source_rows["validation"])
    assert max(temporal.role_source_rows["validation"]) < min(temporal.role_source_rows["test"])
    site = create_split_contract(tmp_path, family="SITE_HOLDOUT", site_column="site", split_seed=19)
    role_sites = {role: set(frame.loc[rows, "site"]) for role, rows in site.role_source_rows.items()}
    assert not (role_sites["train"] & role_sites["validation"])
    assert not (role_sites["train"] & role_sites["test"])


def test_temporal_split_rejects_shared_boundary_timestamp(tmp_path) -> None:
    frame = _frame().assign(event_time=[index // 2 for index in range(45)])
    artifact = persist_dataset_bytes(tmp_path, frame.to_csv(index=False).encode(), original_name="boundary-times.csv")
    profile = inspect_dataset(frame, source_artifact_sha256=artifact.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification", id_columns=["patient_id"])
    persist_dataset_contract(tmp_path, contract, report=run_data_audit(contract, frame), profile=profile)

    with pytest.raises(DatasetConfirmationError, match="strict forward role boundaries"):
        create_split_contract(tmp_path, family="TEMPORAL", time_column="event_time", split_seed=19)


def test_leakage_audit_records_target_derived_feature_signal(tmp_path) -> None:
    frame = pd.DataFrame({
        "x": [0.0, 1.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
        "target_copy": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        "target": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
    })
    artifact = persist_dataset_bytes(tmp_path, frame.to_csv(index=False).encode(), original_name="audit.csv")
    profile = inspect_dataset(frame, source_artifact_sha256=artifact.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification")
    persist_dataset_contract(tmp_path, contract, report=run_data_audit(contract, frame), profile=profile)
    split_contract = create_split_contract(tmp_path, family="RANDOM", split_seed=19)
    split = TabularDataset.from_dataframe(frame).split(DatasetConfig(
        target_column="target", feature_columns=tuple(contract.feature_columns), explicit_split_source_rows=split_contract.role_source_rows,
    ))
    pipeline = create_transform_pipeline_contract(tmp_path, contract=contract, split=split, preprocessing_artifact_sha256="a" * 64, split_contract_id=str(split_contract.split_id))
    audit = run_leakage_audit(tmp_path, split_contract_id=str(split_contract.split_id), transform_pipeline_id=str(pipeline.pipeline_id))

    assert audit.status == "WARN"
    assert {finding.code for finding in audit.findings} >= {"TARGET_DERIVED_FEATURE"}


def test_leakage_audit_records_conflicting_duplicate_feature_vectors(tmp_path) -> None:
    frame = pd.DataFrame({
        "x": [0.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
        "z": [3.0, 3.0, 2.0, 1.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0],
        "target": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
    })
    artifact = persist_dataset_bytes(tmp_path, frame.to_csv(index=False).encode(), original_name="duplicates.csv")
    profile = inspect_dataset(frame, source_artifact_sha256=artifact.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification")
    persist_dataset_contract(tmp_path, contract, report=run_data_audit(contract, frame), profile=profile)
    split_contract = create_split_contract(tmp_path, family="RANDOM", split_seed=19)
    split = TabularDataset.from_dataframe(frame).split(DatasetConfig(
        target_column="target", feature_columns=tuple(contract.feature_columns), explicit_split_source_rows=split_contract.role_source_rows,
    ))
    pipeline = create_transform_pipeline_contract(tmp_path, contract=contract, split=split, preprocessing_artifact_sha256="b" * 64, split_contract_id=str(split_contract.split_id))
    audit = run_leakage_audit(tmp_path, split_contract_id=str(split_contract.split_id), transform_pipeline_id=str(pipeline.pipeline_id))

    assert audit.status == "WARN"
    assert "NEAR_DUPLICATE_ROWS" in {finding.code for finding in audit.findings}


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
    leakage_audit_id = latest.json()["leakage_audit_id"]
    leakage_audit = client.get(f"/api/projects/{reopened['session_id']}/dataset/leakage-audits/{leakage_audit_id}")
    assert leakage_audit.status_code == 200
    assert leakage_audit.json()["status"] in {"PASS", "WARN"}
    assert leakage_audit.json()["rigor_profile"] == "CONFIRMATORY"
    lineage = build_project_lineage(root)
    assert any(node.kind == "split_contract" for node in lineage.nodes)
    audit_node = next(node for node in lineage.nodes if node.kind == "leakage_audit" and node.object_id == leakage_audit_id)
    assert any(edge.target == audit_node.id and edge.relation == "audited" for edge in lineage.edges)
    assert any(node.kind == "transform_pipeline" and node.object_id == pipeline_id for node in lineage.nodes)
    assert inspect_project_integrity(root).status == "PASS"
    audit_path = root / "data" / "leakage-audits" / f"{leakage_audit_id}.json"
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
    original_status = audit_payload["status"]
    audit_payload["status"] = "WARN" if original_status != "WARN" else "PASS"
    audit_path.write_text(json.dumps(audit_payload), encoding="utf-8")
    integrity_after_status_tamper = inspect_project_integrity(root)
    assert any(issue.code == "LEAKAGE_AUDIT_EVIDENCE_MALFORMED" for issue in integrity_after_status_tamper.issues)
    audit_payload["status"] = original_status
    audit_path.write_text(json.dumps(audit_payload), encoding="utf-8")
    from ruflex.application.datasets import TransformPipelineContract, _transform_pipeline_identity

    pipeline_path = root / "data" / "transforms" / f"{pipeline_id}.json"
    pipeline_payload = json.loads(pipeline_path.read_text(encoding="utf-8"))
    original_pipeline = dict(pipeline_payload)
    pipeline_payload["preprocessing_artifact_sha256"] = "f" * 64
    pipeline_model = TransformPipelineContract.model_validate(pipeline_payload)
    pipeline_payload["pipeline_identity"] = _transform_pipeline_identity(pipeline_model)
    pipeline_path.write_text(json.dumps(pipeline_payload), encoding="utf-8")
    invalid_pipeline_artifact = inspect_project_integrity(root)
    assert any(issue.code == "TRANSFORM_PIPELINE_EVIDENCE_MALFORMED" for issue in invalid_pipeline_artifact.issues)
    pipeline_path.write_text(json.dumps(original_pipeline), encoding="utf-8")
    assurance = client.post("/api/projects/evidence/assurance-cases", json={"session_id": reopened["session_id"]})
    assert assurance.status_code == 201, assurance.text
    gates = {gate["key"]: gate["status"] for gate in assurance.json()["gates"]}
    assert gates["transform_pipeline"] == "PASS"
    assert gates["data_leakage_audit"] == "PASS"
    bundle = client.post("/api/projects/evidence/verification-bundles", json={"session_id": reopened["session_id"]})
    assert bundle.status_code == 201, bundle.text
    with zipfile.ZipFile(bundle.json()["path"]) as archive:
        names = set(archive.namelist())
        assert f"data/splits/{split_id}.json" in names
        assert f"data/transforms/{pipeline_id}.json" in names
        assert f"data/leakage-audits/{leakage_audit_id}.json" in names

    from ruflex.application.verification_bundle import validate_verification_bundle
    assert validate_verification_bundle(bundle.json()["path"]).status == "PASS"


@pytest.mark.parametrize("field", ["split_contract_id", "transform_pipeline_id"])
def test_assurance_fails_closed_for_dangling_leakage_audit_links(tmp_path, field: str) -> None:
    import json

    client = TestClient(app)
    root = tmp_path / f"assurance-broken-audit-{field}"
    created = client.post("/api/projects", json={"path": str(root), "name": "audit links"}).json()
    session_id = created["session_id"]
    rows = ["patient_id,x,target"] + [f"p{group},{group * 3 + repeat},{group % 2}" for group in range(12) for repeat in range(3)]
    confirmed = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": "\n".join(rows), "target": "target", "task": "binary_classification", "id_columns": ["patient_id"]})
    assert confirmed.status_code == 200, confirmed.text
    split = client.post("/api/projects/dataset/splits", json={"session_id": session_id, "family": "GROUP", "group_column": "patient_id", "split_seed": 7, "validation_fraction": .2, "test_fraction": .2})
    assert split.status_code == 201, split.text
    trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": 7, "split_contract_id": split.json()["split_id"], "max_epochs": 1, "learning_rate": .01, "batch_size": 8, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert trained.status_code == 201, trained.text

    audit_path = root / "data" / "leakage-audits" / f"{trained.json()['leakage_audit_id']}.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit[field] = "00000000-0000-0000-0000-000000000001"
    audit_path.write_text(json.dumps(audit), encoding="utf-8")

    assurance = client.post("/api/projects/evidence/assurance-cases", json={"session_id": session_id})
    assert assurance.status_code == 201, assurance.text
    gates = {gate["key"]: gate["status"] for gate in assurance.json()["gates"]}
    assert gates["data_leakage_audit"] == "FAIL"


def test_assurance_and_bundle_reject_existing_but_mismatched_audit_split_transform_pair(tmp_path) -> None:
    import json
    from ruflex.application.verification_bundle import validate_verification_bundle

    client = TestClient(app)
    root = tmp_path / "assurance-mismatched-audit"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "mismatched audit"}).json()["session_id"]
    rows = ["patient_id,x,target"] + [f"p{group},{group * 3 + repeat},{group % 2}" for group in range(12) for repeat in range(3)]
    confirmed = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": "\n".join(rows), "target": "target", "task": "binary_classification", "id_columns": ["patient_id"]})
    assert confirmed.status_code == 200, confirmed.text
    split_ids = []
    run_ids = []
    for seed in (7, 19):
        split = client.post("/api/projects/dataset/splits", json={"session_id": session_id, "family": "GROUP", "group_column": "patient_id", "split_seed": seed, "validation_fraction": .2, "test_fraction": .2})
        assert split.status_code == 201, split.text
        split_ids.append(split.json()["split_id"])
        trained = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "logistic_regression", "seed": seed, "split_contract_id": split_ids[-1], "max_epochs": 1, "learning_rate": .01, "batch_size": 8, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
        assert trained.status_code == 201, trained.text
        run_ids.append(trained.json())

    audit_path = root / "data" / "leakage-audits" / f"{run_ids[0]['leakage_audit_id']}.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit["split_contract_id"] = split_ids[1]
    audit_path.write_text(json.dumps(audit), encoding="utf-8")

    assurance = client.post("/api/projects/evidence/assurance-cases", json={"session_id": session_id})
    assert assurance.status_code == 201, assurance.text
    gates = {gate["key"]: gate["status"] for gate in assurance.json()["gates"]}
    assert gates["data_leakage_audit"] == "FAIL"
    bundle = client.post("/api/projects/evidence/verification-bundles", json={"session_id": session_id})
    assert bundle.status_code == 201, bundle.text
    validation = validate_verification_bundle(bundle.json()["path"])
    assert validation.status == "FAIL"
    assert any("mismatched split/transform provenance" in error for error in validation.errors)


@pytest.mark.parametrize(("relative_path", "list_function"), [
    ("data/splits/broken.json", list_split_contracts),
    ("data/transforms/broken.json", list_transform_pipeline_contracts),
    ("data/leakage-audits/broken.json", list_leakage_audits),
])
def test_malformed_persisted_data_governance_evidence_is_not_silently_omitted(tmp_path, relative_path, list_function) -> None:
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True)
    path.write_text("{ not valid JSON", encoding="utf-8")

    with pytest.raises(DatasetConfirmationError, match="malformed or incompatible"):
        list_function(tmp_path)
