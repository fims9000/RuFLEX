"""Run a synthetic, product-native A01 pre-final-test smoke route.

This is deliberately not an A01 benchmark execution: it uses a generated
fixture outside the A01 tree and refuses to create a FinalTestEvaluation.
"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi.testclient import TestClient

from ruflex.api.main import app


def _fixture() -> pd.DataFrame:
    return pd.DataFrame([
        {"sensor_a": 20 + index * .7, "sensor_b": (index * 11) % 37, "failure": int(20 + index * .7 + (index * 11) % 37 > 49)}
        for index in range(72)
    ])


def _must(response):
    if response.status_code >= 400:
        raise RuntimeError(response.text)
    return response.json()


def run_smoke(project_root: Path | None = None) -> dict[str, Any]:
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if project_root is None:
        temporary = tempfile.TemporaryDirectory(prefix="ruflex-a01-smoke-")
        project_root = Path(temporary.name) / "project"
    project_root = project_root.resolve()
    a01_root = Path(__file__).resolve().parents[1]
    if a01_root == project_root or a01_root in project_root.parents:
        raise ValueError("A01 smoke project must be outside the A01 research tree.")
    client = TestClient(app)
    session = _must(client.post("/api/projects", json={"path": str(project_root), "name": "A01 synthetic smoke — not evidence"}))["session_id"]
    _must(client.post("/api/projects/dataset/confirm", json={"session_id": session, "csv_text": _fixture().to_csv(index=False), "target": "failure", "task": "binary_classification", "id_columns": []}))
    study = _must(client.post("/api/projects/training/studies", json={
        "session_id": session, "name": "A01 smoke only — not benchmark evidence", "model_kind": "random_forest",
        "seeds": [0, 1, 2], "randomness_protocol": "TRAINING_VARIABILITY", "split_seed": 42,
        "selection_metric": "f1", "max_epochs": 1, "learning_rate": .01, "batch_size": 16,
        "patience": 1, "validation_fraction": .2, "test_fraction": .2, "max_rules": 3,
    }))
    evaluation = _must(client.post("/api/projects/analyses/evaluations", json={"session_id": session, "run_id": study["selected_run_id"]}))
    threshold = _must(client.post("/api/projects/analyses/thresholds", json={"session_id": session, "evaluation_id": evaluation["evaluation_id"], "objective": "f1"}))
    analysis = _must(client.post("/api/projects/analyses/stability", json={"session_id": session, "study_id": study["study_id"], "evaluation_id": evaluation["evaluation_id"], "threshold_id": threshold["threshold_id"], "high_confidence_threshold": .9, "unstable_agreement_threshold": .8}))
    policy = _must(client.post("/api/projects/analyses/stability-policies", json={"session_id": session, "analysis_id": analysis["analysis_id"], "evaluation_id": evaluation["evaluation_id"], "min_confidence": .9, "min_class_agreement": .8, "max_probability_std": .15}))
    lineage = _must(client.get(f"/api/projects/{session}/lineage"))
    assurance = _must(client.post("/api/projects/evidence/assurance-cases", json={"session_id": session}))
    bundle = _must(client.post("/api/projects/evidence/verification-bundles", json={"session_id": session}))
    close = client.post("/api/projects/close", json={"session_id": session})
    if close.status_code >= 400:
        raise RuntimeError(close.text)
    reopened = _must(client.post("/api/projects/open", json={"path": str(project_root)}))["session_id"]
    restored = _must(client.get(f"/api/projects/{reopened}/analyses/stability"))
    final_root = project_root / "analyses" / "final-tests"
    if final_root.exists() and any(final_root.glob("*.json")):
        raise RuntimeError("Smoke route must not create FinalTestEvaluation evidence.")
    result = {
        "status": "SMOKE_PASS_NOT_A01_EVIDENCE", "project_root": str(project_root), "study_id": study["study_id"],
        "evaluation_id": evaluation["evaluation_id"], "threshold_id": threshold["threshold_id"], "analysis_id": analysis["analysis_id"],
        "policy_id": policy["policy_id"], "lineage_node_count": len(lineage["nodes"]), "assurance_id": assurance["assurance_id"],
        "verification_bundle": bundle["path"], "reopened_analysis_count": len(restored), "final_test_accessed": False,
    }
    if temporary is not None:
        result["project_root"] = "temporary synthetic smoke project removed after execution"
        result["verification_bundle"] = "temporary synthetic smoke bundle removed after execution"
        temporary.cleanup()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()
    import json
    print(json.dumps(run_smoke(args.project_root), sort_keys=True))
