import json
from pathlib import Path

import pandas as pd

from ruflex.application.datasets import build_dataset_contract, inspect_dataset, persist_dataset_bytes, persist_dataset_contract, run_data_audit
from ruflex.application.generalization import create_generalization_contract, persist_generalization_contract
from ruflex.application.projects import ProjectService
from ruflex.application.training import create_validation_evaluation, evaluate_final_test, fit_validation_calibration, select_validation_threshold, train_linear_baseline
from ruflex.sdk import open_studio_project


def test_python_escape_hatch_opens_same_canonical_project(tmp_path: Path) -> None:
    root = tmp_path / "sdk-project"
    ProjectService().create(root, name="SDK project")
    frame = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "target": [0, 0, 1, 1]})
    ref = persist_dataset_bytes(root, frame.to_csv(index=False).encode(), original_name="sdk.csv")
    profile = inspect_dataset(frame, source_artifact_sha256=ref.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification")
    persist_dataset_contract(root, contract, run_data_audit(contract, frame), profile)

    project = open_studio_project(root)
    assert project.manifest.name == "SDK project"
    assert project.dataset_contract().dataset_fingerprint == contract.dataset_fingerprint
    assert any(node.kind == "dataset" for node in project.lineage().nodes)
    assert project.jobs() == []
    assert [plugin.key for plugin in project.explanation_validator_plugins()] == ["native_explanation_validator"]
    assert {item.key for item in project.model_capabilities()} >= {"flat_neuro_fuzzy", "decision_tree", "linear"}


def test_read_only_sdk_resolves_legacy_run_identity_without_rewriting_it(tmp_path: Path) -> None:
    root = tmp_path / "sdk-legacy-runtime"
    ProjectService().create(root, name="SDK legacy runtime")
    frame = pd.DataFrame({"x": list(range(36)), "target": [index % 2 for index in range(36)]})
    ref = persist_dataset_bytes(root, frame.to_csv(index=False).encode(), original_name="legacy.csv")
    profile = inspect_dataset(frame, source_artifact_sha256=ref.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification")
    persist_dataset_contract(root, contract, run_data_audit(contract, frame), profile)
    run = train_linear_baseline(root, kind="logistic_regression", seed=19)

    run_path = root / "runs" / f"{run.run_id}.json"
    payload = json.loads(run_path.read_text(encoding="utf-8"))
    payload["schema_version"] = 2
    for field in ("adapter_key", "adapter_version", "adapter_provider", "adapter_kind", "runtime_capability_snapshot_hash"):
        payload.pop(field, None)
    run_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    original_bytes = run_path.read_bytes()

    reopened = open_studio_project(root)
    legacy_run = next(item for item in reopened.training_runs() if item.run_id == run.run_id)

    assert (legacy_run.adapter_key, legacy_run.adapter_version) == ("native_linear", "1")
    assert run_path.read_bytes() == original_bytes


def test_python_escape_hatch_reads_persisted_analysis_and_active_generalization(tmp_path: Path) -> None:
    root = tmp_path / "sdk-analysis-project"
    service = ProjectService()
    canonical_project = service.create(root, name="SDK analysis project")
    frame = pd.DataFrame(
        {
            "site": ["A" if index % 2 == 0 else "B" for index in range(80)],
            "x": [float(index) / 10.0 for index in range(80)],
            "z": [float((index * 7) % 19) for index in range(80)],
            "target": [0 if index % 4 < 2 else 1 for index in range(80)],
        }
    )
    ref = persist_dataset_bytes(root, frame.to_csv(index=False).encode(), original_name="sdk-analysis.csv")
    profile = inspect_dataset(frame, source_artifact_sha256=ref.sha256)
    contract = build_dataset_contract(
        profile,
        target="target",
        task="binary_classification",
        id_columns=["site"],
    )
    persist_dataset_contract(root, contract, run_data_audit(contract, frame), profile)

    run = train_linear_baseline(root, kind="logistic_regression", seed=13)
    evaluation = create_validation_evaluation(root, run.run_id)
    calibration = fit_validation_calibration(root, evaluation.evaluation_id)
    threshold = select_validation_threshold(
        root,
        evaluation.evaluation_id,
        calibration_id=calibration.calibration_id,
    )
    final_test = evaluate_final_test(
        root,
        evaluation.evaluation_id,
        calibration_id=calibration.calibration_id,
        threshold_id=threshold.threshold_id,
    )
    generalization = create_generalization_contract(
        contract,
        {
            "intended_use": "Evaluate transfer to unseen sites",
            "novelty_axes": [
                {
                    "axis": "site",
                    "expected_future_relation": "unseen site",
                    "evaluation_requirement": "site holdout",
                }
            ],
        },
    )
    persist_generalization_contract(root, generalization)
    canonical_project.manifest.active_generalization_contract_id = generalization.contract_id
    service.save(canonical_project)

    project = open_studio_project(root)
    assert project.evaluation(evaluation.evaluation_id).run_id == run.run_id
    reopened_run = next(item for item in project.training_runs() if item.run_id == run.run_id)
    assert (reopened_run.adapter_key, reopened_run.adapter_version) == ("native_linear", "1")
    assert project.calibration(calibration.calibration_id).evaluation_id == evaluation.evaluation_id
    assert project.threshold(threshold.threshold_id).calibration_id == calibration.calibration_id
    assert project.final_test(final_test.final_test_id).policy_identity == final_test.policy_identity
    assert project.generalization_contract().contract_id == generalization.contract_id
