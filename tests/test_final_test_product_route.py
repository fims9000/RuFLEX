from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ruflex.application.datasets import (
    build_dataset_contract,
    inspect_dataset,
    persist_dataset_bytes,
    persist_dataset_contract,
    run_data_audit,
)
from ruflex.application.projects import ProjectService
from ruflex.application.training import (
    TrainingError,
    create_validation_evaluation,
    evaluate_final_test,
    select_validation_threshold,
    train_model,
)
from ruflex.application.selective import create_selective_policy


def _frame(rows: int = 80) -> pd.DataFrame:
    records = []
    for index in range(rows):
        a = float(index) / 8.0
        b = float((index * 13) % 31) / 5.0
        records.append({"a": a, "b": b, "target": int(a + b > 8.0)})
    return pd.DataFrame(records)


def _project(root: Path) -> None:
    ProjectService().create(root, name="Final test replay")
    frame = _frame()
    ref = persist_dataset_bytes(root, frame.to_csv(index=False).encode(), original_name="data.csv")
    profile = inspect_dataset(frame, source_artifact_sha256=ref.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification")
    persist_dataset_contract(root, contract, run_data_audit(contract, frame), profile)


@pytest.mark.parametrize(
    "model_kind",
    ["logistic_regression", "decision_tree", "random_forest", "gradient_boosting", "flat_neuro_fuzzy"],
)
def test_final_test_replays_each_product_v1_trainable_classifier_without_refit(tmp_path: Path, model_kind: str) -> None:
    root = tmp_path / model_kind
    _project(root)
    run = train_model(
        root,
        model_kind=model_kind,
        seed=29,
        max_epochs=1,
        learning_rate=0.01,
        batch_size=16,
        patience=1,
        validation_fraction=0.2,
        test_fraction=0.2,
        max_rules=3,
    )
    evaluation = create_validation_evaluation(root, run.run_id)
    threshold = select_validation_threshold(root, evaluation.evaluation_id)
    final_test = evaluate_final_test(root, evaluation.evaluation_id, threshold_id=threshold.threshold_id)

    assert final_test.run_id == run.run_id
    assert final_test.test_row_count == run.split.test_count
    assert final_test.threshold_id == threshold.threshold_id
    assert final_test.probability_source == "raw"
    assert 0.0 <= final_test.metrics["accuracy"] <= 1.0
    assert 0.0 <= final_test.metrics["f1"] <= 1.0
    assert all(row.source_row is not None for row in final_test.prediction_rows)


def test_final_test_firewall_blocks_late_selective_policy_tuning(tmp_path: Path) -> None:
    root = tmp_path / "late-selective"; _project(root)
    run = train_model(root, model_kind="logistic_regression", seed=29, max_epochs=1, learning_rate=.01, batch_size=16, patience=1, validation_fraction=.2, test_fraction=.2, max_rules=3)
    evaluation = create_validation_evaluation(root, run.run_id); threshold = select_validation_threshold(root, evaluation.evaluation_id)
    evaluate_final_test(root, evaluation.evaluation_id, threshold_id=threshold.threshold_id)
    with pytest.raises(TrainingError, match="cannot be tuned"):
        create_selective_policy(root, evaluation.evaluation_id, .8)


def _regression_frame(rows: int = 72) -> pd.DataFrame:
    records = []
    for index in range(rows):
        x = float(index) / 9.0
        z = float((index * 5) % 17) / 4.0
        records.append({"x": x, "z": z, "target": 1.5 * x - 0.7 * z + 2.0})
    return pd.DataFrame(records)


@pytest.mark.parametrize("model_kind", ["linear_regression", "decision_tree", "random_forest", "gradient_boosting", "flat_neuro_fuzzy"])
def test_final_test_replays_product_v1_regressors_without_decision_policy(tmp_path: Path, model_kind: str) -> None:
    root = tmp_path / f"reg-{model_kind}"
    ProjectService().create(root, name="Final test regression")
    frame = _regression_frame()
    ref = persist_dataset_bytes(root, frame.to_csv(index=False).encode(), original_name="reg.csv")
    profile = inspect_dataset(frame, source_artifact_sha256=ref.sha256)
    contract = build_dataset_contract(profile, target="target", task="regression")
    persist_dataset_contract(root, contract, run_data_audit(contract, frame), profile)

    run = train_model(
        root,
        model_kind=model_kind,
        seed=31,
        max_epochs=1,
        learning_rate=0.01,
        batch_size=16,
        patience=1,
        validation_fraction=0.2,
        test_fraction=0.2,
        max_rules=3,
    )
    evaluation = create_validation_evaluation(root, run.run_id)
    final_test = evaluate_final_test(root, evaluation.evaluation_id)

    assert final_test.probability_source == "not_applicable"
    assert final_test.decision_threshold is None
    assert final_test.test_row_count == run.split.test_count
    assert "rmse" in final_test.metrics
    assert "mae" in final_test.metrics
    assert all(row.residual is not None for row in final_test.prediction_rows)
