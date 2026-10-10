from __future__ import annotations

import pytest
import pandas as pd

from ruflex.application import runtime_training
from ruflex.application.datasets import build_dataset_contract, inspect_dataset, persist_dataset_bytes, persist_dataset_contract, run_data_audit
from ruflex.application.projects import ProjectService
from ruflex.application.training import train_model
from ruflex.runtime.errors import RuntimeIncompatibleError


def test_train_model_preserves_typed_runtime_incompatibility(monkeypatch, tmp_path) -> None:
    root = tmp_path / "project"
    ProjectService().create(root, name="Runtime error identity")
    frame = pd.DataFrame({"x": range(36), "target": [index % 2 for index in range(36)]})
    source = persist_dataset_bytes(root, frame.to_csv(index=False).encode())
    profile = inspect_dataset(frame, source_artifact_sha256=source.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification")
    persist_dataset_contract(root, contract, run_data_audit(contract, frame), profile)
    expected = RuntimeIncompatibleError("The frozen split is incompatible with this training request.")

    def reject(*args, **kwargs):
        raise expected

    monkeypatch.setattr(runtime_training, "train_with_adapter", reject)

    with pytest.raises(RuntimeIncompatibleError) as captured:
        train_model(root, model_kind="logistic_regression", seed=5)

    assert captured.value.code == "RUNTIME_INCOMPATIBLE"
    assert str(captured.value) == str(expected)
