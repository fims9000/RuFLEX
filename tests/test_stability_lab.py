from __future__ import annotations

from pathlib import Path
import zipfile
from uuid import uuid4

import pandas as pd
from fastapi.testclient import TestClient

from ruflex.api.main import app
from ruflex.application.stability import evaluate_frozen_stability_probabilities
from ruflex.domain.stability import StabilityGatePolicy


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
    selected = study["selected_run_id"]
    evaluation_response = client.post("/api/projects/analyses/evaluations", json={"session_id": session_id, "run_id": selected})
    assert evaluation_response.status_code == 201, evaluation_response.text
    threshold = client.post("/api/projects/analyses/thresholds", json={"session_id": session_id, "evaluation_id": evaluation_response.json()["evaluation_id"]})
    assert threshold.status_code == 201, threshold.text
    analysis_response = client.post("/api/projects/analyses/stability", json={"session_id": session_id, "study_id": study["study_id"], "evaluation_id": evaluation_response.json()["evaluation_id"], "threshold_id": threshold.json()["threshold_id"], "high_confidence_threshold": .9, "unstable_agreement_threshold": .8})
    assert analysis_response.status_code == 201, analysis_response.text
    analysis = analysis_response.json()
    assert analysis["applicability"] == "APPLICABLE"
    assert analysis["validation_alignment_status"] == "EXACT_MATCH"
    assert analysis["case_count"] > 0
    assert analysis["split_seed"] == 42
    assert analysis["probability_source"] == "raw"
    assert all(case["run_support_count"] == 3 for case in analysis["cases"])
    assert all(case["row_identity"] for case in analysis["cases"])
    assert len({case["row_identity"] for case in analysis["cases"]}) == analysis["case_count"]
    policy_response = client.post("/api/projects/analyses/stability-policies", json={"session_id": session_id, "analysis_id": analysis["analysis_id"], "evaluation_id": evaluation_response.json()["evaluation_id"], "min_confidence": .9, "min_class_agreement": .8, "max_probability_std": .15})
    assert policy_response.status_code == 201, policy_response.text
    policy = policy_response.json()
    assert policy["source_split"] == "validation"
    assert policy["run_ids"] == analysis["run_ids"]
    assert policy["probability_source"] == "raw"
    assert {item["policy"] for item in policy["risk_coverage"]} == {"NO_REVIEW", "RANDOM_REVIEW", "CONFIDENCE_ONLY", "STABILITY_AWARE"}
    applied = client.post("/api/projects/analyses/stability-policies/apply", json={"session_id": session_id, "policy_id": policy["policy_id"], "sample": {"temperature": 55.0, "torque": 25.0}})
    assert applied.status_code == 200, applied.text
    assert applied.json()["disposition"] in {"ACCEPT", "REVIEW", "BLOCK"}
    assert len(applied.json()["run_probabilities"]) == 3
    final = client.post("/api/projects/analyses/final-test", json={"session_id": session_id, "evaluation_id": evaluation_response.json()["evaluation_id"], "threshold_id": threshold.json()["threshold_id"], "stability_gate_policy_id": policy["policy_id"]})
    assert final.status_code == 201, final.text
    assert final.json()["stability_gate_policy_id"] == policy["policy_id"]
    evidence = final.json()["stability_gate_evidence"]
    assert evidence["class_threshold_id"] == threshold.json()["threshold_id"]
    assert evidence["decision_threshold"] == policy["decision_threshold"]
    assert evidence["accepted_count"] + evidence["review_count"] + evidence["block_count"] == final.json()["test_row_count"]
    assert evidence["confidence_only_accepted_count"] == evidence["accepted_count"]
    post_unlock = client.post("/api/projects/analyses/stability-policies", json={"session_id": session_id, "analysis_id": analysis["analysis_id"], "evaluation_id": evaluation_response.json()["evaluation_id"], "min_confidence": .85, "min_class_agreement": .8, "max_probability_std": .15})
    assert post_unlock.status_code == 422
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
    assert listed.json()[0]["class_threshold_id"] == threshold.json()["threshold_id"]
    assert listed.json()[0]["decision_threshold"] == policy["decision_threshold"]
    reopened_policies = client.get(f"/api/projects/{reopened.json()['session_id']}/analyses/stability-policies")
    assert reopened_policies.status_code == 200
    assert reopened_policies.json()[0]["class_threshold_id"] == threshold.json()["threshold_id"]
    assert reopened_policies.json()[0]["decision_threshold"] == policy["decision_threshold"]
    # Assurance must validate references, not merely accept a parseable JSON
    # object in the evidence directory.
    policy_path = tmp_path / "stability" / "analyses" / "stability-policies" / f"{policy['policy_id']}.json"
    corrupted = policy_path.read_text(encoding="utf-8").replace(f'"dataset_fingerprint": "{analysis["dataset_fingerprint"]}"', '"dataset_fingerprint": "wrong-revision"').replace(f'"class_threshold_id": "{threshold.json()["threshold_id"]}"', '"class_threshold_id": "00000000-0000-0000-0000-000000000000"')
    policy_path.write_text(corrupted, encoding="utf-8")
    invalid_assurance = client.post("/api/projects/evidence/assurance-cases", json={"session_id": session_id})
    invalid_gates = {gate["key"]: gate for gate in invalid_assurance.json()["gates"]}
    assert invalid_gates["stability_gate_policy"]["status"] == "FAIL"


