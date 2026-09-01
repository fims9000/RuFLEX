from __future__ import annotations

from pathlib import Path
import zipfile

import pandas as pd
from fastapi.testclient import TestClient

from ruflex.api.main import app


def _frame() -> pd.DataFrame:
    return pd.DataFrame([
        {"temperature": 20 + index * .8, "torque": 10 + (index * 7) % 50, "target": int(20 + index * .8 + 10 + (index * 7) % 50 > 58)}
        for index in range(72)
    ])


def _project(tmp_path: Path) -> tuple[TestClient, str]:
    client = TestClient(app)
    root = tmp_path / "stability"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Stability"}).json()["session_id"]
    response = client.post("/api/projects/dataset/confirm", json={"session_id": session_id, "csv_text": _frame().to_csv(index=False), "target": "target", "task": "binary_classification", "id_columns": []})
    assert response.status_code == 200, response.text
    return client, session_id


def test_training_variability_keeps_split_identity_and_persists_stability_gate(tmp_path: Path) -> None:
    client, session_id = _project(tmp_path)
    response = client.post("/api/projects/training/studies", json={"session_id": session_id, "name": "fixed split", "model_kind": "random_forest", "seeds": [11, 13, 17], "randomness_protocol": "TRAINING_VARIABILITY", "split_seed": 42, "selection_metric": "f1", "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert response.status_code == 201, response.text
    study = response.json()
    assert study["randomness_protocol"] == "TRAINING_VARIABILITY"
    assert {run["split_seed"] for run in study["seed_runs"]} == {42}
    assert len({run["training_seed"] for run in study["seed_runs"]}) == 3
    assert len({run["split"]["split_identity"] for run in study["seed_runs"]}) == 1
    analysis_response = client.post("/api/projects/analyses/stability", json={"session_id": session_id, "study_id": study["study_id"], "high_confidence_threshold": .9, "unstable_agreement_threshold": .8})
    assert analysis_response.status_code == 201, analysis_response.text
    analysis = analysis_response.json()
    assert analysis["case_count"] > 0
    assert analysis["split_seed"] == 42
    selected = study["selected_run_id"]
    evaluation_response = client.post("/api/projects/analyses/evaluations", json={"session_id": session_id, "run_id": selected})
    assert evaluation_response.status_code == 201, evaluation_response.text
    policy_response = client.post("/api/projects/analyses/stability-policies", json={"session_id": session_id, "analysis_id": analysis["analysis_id"], "evaluation_id": evaluation_response.json()["evaluation_id"], "min_confidence": .9, "min_class_agreement": .8, "max_probability_std": .15})
    assert policy_response.status_code == 201, policy_response.text
    policy = policy_response.json()
    assert policy["source_split"] == "validation"
    assert {item["policy"] for item in policy["risk_coverage"]} == {"NO_REVIEW", "RANDOM_REVIEW", "CONFIDENCE_ONLY", "STABILITY_AWARE"}
    applied = client.post("/api/projects/analyses/stability-policies/apply", json={"session_id": session_id, "policy_id": policy["policy_id"], "sample": {"temperature": 55.0, "torque": 25.0}})
    assert applied.status_code == 200, applied.text
    assert applied.json()["disposition"] in {"ACCEPT", "REVIEW", "BLOCK"}
    assert len(applied.json()["run_probabilities"]) == 3
    assurance = client.post("/api/projects/evidence/assurance-cases", json={"session_id": session_id})
    assert assurance.status_code == 201, assurance.text
    gates = {gate["key"]: gate for gate in assurance.json()["gates"]}
    assert gates["prediction_stability"]["status"] == "PASS"
    assert gates["stability_gate_policy"]["status"] == "PASS"
    bundle = client.post("/api/projects/evidence/verification-bundles", json={"session_id": session_id})
    assert bundle.status_code == 201, bundle.text
    with zipfile.ZipFile(bundle.json()["path"]) as archive:
        names = archive.namelist()
    assert any(name.startswith("analyses/stability-analyses/") for name in names)
    assert any(name.startswith("analyses/stability-policies/") for name in names)
    reopened = client.post("/api/projects/open", json={"path": str(tmp_path / "stability")})
    listed = client.get(f"/api/projects/{reopened.json()['session_id']}/analyses/stability")
    assert listed.status_code == 200 and listed.json()[0]["analysis_id"] == analysis["analysis_id"]


def test_stability_analysis_rejects_split_variability(tmp_path: Path) -> None:
    client, session_id = _project(tmp_path)
    response = client.post("/api/projects/training/studies", json={"session_id": session_id, "name": "variable split", "model_kind": "random_forest", "seeds": [11, 13, 17], "randomness_protocol": "SPLIT_VARIABILITY", "training_seed": 5, "selection_metric": "f1", "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert response.status_code == 201, response.text
    invalid = client.post("/api/projects/analyses/stability", json={"session_id": session_id, "study_id": response.json()["study_id"]})
    assert invalid.status_code == 422


def test_stability_gate_refuses_final_test_tuning(tmp_path: Path) -> None:
    client, session_id = _project(tmp_path)
    readonly = client.post("/api/projects/open", json={"path": str(tmp_path / "stability"), "read_only": True})
    response = client.post("/api/projects/analyses/stability", json={"session_id": readonly.json()["session_id"], "study_id": "00000000-0000-0000-0000-000000000000"})
    assert response.status_code == 403
