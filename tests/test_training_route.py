from __future__ import annotations

import pandas as pd

from ruflex.application.datasets import build_dataset_contract, inspect_dataset, persist_dataset_bytes, persist_dataset_contract, run_data_audit
from ruflex.application.fis import create_default_fis


def test_real_ruanfis_training_persists_epoch_zero_best_checkpoint_and_evaluation(tmp_path) -> None:
    from ruflex.application.training_route import load_training_run, train_configured_fis

    root = tmp_path / "project"
    (root / "data").mkdir(parents=True)
    frame = pd.DataFrame({"x1": [0., 1., 0., 1., 0., 1.], "x2": [0., 0., 1., 1., .2, .8], "target": [0, 1, 1, 0, 0, 1]})
    ref = persist_dataset_bytes(root, frame.to_csv(index=False).encode())
    profile = inspect_dataset(frame, source_artifact_sha256=ref.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification")
    persist_dataset_contract(root, contract, run_data_audit(contract, frame), profile)
    create_default_fis(root, input_columns=["x1", "x2"])

    run = train_configured_fis(root, max_epochs=8, patience=3, learning_rate=0.03, validation_fraction=0.34)
    assert run.trajectory[0].epoch == 0
    assert run.best_epoch >= 0
    assert run.model_artifact_sha256
    assert run.validation.metrics["accuracy"] >= 0.0
    assert run.validation.predictions
    restored = load_training_run(root)
    assert restored.run_id == run.run_id
    assert restored.evaluation_artifact_sha256 == run.evaluation_artifact_sha256
