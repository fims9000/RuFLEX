from __future__ import annotations

import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from ruflex.api.main import app
from ruflex.application.datasets import (
    build_dataset_contract,
    inspect_dataset,
    load_dataset_frame,
    load_dataset_profile,
    persist_dataset_bytes,
    persist_dataset_contract,
    run_data_audit,
)
from ruflex.application.fis import FISError, create_default_fis, evaluate_fis, load_fis, persist_fis, semantic_hash
from ruflex.domain.fis import FISSpec


CSV = "temperature,torque,target\n10,20,0\n20,50,1\n30,80,1\n"


def _confirmed_project(tmp_path):
    root = tmp_path / "project"
    (root / "data").mkdir(parents=True)
    (root / "models").mkdir()
    (root / "artifacts").mkdir()
    raw = CSV.encode()
    ref = persist_dataset_bytes(root, raw)
    frame = pd.read_csv(__import__("io").StringIO(CSV))
    profile = inspect_dataset(frame, source_artifact_sha256=ref.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification")
    persist_dataset_contract(root, contract, run_data_audit(contract, frame), profile)
    return root


def test_confirmed_dataset_bytes_are_reopenable_from_artifact_store(tmp_path) -> None:
    root = _confirmed_project(tmp_path)
    frame = load_dataset_frame(root)
    profile = load_dataset_profile(root)
    assert list(frame.columns) == ["temperature", "torque", "target"]
    assert len(frame) == 3
    assert profile.row_count == 3
    assert (root / "objects" / "artifacts").is_dir()


def test_default_mamdani_fis_is_persisted_and_deterministic(tmp_path) -> None:
    root = _confirmed_project(tmp_path)
    spec = create_default_fis(root, input_columns=["temperature", "torque"])
    restored = load_fis(root)
    assert restored.fis_id == spec.fis_id
    assert restored.semantic_hash == semantic_hash(restored)
    inputs = {"temperature": 25.0, "torque": 65.0}
    first = evaluate_fis(restored, inputs)
    second = evaluate_fis(restored, inputs)
    assert first.output == pytest.approx(second.output, abs=1e-12)
    assert 0.0 <= first.output <= 1.0
    assert first.trace.reconstruction_error <= 1e-12
    assert len(first.trace.memberships) == 2
    assert len(first.trace.rules) == 3


def test_fis_rejects_out_of_range_input_and_tampered_semantic_hash(tmp_path) -> None:
    root = _confirmed_project(tmp_path)
    spec = create_default_fis(root, input_columns=["temperature"])
    with pytest.raises(FISError, match="outside the declared range"):
        evaluate_fis(spec, {"temperature": 9999})

    path = root / "models" / "fis" / f"{spec.fis_id}.json"
    payload = json.loads(path.read_text())
    payload["name"] = "tampered"
    path.write_text(json.dumps(payload))
    with pytest.raises(FISError, match="semantic hash mismatch"):
        load_fis(root)


def test_saved_fis_exposes_canonical_json_and_yaml_for_python_escape_hatch(tmp_path) -> None:
    client = TestClient(app)
    root = tmp_path / "canonical-fis"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Canonical FIS"}).json()["session_id"]
    csv_text = "x,target\n0,0\n1,1\n2,1\n3,1\n"
    assert client.post(
        "/api/projects/dataset/confirm",
        json={"session_id": session_id, "csv_text": csv_text, "target": "target", "task": "binary_classification", "id_columns": []},
    ).status_code == 200
    created = client.post("/api/projects/fis/default", json={"session_id": session_id, "name": "Inspectable", "input_columns": ["x"]})
    assert created.status_code == 201, created.text

    canonical_json = client.get(f"/api/projects/{session_id}/fis/canonical.json")
    canonical_yaml = client.get(f"/api/projects/{session_id}/fis/canonical.yaml")
    assert canonical_json.status_code == 200, canonical_json.text
    assert canonical_yaml.status_code == 200, canonical_yaml.text
    assert '"fis_id"' in canonical_json.text
    assert created.json()["semantic_hash"] in canonical_json.text
    assert "fis_id:" in canonical_yaml.text
    assert created.json()["semantic_hash"] in canonical_yaml.text


def test_fis_rule_reference_validation_fails_before_inference(tmp_path) -> None:
    root = _confirmed_project(tmp_path)
    spec = create_default_fis(root, input_columns=["temperature"])
    payload = spec.model_dump(mode="json")
    payload["rules"][0]["clauses"][0]["term"] = "UNKNOWN"
    with pytest.raises(ValueError, match="unknown term"):
        FISSpec.model_validate(payload)


def test_api_golden_slice_persists_dataset_builds_fis_and_emits_trace(tmp_path) -> None:
    from fastapi.testclient import TestClient
    from ruflex.api.main import app

    client = TestClient(app)
    root = tmp_path / "api-project"
    created = client.post("/api/projects", json={"path": str(root), "name": "Product route"})
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    confirmed = client.post(
        "/api/projects/dataset/confirm",
        json={
            "session_id": session_id,
            "csv_text": CSV,
            "target": "target",
            "task": "binary_classification",
            "id_columns": [],
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    assert (root / "artifacts" / "sha256").is_dir()

    dataset = client.get(f"/api/projects/{session_id}/dataset")
    assert dataset.status_code == 200, dataset.text
    assert dataset.json()["preview"][1]["torque"] == 50
    range_response = client.get(
        f"/api/projects/{session_id}/dataset/features/temperature/range"
    )
    assert range_response.status_code == 200, range_response.text
    assert range_response.json() == {"minimum": 10.0, "maximum": 30.0}
    assert client.get(
        f"/api/projects/{session_id}/dataset/features/target/range"
    ).status_code == 422

    created_fis = client.post("/api/projects/fis/default", json={"session_id": session_id, "name": "Machine risk"})
    assert created_fis.status_code == 201, created_fis.text
    spec = created_fis.json()
    assert [item["name"] for item in spec["inputs"]] == ["temperature", "torque"]

    midpoint_inputs = {
        variable["name"]: (variable["minimum"] + variable["maximum"]) / 2.0
        for variable in spec["inputs"]
    }
    evaluation = client.post(
        "/api/projects/fis/evaluate",
        json={"session_id": session_id, "inputs": midpoint_inputs, "persist_trace": True},
    )
    assert evaluation.status_code == 200, evaluation.text
    payload = evaluation.json()
    assert payload["evaluation"]["trace"]["reconstruction_error"] <= 1e-12
    assert payload["trace_artifact_sha256"]

    client.post("/api/projects/close", json={"session_id": session_id})
    reopened = client.post("/api/projects/open", json={"path": str(root), "read_only": False})
    assert reopened.status_code == 200
    new_session = reopened.json()["session_id"]
    restored_dataset = client.get(f"/api/projects/{new_session}/dataset")
    restored_fis = client.get(f"/api/projects/{new_session}/fis/active")
    restored_trace = client.get(f"/api/projects/{new_session}/fis/trace/latest")
    assert restored_dataset.status_code == 200
    assert restored_fis.status_code == 200
    assert restored_trace.status_code == 200
    assert restored_fis.json()["fis_id"] == spec["fis_id"]
    assert restored_trace.json()["trace"]["fis_id"] == spec["fis_id"]
