"""Registry-driven contract matrix: a new built-in automatically enters it."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ruflex.application.artifacts import ArtifactRef, ArtifactStore
from ruflex.application.datasets import build_dataset_contract, inspect_dataset, persist_dataset_bytes, persist_dataset_contract, run_data_audit
from ruflex.application.projects import ProjectService
from ruflex.application.runtime_training import train_with_adapter
from ruflex.application.training import load_training_run
from ruflex.runtime import builtin_runtime_registry
from ruflex.runtime.contracts import PredictionRequest
from ruflex.runtime.errors import RuntimeIncompatibleError


def _prepare(root: Path, task: str) -> None:
    ProjectService().create(root, name="Runtime matrix")
    frame = pd.DataFrame({"x": np.linspace(-2, 2, 48), "z": np.linspace(1, 3, 48)})
    frame["target"] = ([index % 2 for index in range(len(frame))] if task == "binary_classification" else (frame["x"] * .75 + frame["z"] * .25))
    source = persist_dataset_bytes(root, frame.to_csv(index=False).encode())
    profile = inspect_dataset(frame, source_artifact_sha256=source.sha256)
    contract = build_dataset_contract(profile, target="target", task=task)
    persist_dataset_contract(root, contract, run_data_audit(contract, frame), profile)


def _cases() -> list[tuple[str, str, str]]:
    registry = builtin_runtime_registry()
    return [
        (descriptor.identity.key, model_kind, task)
        for descriptor in registry.model_descriptors() if descriptor.available and descriptor.capabilities.get("fit", False)
        for model_kind in descriptor.training_model_kinds
        for task in descriptor.supported_tasks
        if descriptor.supports_model_kind_task(model_kind, task)
    ]


def _rejected_cases() -> list[tuple[str, str, str]]:
    registry = builtin_runtime_registry()
    return [
        (descriptor.identity.key, model_kind, task)
        for descriptor in registry.model_descriptors() if descriptor.available and descriptor.capabilities.get("fit", False)
        for model_kind in descriptor.training_model_kinds
        for task in descriptor.supported_tasks
        if not descriptor.supports_model_kind_task(model_kind, task)
    ]


@pytest.mark.parametrize("adapter_key,model_kind,task", _rejected_cases())
def test_runtime_model_adapter_rejects_undeclared_kind_task_pair(tmp_path: Path, adapter_key: str, model_kind: str, task: str) -> None:
    root = tmp_path / f"{adapter_key}-{model_kind}-{task}"
    _prepare(root, task)

    with pytest.raises(RuntimeIncompatibleError, match="cannot train model kind"):
        train_with_adapter(root, registry=builtin_runtime_registry(), adapter_key=adapter_key, model_kind=model_kind, seed=17)
    assert not list((root / "runs").glob("*.json"))


@pytest.mark.parametrize("adapter_key,model_kind,task", _cases())
def test_runtime_model_adapter_matrix(tmp_path: Path, adapter_key: str, model_kind: str, task: str) -> None:
    root = tmp_path / f"{adapter_key}-{task}"
    _prepare(root, task)
    params = {"max_epochs": 2, "batch_size": 16, "patience": 2, "max_rules": 3, "learning_rate": .01, "n_estimators": 3, "max_depth": 2}
    registry = builtin_runtime_registry()
    run = train_with_adapter(root, registry=registry, adapter_key=adapter_key, model_kind=model_kind, seed=17, parameters=params)
    assert ArtifactStore(root).verify(ArtifactRef(sha256=run.model_artifact_sha256)).valid
    with ArtifactStore(root).open(ArtifactRef(sha256=run.model_artifact_sha256)) as handle:
        before = registry.resolve_model_adapter(adapter_key).predict(PredictionRequest(task=task, feature_names=tuple(run.feature_columns), features=np.zeros((2, len(run.feature_columns))), artifact=handle.read(), model_spec=run.model_spec, preprocessing_identity=run.preprocessing_artifact_sha256 or ""))
    ProjectService().open(root, read_only=True)
    restored = load_training_run(root, run.run_id)
    with ArtifactStore(root).open(ArtifactRef(sha256=restored.model_artifact_sha256)) as handle:
        after = registry.resolve_model_adapter(adapter_key).predict(PredictionRequest(task=task, feature_names=tuple(restored.feature_columns), features=np.zeros((2, len(restored.feature_columns))), artifact=handle.read(), model_spec=restored.model_spec, preprocessing_identity=restored.preprocessing_artifact_sha256 or ""))
    assert before.model_dump() == after.model_dump()
    assert restored.adapter_key == adapter_key
