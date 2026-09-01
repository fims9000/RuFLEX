from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from ruflex.api.main import app


def _frame(rows: int = 96) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for index in range(rows):
        temperature = 8.0 + index * 0.55
        torque = 15.0 + ((index * 13) % 70)
        wear = ((index * 17) % 25) / 25.0
        site = "north" if index % 3 else "south"
        target = int(temperature + 0.55 * torque + 7.0 * wear > 52.0)
        records.append(
            {
                "site": site,
                "temperature": temperature,
                "torque": torque,
                "wear": wear,
                "target": target,
            }
        )
    return pd.DataFrame(records)


def test_product_v1_project_journey_persists_scientific_objects_and_provenance(tmp_path: Path) -> None:
    """Exercise one coherent Product V1 project instead of isolated endpoints.

    The route deliberately keeps final-test access last: every model choice,
    calibration transform, threshold and slice/explanation analysis is created
    from train/validation evidence before the one-way final-test gate opens.
    """

    client = TestClient(app)
    root = tmp_path / "ruflex-v1-journey"

    created = client.post("/api/projects", json={"path": str(root), "name": "Product V1 journey"})
    assert created.status_code == 201, created.text
    session_id = created.json()["session_id"]

    frame = _frame()
    confirmed = client.post(
        "/api/projects/dataset/confirm",
        json={
            "session_id": session_id,
            "csv_text": frame.to_csv(index=False),
            "target": "target",
            "task": "binary_classification",
            "id_columns": ["site"],
        },
    )
    assert confirmed.status_code == 200, confirmed.text

    contract = client.post(
        "/api/projects/generalization/contracts",
        json={
            "session_id": session_id,
            "intended_use": "Evaluate the frozen classifier on declared north-site cases.",
            "novelty_axes": [
                {
                    "axis": "site",
                    "expected_future_relation": "deployment site may differ from training sites",
                    "evaluation_requirement": "report site slices separately",
                }
            ],
            "supported_scope": [
                {
                    "field": "site",
                    "operator": "in",
                    "value": ["north"],
                    "rationale": "North is the declared Product V1 scope.",
                }
            ],
            "forbidden_scope": [
                {
                    "field": "site",
                    "operator": "in",
                    "value": ["south"],
                    "rationale": "South is intentionally outside the declared scope.",
                }
            ],
            "unsupported_action": "REVIEW",
        },
    )
    assert contract.status_code == 201, contract.text
    contract_id = contract.json()["contract"]["contract_id"]
    frozen = client.post(
        f"/api/projects/generalization/contracts/{contract_id}/freeze",
        json={"session_id": session_id},
    )
    assert frozen.status_code == 200, frozen.text

    fis_created = client.post(
        "/api/projects/fis/default",
        json={"session_id": session_id, "name": "Manual risk FIS"},
    )
    assert fis_created.status_code == 201, fis_created.text
    fis = fis_created.json()
    fis_inputs = {
        variable["name"]: (variable["minimum"] + variable["maximum"]) / 2.0
        for variable in fis["inputs"]
    }
    fis_run = client.post(
        "/api/projects/fis/evaluate",
        json={"session_id": session_id, "inputs": fis_inputs, "persist_trace": True},
    )
    assert fis_run.status_code == 200, fis_run.text
    assert fis_run.json()["evaluation"]["trace"]["reconstruction_error"] <= 1e-12

    trained = client.post(
        "/api/projects/training/run",
        json={
            "session_id": session_id,
            "model_kind": "decision_tree",
            "seed": 23,
            "max_epochs": 1,
            "learning_rate": 0.01,
            "batch_size": 24,
            "patience": 1,
            "validation_fraction": 0.2,
            "test_fraction": 0.2,
            "max_rules": 4,
        },
    )
    assert trained.status_code == 201, trained.text
    run = trained.json()
    assert run["split"]["test_status"] == "LOCKED_NOT_EVALUATED"

    baseline_response = client.post(
        "/api/projects/training/run",
        json={
            "session_id": session_id,
            "model_kind": "logistic_regression",
            "seed": 23,
            "max_epochs": 1,
            "learning_rate": 0.01,
            "batch_size": 24,
            "patience": 1,
            "validation_fraction": 0.2,
            "test_fraction": 0.2,
            "max_rules": 4,
        },
    )
    assert baseline_response.status_code == 201, baseline_response.text
    baseline_run = baseline_response.json()

    evaluation_response = client.post(
        "/api/projects/analyses/evaluations",
        json={"session_id": session_id, "run_id": run["run_id"]},
    )
    assert evaluation_response.status_code == 201, evaluation_response.text
    evaluation = evaluation_response.json()
    assert evaluation["split"] == "validation"
    assert evaluation["test_status"] == "LOCKED_NOT_EVALUATED"

    calibration_response = client.post(
        "/api/projects/analyses/calibrations",
        json={"session_id": session_id, "evaluation_id": evaluation["evaluation_id"]},
    )
    assert calibration_response.status_code == 201, calibration_response.text
    calibration = calibration_response.json()
    assert calibration["source_split"] == "validation"

    threshold_response = client.post(
        "/api/projects/analyses/thresholds",
        json={
            "session_id": session_id,
            "evaluation_id": evaluation["evaluation_id"],
            "calibration_id": calibration["calibration_id"],
            "objective": "f1",
        },
    )
    assert threshold_response.status_code == 201, threshold_response.text
    threshold = threshold_response.json()
    assert threshold["source_split"] == "validation"

    sample = {
        "temperature": float(frame.iloc[7]["temperature"]),
        "torque": float(frame.iloc[7]["torque"]),
        "wear": float(frame.iloc[7]["wear"]),
    }
    tree_path_response = client.post(
        "/api/projects/training/tree-path",
        json={"session_id": session_id, "run_id": run["run_id"], "sample": sample},
    )
    assert tree_path_response.status_code == 201, tree_path_response.text
    tree_path = tree_path_response.json()
    assert tree_path["label"] == "EXACT TREE EXECUTION PATH"

    explanation_response = client.post(
        "/api/projects/evidence/explanations",
        json={
            "session_id": session_id,
            "run_id": run["run_id"],
            "sample": sample,
            "method": "occlusion",
        },
    )
    assert explanation_response.status_code == 201, explanation_response.text
    explanation = explanation_response.json()
    assert explanation["preprocessing_identity"]
    assert explanation["sample_identity"]

    explanation_check_response = client.post(
        "/api/projects/evidence/explanation-checks",
        json={"session_id": session_id, "explanation_id": explanation["explanation_id"]},
    )
    assert explanation_check_response.status_code == 201, explanation_check_response.text
    explanation_check = explanation_check_response.json()
    assert explanation_check["status"] in {"PASSED_AVAILABLE_CHECKS", "WARNING"}

    validation_rows = evaluation["prediction_preview"]
    assert validation_rows
    manual_source_row = validation_rows[0]["source_row"]
    slices_response = client.post(
        "/api/projects/analyses/slices",
        json={
            "session_id": session_id,
            "evaluation_id": evaluation["evaluation_id"],
            "metric": "f1",
            "definitions": [
                {"name": "north", "kind": "categorical", "field": "site", "values": ["north"]},
                {"name": "one case", "kind": "manual", "source_rows": [manual_source_row]},
            ],
        },
    )
    assert slices_response.status_code == 201, slices_response.text
    slices = slices_response.json()
    assert slices["generalization_contract_id"] == contract_id
    assert slices["test_status"] == "LOCKED_NOT_EVALUATED"

    comparison_response = client.post(
        "/api/projects/analyses/comparisons",
        json={
            "session_id": session_id,
            "run_ids": [run["run_id"], baseline_run["run_id"]],
            "include_active_fis": True,
        },
    )
    assert comparison_response.status_code == 201, comparison_response.text
    comparison = comparison_response.json()
    assert comparison["validation_alignment"] == "same_cases"
    assert {row["subject_type"] for row in comparison["metric_rows"]} == {"training_run", "manual_fis"}
    assert len(comparison["metric_rows"]) == 3

    selective = client.post(
        "/api/projects/analyses/selective-policies",
        json={"session_id": session_id, "evaluation_id": evaluation["evaluation_id"], "calibration_id": calibration["calibration_id"], "threshold_id": threshold["threshold_id"], "confidence_cutoff": 0.8},
    )
    assert selective.status_code == 201, selective.text

    behavior = client.post(
        "/api/projects/evidence/behavior-specs",
        json={"session_id": session_id, "run_id": run["run_id"], "name": "Probability range", "kind": "output_range", "sample": sample, "minimum": 0.0, "maximum": 1.0, "rationale": "Engineering risk probability bound."},
    )
    assert behavior.status_code == 201, behavior.text
    assert client.post("/api/projects/evidence/behavior-specs/run", json={"session_id": session_id, "spec_id": behavior.json()["spec_id"]}).status_code == 201

    exhaustive = client.post("/api/projects/evidence/exhaustive-lab", json={"session_id": session_id, "kind": "decision_tree_structure", "run_id": run["run_id"]})
    assert exhaustive.status_code == 201 and exhaustive.json()["exactness_label"] == "EXACT_FINITE_STRUCTURE"

    second_sample = {**sample, "temperature": sample["temperature"] + 1.0}
    repro_ids = [explanation["explanation_id"]]
    for candidate, current_sample in [(run, second_sample), (baseline_run, sample), (baseline_run, second_sample)]:
        response = client.post("/api/projects/evidence/explanations", json={"session_id": session_id, "run_id": candidate["run_id"], "sample": current_sample, "method": "occlusion"})
        assert response.status_code == 201, response.text
        repro_ids.append(response.json()["explanation_id"])
    reproducibility = client.post("/api/projects/evidence/explanation-reproducibility", json={"session_id": session_id, "explanation_ids": repro_ids})
    assert reproducibility.status_code == 201, reproducibility.text
    assert "class_agreement" in reproducibility.json()["prediction_agreement"]

    final_test_response = client.post(
        "/api/projects/analyses/final-test",
        json={
            "session_id": session_id,
            "evaluation_id": evaluation["evaluation_id"],
            "calibration_id": calibration["calibration_id"],
            "threshold_id": threshold["threshold_id"],
        },
    )
    assert final_test_response.status_code == 201, final_test_response.text
    final_test = final_test_response.json()
    assert final_test["status"] == "FINAL_TEST_EVALUATED"
    assert final_test["split"] == "test"
    assert final_test["calibration_id"] == calibration["calibration_id"]
    assert final_test["threshold_id"] == threshold["threshold_id"]

    # Frozen policy replay is idempotent rather than silently re-opening the
    # holdout as a fresh selection opportunity.
    repeated_final = client.post(
        "/api/projects/analyses/final-test",
        json={
            "session_id": session_id,
            "evaluation_id": evaluation["evaluation_id"],
            "calibration_id": calibration["calibration_id"],
            "threshold_id": threshold["threshold_id"],
        },
    )
    assert repeated_final.status_code == 201, repeated_final.text
    assert repeated_final.json()["final_test_id"] == final_test["final_test_id"]

    assurance = client.post("/api/projects/evidence/assurance-cases", json={"session_id": session_id})
    assert assurance.status_code == 201, assurance.text
    bundle = client.post("/api/projects/evidence/verification-bundles", json={"session_id": session_id})
    assert bundle.status_code == 201 and len(bundle.json()["sha256"]) == 64

    lineage_response = client.get(f"/api/projects/{session_id}/lineage")
    assert lineage_response.status_code == 200, lineage_response.text
    lineage = lineage_response.json()
    node_kinds = {node["kind"] for node in lineage["nodes"]}
    expected_node_kinds = {
        "dataset",
        "fis_revision",
        "training_run",
        "evaluation",
        "calibration",
        "decision_threshold",
        "final_test_evaluation",
        "explanation",
        "explanation_check",
        "generalization_contract",
        "slice_analysis",
        "comparison",
    }
    assert expected_node_kinds.issubset(node_kinds), (expected_node_kinds - node_kinds, node_kinds)

    assert client.post("/api/projects/close", json={"session_id": session_id}).status_code == 204
    reopened_response = client.post("/api/projects/open", json={"path": str(root), "read_only": False})
    assert reopened_response.status_code == 200, reopened_response.text
    reopened = reopened_response.json()["session_id"]

    assert client.get(f"/api/projects/{reopened}/dataset").status_code == 200
    assert client.get(f"/api/projects/{reopened}/fis/active").json()["fis_id"] == fis["fis_id"]
    assert client.get(f"/api/projects/{reopened}/fis/trace/latest").status_code == 200
    assert client.get(f"/api/projects/{reopened}/analyses/evaluations/latest").json()["evaluation_id"] == evaluation["evaluation_id"]
    assert client.get(f"/api/projects/{reopened}/analyses/calibrations/latest").json()["calibration_id"] == calibration["calibration_id"]
    assert client.get(f"/api/projects/{reopened}/analyses/thresholds/latest").json()["threshold_id"] == threshold["threshold_id"]
    assert client.get(f"/api/projects/{reopened}/analyses/final-test/latest").json()["final_test_id"] == final_test["final_test_id"]
    assert client.get(f"/api/projects/{reopened}/evidence/tree-path/latest").json()["evidence_id"] == tree_path["evidence_id"]
    assert client.get(f"/api/projects/{reopened}/evidence/explanations/latest").json()["explanation_id"] in repro_ids
    assert client.get(f"/api/projects/{reopened}/evidence/explanation-checks/latest").json()["check_id"] == explanation_check["check_id"]
    assert client.get(f"/api/projects/{reopened}/analyses/slices/latest").json()["analysis_id"] == slices["analysis_id"]
    assert client.get(f"/api/projects/{reopened}/generalization/contracts/active").json()["contract"]["contract_id"] == contract_id
    assert client.get(f"/api/projects/{reopened}/evidence/explanation-reproducibility/latest").status_code == 200
    assert client.get(f"/api/projects/{reopened}/evidence/exhaustive-lab/latest").status_code == 200
    assert client.get(f"/api/projects/{reopened}/evidence/assurance-cases/latest").status_code == 200
    assert client.get(f"/api/projects/{reopened}/lineage").status_code == 200
