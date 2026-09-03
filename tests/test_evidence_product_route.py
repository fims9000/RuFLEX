from __future__ import annotations

from pathlib import Path
import time

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ruflex.api.main import app
from ruflex.application.jobs import Job, JobStatus, persist_job


def _frame(rows: int = 48) -> pd.DataFrame:
    records = []
    for index in range(rows):
        temperature = 8.0 + index * 0.65
        torque = 18.0 + (index * 13) % 70
        vibration = 0.1 + ((index * 7) % 20) / 20.0
        target = int(temperature + 0.55 * torque + 8 * vibration > 50)
        records.append({"temperature": temperature, "torque": torque, "vibration": vibration, "target": target})
    return pd.DataFrame(records)


def _project_with_data(client: TestClient, root: Path) -> str:
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Evidence"}).json()["session_id"]
    response = client.post(
        "/api/projects/dataset/confirm",
        json={
            "session_id": session_id,
            "csv_text": _frame().to_csv(index=False),
            "target": "target",
            "task": "binary_classification",
            "id_columns": [],
        },
    )
    assert response.status_code == 200, response.text
    return session_id


def _train(client: TestClient, session_id: str, model_kind: str) -> dict:
    response = client.post(
        "/api/projects/training/run",
        json={
            "session_id": session_id,
            "model_kind": model_kind,
            "seed": 31,
            "max_epochs": 2,
            "learning_rate": 0.05,
            "batch_size": 16,
            "patience": 2,
            "validation_fraction": 0.2,
            "test_fraction": 0.2,
            "max_rules": 4,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_posthoc_occlusion_is_persisted_checked_and_not_mislabeled_exact(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "occlusion"
    session_id = _project_with_data(client, root)
    run = _train(client, session_id, "logistic_regression")
    sample = {"temperature": 25.0, "torque": 48.0, "vibration": 0.6}

    created = client.post(
        "/api/projects/evidence/explanations/occlusion",
        json={"session_id": session_id, "run_id": run["run_id"], "sample": sample},
    )
    assert created.status_code == 201, created.text
    explanation = created.json()
    assert explanation["epistemic_category"] == "POST-HOC ATTRIBUTION"
    assert explanation["exactness"] == "post_hoc"
    assert explanation["family"] == "occlusion"
    assert explanation["preprocessing_artifact_sha256"] == run["preprocessing_artifact_sha256"]
    assert {item["feature"] for item in explanation["attributions"]} == set(run["feature_columns"])
    assert "not a causal" in explanation["scientific_note"]

    checked = client.post(
        "/api/projects/evidence/explanation-checks",
        json={"session_id": session_id, "explanation_id": explanation["explanation_id"]},
    )
    assert checked.status_code == 201, checked.text
    check = checked.json()
    assert check["status"] == "PASSED_AVAILABLE_CHECKS"
    statuses = {item["name"]: item["status"] for item in check["checks"]}
    assert statuses["model_identity"] == "PASS"
    assert statuses["preprocessing_artifact"] == "PASS"
    assert statuses["feature_order_identity"] == "PASS"
    assert statuses["repeatability"] == "PASS"
    assert statuses["causal_validity"] == "N/A"

    assert client.post("/api/projects/close", json={"session_id": session_id}).status_code == 204
    reopened = client.post("/api/projects/open", json={"path": str(root), "read_only": False})
    assert reopened.status_code == 200, reopened.text
    reopened_session = reopened.json()["session_id"]
    latest = client.get(f"/api/projects/{reopened_session}/evidence/explanations/latest")
    latest_check = client.get(f"/api/projects/{reopened_session}/evidence/explanation-checks/latest")
    assert latest.status_code == 200 and latest.json()["explanation_id"] == explanation["explanation_id"]
    assert latest_check.status_code == 200 and latest_check.json()["check_id"] == check["check_id"]


def test_explanation_job_persists_local_executor_lifecycle_and_reopens(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "explanation-job"
    session_id = _project_with_data(client, root)
    run = _train(client, session_id, "logistic_regression")
    started = client.post(
        "/api/projects/evidence/explanation-jobs",
        json={
            "session_id": session_id,
            "run_id": run["run_id"],
            "sample": {"temperature": 25.0, "torque": 48.0, "vibration": 0.6},
            "method": "occlusion",
        },
    )
    assert started.status_code == 202, started.text
    job = started.json()
    assert job["kind"] == "explanation_generation"
    assert job["request"]["run_id"] == run["run_id"]
    for _ in range(100):
        job = client.get(f"/api/projects/{session_id}/evidence/explanation-jobs/{job['job_id']}").json()
        if job["status"] not in {"queued", "running"}:
            break
        time.sleep(0.02)
    assert job["status"] == "succeeded", job
    assert job["progress"] == 1.0
    explanation = client.get(f"/api/projects/{session_id}/evidence/explanations/{job['output']['explanation_id']}")
    assert explanation.status_code == 200
    checked = client.post(
        "/api/projects/evidence/explanation-check-jobs",
        json={"session_id": session_id, "explanation_id": job["output"]["explanation_id"]},
    )
    assert checked.status_code == 202, checked.text
    check_job = checked.json()
    for _ in range(100):
        check_job = client.get(f"/api/projects/{session_id}/evidence/explanation-jobs/{check_job['job_id']}").json()
        if check_job["status"] not in {"queued", "running"}:
            break
        time.sleep(0.02)
    assert check_job["status"] == "succeeded", check_job
    check = client.get(f"/api/projects/{session_id}/evidence/explanation-checks/{check_job['output']['check_id']}")
    assert check.status_code == 200
    assert client.post("/api/projects/close", json={"session_id": session_id}).status_code == 204
    reopened = client.post("/api/projects/open", json={"path": str(root), "read_only": False}).json()["session_id"]
    persisted = client.get(f"/api/projects/{reopened}/evidence/explanation-jobs")
    assert persisted.status_code == 200
    assert persisted.json()[0]["job_id"] == job["job_id"]
    assert persisted.json()[0]["output"] == job["output"]


def test_queued_evidence_job_can_cancel_without_creating_a_canonical_output(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "queued-cancel"
    session_id = _project_with_data(client, root)
    queued = persist_job(root, Job(kind="explanation_generation", message="Queued for LocalExecutor."))
    cancelled = client.post(f"/api/projects/{session_id}/evidence/jobs/{queued.job_id}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["output"] == {}
    assert cancelled.json()["finished_at"] is not None
    assert client.post(f"/api/projects/{session_id}/evidence/jobs/{queued.job_id}/cancel").json()["status"] == "cancelled"
    running = persist_job(root, Job(kind="explanation_generation", status=JobStatus.RUNNING))
    rejected = client.post(f"/api/projects/{session_id}/evidence/jobs/{running.job_id}/cancel")
    assert rejected.status_code == 409
    assert "not safely interruptible" in rejected.text


def test_assurance_claim_refuses_an_unbound_claim() -> None:
    from ruflex.domain.assurance import AssuranceClaim
    with pytest.raises(ValidationError):
        AssuranceClaim(statement="Unbound claim", status="SUPPORTED", evidence_ids=[])


def test_behavior_spec_is_revision_bound_persists_and_reopens(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "behavior"
    session_id = _project_with_data(client, root)
    run = _train(client, session_id, "logistic_regression")
    spec = client.post("/api/projects/evidence/behavior-specs", json={
        "session_id": session_id, "run_id": run["run_id"], "name": "Probability range",
        "kind": "output_range", "sample": {"temperature": 25.0, "torque": 48.0, "vibration": 0.6},
        "minimum": 0.0, "maximum": 1.0, "rationale": "Binary probability must be bounded.",
    })
    assert spec.status_code == 201, spec.text
    result = client.post("/api/projects/evidence/behavior-specs/run", json={"session_id": session_id, "spec_id": spec.json()["spec_id"]})
    assert result.status_code == 201, result.text
    assert result.json()["status"] == "PASS"
    assert result.json()["model_artifact_sha256"] == run["model_artifact_sha256"]
    assert client.post("/api/projects/close", json={"session_id": session_id}).status_code == 204
    reopened = client.post("/api/projects/open", json={"path": str(root), "read_only": False}).json()["session_id"]
    latest = client.get(f"/api/projects/{reopened}/evidence/behavior-specs/latest")
    assert latest.status_code == 200 and latest.json()["result_id"] == result.json()["result_id"]
    specs = client.get(f"/api/projects/{reopened}/evidence/behavior-specs")
    results = client.get(f"/api/projects/{reopened}/evidence/behavior-specs/results")
    assert specs.status_code == 200 and specs.json()[0]["spec_id"] == spec.json()["spec_id"]
    assert results.status_code == 200 and results.json()[0]["result_id"] == result.json()["result_id"]
    invalid_pair = client.post("/api/projects/evidence/behavior-specs", json={
        "session_id": reopened, "run_id": run["run_id"], "name": "Incomplete pair", "kind": "monotonic_pair",
        "sample": {"temperature": 25.0, "torque": 48.0, "vibration": 0.6}, "expected_direction": "nondecreasing",
        "rationale": "A pair must have two explicit cases.",
    })
    assert invalid_pair.status_code == 422
    readonly = client.post("/api/projects/open", json={"path": str(root), "read_only": True}).json()["session_id"]
    denied = client.post("/api/projects/evidence/behavior-specs/run", json={"session_id": readonly, "spec_id": spec.json()["spec_id"]})
    assert denied.status_code == 403


def test_gradient_boosting_declarative_artifact_supports_posthoc_replay(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "gb-evidence"
    session_id = _project_with_data(client, root)
    run = _train(client, session_id, "gradient_boosting")

    explanation = client.post(
        "/api/projects/evidence/explanations/occlusion",
        json={
            "session_id": session_id,
            "run_id": run["run_id"],
            "sample": {"temperature": 20.0, "torque": 44.0, "vibration": 0.4},
        },
    )
    assert explanation.status_code == 201, explanation.text
    payload = explanation.json()
    assert payload["model_kind"] == "gradient_boosting"
    assert 0.0 <= payload["prediction"] <= 1.0
    assert len(payload["attributions"]) == 3


def test_anfis_gradient_explainers_are_posthoc_train_referenced_and_checkable(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "gradient-evidence"
    session_id = _project_with_data(client, root)
    run = _train(client, session_id, "flat_neuro_fuzzy")
    sample = {"temperature": 24.0, "torque": 42.0, "vibration": 0.5}

    for method, family in [("integrated_gradients", "integrated_gradients"), ("gradient_shap", "gradient_shap")]:
        response = client.post(
            "/api/projects/evidence/explanations",
            json={"session_id": session_id, "run_id": run["run_id"], "sample": sample, "method": method},
        )
        assert response.status_code == 201, response.text
        explanation = response.json()
        assert explanation["family"] == family
        assert explanation["epistemic_category"] == "POST-HOC ATTRIBUTION"
        assert explanation["base_value"] is not None
        assert explanation["completeness_error"] is not None
        assert explanation["generation_parameters"]
        assert len(explanation["attributions"]) == len(run["feature_columns"])
        checked = client.post(
            "/api/projects/evidence/explanation-checks",
            json={"session_id": session_id, "explanation_id": explanation["explanation_id"]},
        )
        assert checked.status_code == 201, checked.text
        assert checked.json()["status"] in {"PASSED_AVAILABLE_CHECKS", "WARNING"}


def test_permutation_shap_uses_train_background_and_persists_additivity_evidence(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "shap-evidence"
    session_id = _project_with_data(client, root)
    run = _train(client, session_id, "logistic_regression")
    response = client.post(
        "/api/projects/evidence/explanations",
        json={
            "session_id": session_id,
            "run_id": run["run_id"],
            "sample": {"temperature": 22.0, "torque": 46.0, "vibration": 0.55},
            "method": "shap",
        },
    )
    assert response.status_code == 201, response.text
    explanation = response.json()
    assert explanation["family"] == "shap"
    assert explanation["method"] == "permutation_shap_train_background"
    assert "train-partition" in explanation["reference_definition"]
    assert explanation["base_value"] is not None
    assert explanation["completeness_error"] < 1e-5
    assert explanation["generation_parameters"]["background_count"] == 24
    assert "max_evals" in explanation["generation_parameters"]
    checked = client.post(
        "/api/projects/evidence/explanation-checks",
        json={"session_id": session_id, "explanation_id": explanation["explanation_id"]},
    )
    assert checked.status_code == 201, checked.text
    assert any(item["name"] == "numerical_completeness" for item in checked.json()["checks"])


def test_tree_shap_replays_declarative_tree_models_without_mislabeling_exact_trace(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "tree-shap-evidence"
    session_id = _project_with_data(client, root)
    sample = {"temperature": 23.0, "torque": 51.0, "vibration": 0.45}

    for model_kind in ["decision_tree", "random_forest", "gradient_boosting"]:
        run = _train(client, session_id, model_kind)
        response = client.post(
            "/api/projects/evidence/explanations",
            json={"session_id": session_id, "run_id": run["run_id"], "sample": sample, "method": "tree_shap"},
        )
        assert response.status_code == 201, response.text
        explanation = response.json()
        assert explanation["family"] == "tree_shap"
        assert explanation["method"] == "tree_shap_train_background"
        assert explanation["epistemic_category"] == "POST-HOC ATTRIBUTION"
        assert explanation["exactness"] == "post_hoc"
        assert "train-partition" in explanation["reference_definition"]
        assert explanation["completeness_error"] < 1e-4
        assert explanation["generation_parameters"]["feature_perturbation"] == "tree_path_dependent"
        assert len(explanation["attributions"]) == len(run["feature_columns"])
        if model_kind in {"decision_tree", "random_forest"}:
            assert explanation["output_space"] == "probability"
            assert 0.0 <= explanation["prediction"] <= 1.0
        else:
            assert explanation["output_space"] == "raw_score"
            assert "raw decision score" in explanation["scientific_note"]

        checked = client.post(
            "/api/projects/evidence/explanation-checks",
            json={"session_id": session_id, "explanation_id": explanation["explanation_id"]},
        )
        assert checked.status_code == 201, checked.text
        assert checked.json()["status"] == "PASSED_AVAILABLE_CHECKS"
        assert any(item["name"] == "numerical_completeness" and item["status"] == "PASS" for item in checked.json()["checks"])


def test_cross_run_explanation_reproducibility_persists_and_rejects_incompatible_evidence(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "reproducibility"
    session_id = _project_with_data(client, root)
    left, right = _train(client, session_id, "logistic_regression"), _train(client, session_id, "decision_tree")
    ids: list[str] = []
    for sample in [{"temperature": 22.0, "torque": 46.0, "vibration": 0.55}, {"temperature": 30.0, "torque": 52.0, "vibration": 0.35}]:
        for run in [left, right]:
            response = client.post("/api/projects/evidence/explanations/occlusion", json={"session_id": session_id, "run_id": run["run_id"], "sample": sample})
            assert response.status_code == 201, response.text
            ids.append(response.json()["explanation_id"])
    created = client.post("/api/projects/evidence/explanation-reproducibility", json={"session_id": session_id, "explanation_ids": ids})
    assert created.status_code == 201, created.text
    analysis = created.json()
    assert len(analysis["run_ids"]) == 2 and len(analysis["validation_case_identities"]) > 0
    assert "class_agreement" in analysis["prediction_agreement"]
    assert "mean_sign_agreement" in analysis["explanation_agreement"]
    assert len(analysis["pairwise"]) == 1 and len(analysis["per_feature_variability"]) == 3
    assert "must not be interpreted" in analysis["warnings"][0]
    assert client.post("/api/projects/close", json={"session_id": session_id}).status_code == 204
    reopened = client.post("/api/projects/open", json={"path": str(root), "read_only": False}).json()["session_id"]
    latest = client.get(f"/api/projects/{reopened}/evidence/explanation-reproducibility/latest")
    assert latest.status_code == 200 and latest.json()["analysis_id"] == analysis["analysis_id"]
    assert client.post("/api/projects/evidence/explanation-reproducibility", json={"session_id": reopened, "explanation_ids": ids[:3]}).status_code == 422
    incompatible = client.post("/api/projects/evidence/explanations", json={"session_id": reopened, "run_id": left["run_id"], "sample": {"temperature": 22.0, "torque": 46.0, "vibration": 0.55}, "method": "shap"})
    assert incompatible.status_code == 201, incompatible.text
    assert client.post("/api/projects/evidence/explanation-reproducibility", json={"session_id": reopened, "explanation_ids": [ids[0], ids[1], ids[2], incompatible.json()["explanation_id"]]}).status_code == 422


def test_exhaustive_lab_persists_exact_tree_structure_and_declared_fis_grid(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "exhaustive"
    session_id = _project_with_data(client, root)
    tree = _train(client, session_id, "decision_tree")
    tree_result = client.post("/api/projects/evidence/exhaustive-lab", json={"session_id": session_id, "kind": "decision_tree_structure", "run_id": tree["run_id"]})
    assert tree_result.status_code == 201, tree_result.text
    assert tree_result.json()["exactness_label"] == "EXACT_FINITE_STRUCTURE"
    assert tree_result.json()["state_count"] == len(tree_result.json()["paths"])
    assert client.post("/api/projects/evidence/exhaustive-lab", json={"session_id": session_id, "kind": "decision_tree_structure"}).status_code == 422
    fis = client.post("/api/projects/fis/default", json={"session_id": session_id, "name": "grid fis"})
    assert fis.status_code == 201, fis.text
    grid_result = client.post("/api/projects/evidence/exhaustive-lab", json={"session_id": session_id, "kind": "fis_discrete_grid", "grid_points": 3})
    assert grid_result.status_code == 201, grid_result.text
    assert grid_result.json()["exactness_label"] == "EXACT_ON_DECLARED_DISCRETE_GRID"
    assert "does not fully explain" in grid_result.json()["scientific_note"]
    assert client.post("/api/projects/close", json={"session_id": session_id}).status_code == 204
    reopened = client.post("/api/projects/open", json={"path": str(root), "read_only": False}).json()["session_id"]
    latest = client.get(f"/api/projects/{reopened}/evidence/exhaustive-lab/latest")
    assert latest.status_code == 200 and latest.json()["result_id"] == grid_result.json()["result_id"]


def test_assurance_case_is_persisted_independent_gate_evidence(tmp_path: Path) -> None:
    client = TestClient(app); root = tmp_path / "assurance"; session_id = _project_with_data(client, root)
    fis = client.post("/api/projects/fis/default", json={"session_id": session_id, "name": "bundle centroid fis"})
    assert fis.status_code == 201, fis.text
    created = client.post("/api/projects/evidence/assurance-cases", json={"session_id": session_id})
    assert created.status_code == 201, created.text
    case = created.json(); assert "trust" not in case and any(gate["key"] == "dataset_contract" and gate["status"] == "PASS" for gate in case["gates"])
    assert case["claims"] and all(claim["evidence_ids"] for claim in case["claims"])
    assert any(gate["status"] == "NOT_AVAILABLE" for gate in case["gates"])
    assert client.post("/api/projects/close", json={"session_id": session_id}).status_code == 204
    reopened = client.post("/api/projects/open", json={"path": str(root), "read_only": False}).json()["session_id"]
    assert client.get(f"/api/projects/{reopened}/evidence/assurance-cases/latest").json()["assurance_id"] == case["assurance_id"]
    readonly = client.post("/api/projects/open", json={"path": str(root), "read_only": True}).json()["session_id"]
    assert client.post("/api/projects/evidence/assurance-cases", json={"session_id": readonly}).status_code == 403
    bundle = client.post("/api/projects/evidence/verification-bundles", json={"session_id": reopened})
    assert bundle.status_code == 201, bundle.text
    import zipfile
    with zipfile.ZipFile(bundle.json()["path"]) as archive:
        names = archive.namelist(); assert "verification-manifest.json" in names and "assurance-summary.json" in names and "project.yaml" in names and "lineage.json" in names
        import hashlib, json
        manifest = json.loads(archive.read("verification-manifest.json"))
        assert all(hashlib.sha256(archive.read(name)).hexdigest() == digest for name, digest in manifest["checksums"].items())
        assert archive.read("verification-manifest.sha256").decode().split()[0] == hashlib.sha256(archive.read("verification-manifest.json")).hexdigest()
        assert not any(name.endswith((".pkl", ".joblib")) or "node_modules" in name for name in names)
        fis_entries = [name for name in names if name.startswith("models/fis/") and name.endswith(".json")]
        assert fis_entries
        exported_fis = json.loads(archive.read(fis_entries[0]))
        assert exported_fis["operators"]["centroid_sampling"] == "midpoint_cells"


def test_verification_bundle_validates_portably_and_fails_closed_on_tampering(tmp_path: Path) -> None:
    from ruflex.application.verification_bundle import validate_verification_bundle
    from ruflex.sdk.studio import validate_bundle
    import shutil

    client = TestClient(app); root = tmp_path / "portable-bundle"; session_id = _project_with_data(client, root)
    assert client.post("/api/projects/fis/default", json={"session_id": session_id, "name": "portable bundle fis"}).status_code == 201
    assert client.post("/api/projects/evidence/assurance-cases", json={"session_id": session_id}).status_code == 201
    exported = client.post("/api/projects/evidence/verification-bundles", json={"session_id": session_id})
    assert exported.status_code == 201, exported.text
    bundle_path = Path(exported.json()["path"])
    valid = validate_verification_bundle(bundle_path)
    assert valid.status == "PASS", valid.errors
    api_valid = client.post("/api/verification-bundles/validate", json={"path": str(bundle_path)})
    assert api_valid.status_code == 200 and api_valid.json()["status"] == "PASS"
    assert validate_bundle(bundle_path).status == "PASS"
    extracted = tmp_path / "fresh-root"; shutil.unpack_archive(bundle_path, extracted, "zip")
    assert validate_verification_bundle(extracted).status == "PASS"
    contract = extracted / "data" / "dataset-contract.json"
    contract.write_text('{"tampered": true}', encoding="utf-8")
    invalid = validate_verification_bundle(extracted)
    assert invalid.status == "FAIL"
    assert any("Checksum mismatch" in error for error in invalid.errors)
    api_invalid = client.post("/api/verification-bundles/validate", json={"path": str(extracted)})
    assert api_invalid.status_code == 200 and api_invalid.json()["status"] == "FAIL"


def test_verification_bundle_rejects_rechecksumming_broken_provenance(tmp_path: Path) -> None:
    from ruflex.application.verification_bundle import validate_verification_bundle
    import hashlib
    import json
    import shutil

    client = TestClient(app); root = tmp_path / "broken-provenance"; session_id = _project_with_data(client, root)
    run = _train(client, session_id, "logistic_regression")
    explanation = client.post("/api/projects/evidence/explanations/occlusion", json={"session_id": session_id, "run_id": run["run_id"], "sample": {"temperature": 25.0, "torque": 48.0, "vibration": 0.6}})
    assert explanation.status_code == 201, explanation.text
    assert client.post("/api/projects/evidence/explanation-checks", json={"session_id": session_id, "explanation_id": explanation.json()["explanation_id"]}).status_code == 201
    assert client.post("/api/projects/evidence/assurance-cases", json={"session_id": session_id}).status_code == 201
    bundle = client.post("/api/projects/evidence/verification-bundles", json={"session_id": session_id}).json()
    extracted = tmp_path / "rebuilt-broken"; shutil.unpack_archive(bundle["path"], extracted, "zip")
    check_path = next((extracted / "evidence" / "explanation-checks").glob("*.json"))
    changed = json.loads(check_path.read_text(encoding="utf-8")); changed["run_id"] = "00000000-0000-0000-0000-000000000001"
    check_path.write_text(json.dumps(changed), encoding="utf-8")
    manifest_path = extracted / "verification-manifest.json"; manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    relative = check_path.relative_to(extracted).as_posix(); manifest["checksums"][relative] = hashlib.sha256(check_path.read_bytes()).hexdigest()
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode(); manifest_path.write_bytes(manifest_bytes)
    (extracted / "verification-manifest.sha256").write_text(f"{hashlib.sha256(manifest_bytes).hexdigest()}  verification-manifest.json\n", encoding="utf-8")
    invalid = validate_verification_bundle(extracted)
    assert invalid.status == "FAIL"
    assert any("broken evidence provenance" in error for error in invalid.errors)


def test_assurance_never_passes_malformed_or_failed_behavior_evidence(tmp_path: Path) -> None:
    client = TestClient(app); root = tmp_path / "assurance-negative"; session_id = _project_with_data(client, root)
    malformed = root / "evidence" / "behavior-specs" / "00000000-0000-0000-0000-000000000001.json"
    malformed.parent.mkdir(parents=True, exist_ok=True); malformed.write_text("{not json", encoding="utf-8")
    created = client.post("/api/projects/evidence/assurance-cases", json={"session_id": session_id})
    assert created.status_code == 201
    behavior_gate = next(gate for gate in created.json()["gates"] if gate["key"] == "behavior_specs")
    assert behavior_gate["status"] == "FAIL"