def test_confident_selected_run_minority_uses_selected_run_agreement() -> None:
    selected = uuid4(); run_ids = [selected, *[uuid4() for _ in range(19)]]
    policy = StabilityGatePolicy(study_id=uuid4(), stability_analysis_id=uuid4(), selected_run_id=selected, evaluation_id=uuid4(), class_threshold_id=uuid4(), decision_threshold=.5, model_kind="random_forest", fit_sample_identity="validation", run_ids=run_ids, analysis_schema_version=3, min_confidence=.8, min_class_agreement=.8, max_probability_std=1.0, decisions=[], risk_coverage=[])
    result = evaluate_frozen_stability_probabilities(policy, {str(selected): .9, **{str(run_id): .49 for run_id in run_ids[1:]}})
    assert result.majority_class_agreement == .95
    assert result.selected_run_agreement == .05
    assert result.disposition == "REVIEW"
    assert "RUN_DISAGREEMENT" in result.reasons


def test_stability_gate_uses_non_half_frozen_decision_threshold() -> None:
    selected = uuid4(); run_ids = [selected, uuid4(), uuid4()]
    policy = StabilityGatePolicy(
        study_id=uuid4(), stability_analysis_id=uuid4(), selected_run_id=selected,
        evaluation_id=uuid4(), class_threshold_id=uuid4(), decision_threshold=.8,
        model_kind="random_forest", fit_sample_identity="validation", run_ids=run_ids,
        analysis_schema_version=3, min_confidence=.5, min_class_agreement=.8,
        max_probability_std=1.0, decisions=[], risk_coverage=[],
    )
    # At the frozen .8 threshold all three fits vote class 0.  A hidden .5
    # threshold would instead label all three class 1.
    result = evaluate_frozen_stability_probabilities(
        policy, {str(run_ids[0]): .75, str(run_ids[1]): .70, str(run_ids[2]): .72},
    )
    assert result.predicted_label == 0
    assert result.selected_run_agreement == 1.0
    assert result.disposition == "ACCEPT"


def test_zero_hcir_denominator_is_undefined(tmp_path: Path) -> None:
    client, session_id = _project(tmp_path)
    study = client.post("/api/projects/training/studies", json={"session_id": session_id, "name": "fixed", "model_kind": "random_forest", "seeds": [11, 13, 17], "randomness_protocol": "TRAINING_VARIABILITY", "split_seed": 42, "selection_metric": "f1", "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3}).json()
    evaluation = client.post("/api/projects/analyses/evaluations", json={"session_id": session_id, "run_id": study["selected_run_id"]}).json()
    threshold = client.post("/api/projects/analyses/thresholds", json={"session_id": session_id, "evaluation_id": evaluation["evaluation_id"]}).json()
    analysis = client.post("/api/projects/analyses/stability", json={"session_id": session_id, "study_id": study["study_id"], "evaluation_id": evaluation["evaluation_id"], "threshold_id": threshold["threshold_id"], "high_confidence_threshold": 1.0}).json()
    assert analysis["high_confidence_case_count"] == 0
    assert analysis["high_confidence_instability_rate"] is None
    assert any("HCIR is undefined" in warning for warning in analysis["warnings"])


def test_split_variability_persists_not_applicable_case_level_evidence(tmp_path: Path) -> None:
    client, session_id = _project(tmp_path)
    response = client.post("/api/projects/training/studies", json={"session_id": session_id, "name": "variable split", "model_kind": "random_forest", "seeds": [11, 13, 17], "randomness_protocol": "SPLIT_VARIABILITY", "training_seed": 5, "selection_metric": "f1", "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert response.status_code == 201, response.text
    analysis = client.post("/api/projects/analyses/stability", json={"session_id": session_id, "study_id": response.json()["study_id"]})
    assert analysis.status_code == 201, analysis.text
    payload = analysis.json()
    assert payload["mode"] == "SPLIT_VARIABILITY"
    assert payload["applicability"] == "NOT_APPLICABLE"
    assert payload["validation_alignment_status"] == "NOT_APPLICABLE"
    assert payload["cases"] == []
    assert payload["high_confidence_instability_rate"] is None
    evaluation = client.post("/api/projects/analyses/evaluations", json={"session_id": session_id, "run_id": response.json()["selected_run_id"]})
    blocked = client.post("/api/projects/analyses/stability-policies", json={"session_id": session_id, "analysis_id": payload["analysis_id"], "evaluation_id": evaluation.json()["evaluation_id"], "min_confidence": .9, "min_class_agreement": .8, "max_probability_std": .15})
    assert blocked.status_code == 422


def test_combined_variability_is_explicitly_mixed_not_training_seed_evidence(tmp_path: Path) -> None:
    client, session_id = _project(tmp_path)
    response = client.post("/api/projects/training/studies", json={"session_id": session_id, "name": "combined", "model_kind": "random_forest", "seeds": [11, 13, 17], "randomness_protocol": "COMBINED_VARIABILITY", "selection_metric": "f1", "max_epochs": 1, "learning_rate": .01, "batch_size": 16, "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3})
    assert response.status_code == 201, response.text
    analysis = client.post("/api/projects/analyses/stability", json={"session_id": session_id, "study_id": response.json()["study_id"]})
    assert analysis.status_code == 201, analysis.text
    payload = analysis.json()
    assert payload["mode"] == "COMBINED_VARIABILITY"
    assert payload["applicability"] == "NOT_APPLICABLE"
    assert payload["high_confidence_instability_rate"] is None
    assert "mixes sampling and training effects" in payload["applicability_reason"]


def test_stability_gate_refuses_final_test_tuning(tmp_path: Path) -> None:
    client, session_id = _project(tmp_path)
    readonly = client.post("/api/projects/open", json={"path": str(tmp_path / "stability"), "read_only": True})
    response = client.post("/api/projects/analyses/stability", json={"session_id": readonly.json()["session_id"], "study_id": "00000000-0000-0000-0000-000000000000"})
    assert response.status_code == 403
