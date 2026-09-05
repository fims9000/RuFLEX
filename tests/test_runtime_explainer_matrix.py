from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ruflex.application.capabilities import negotiate_run_capabilities
from ruflex.application.datasets import build_dataset_contract, inspect_dataset, persist_dataset_bytes, persist_dataset_contract, run_data_audit
from ruflex.application.evidence import EvidenceError, check_explanation, create_runtime_explanation, load_explanation
from ruflex.application.runtime_training import train_with_adapter
from ruflex.runtime import builtin_runtime_registry


def _project(root: Path) -> None:
    frame = pd.DataFrame({
        "temperature": [10.0 + index * .5 for index in range(48)],
        "torque": [20.0 + (index * 7) % 50 for index in range(48)],
        "vibration": [.1 + (index % 5) * .1 for index in range(48)],
        "target": [int((index * 7) % 11 > 4) for index in range(48)],
    })
    source = persist_dataset_bytes(root, frame.to_csv(index=False).encode("utf-8"))
    profile = inspect_dataset(frame, source_artifact_sha256=source.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification")
    persist_dataset_contract(root, contract, run_data_audit(contract, frame), profile)


def _runs(root: Path):
    registry = builtin_runtime_registry()
    parameters = {
        "flat_neuro_fuzzy": {"max_epochs": 2, "batch_size": 16, "patience": 2, "max_rules": 3, "learning_rate": .01},
        "logistic_regression": {},
        "decision_tree": {"max_depth": 2},
        "random_forest": {"n_estimators": 3, "max_depth": 2},
        "gradient_boosting": {"n_estimators": 3, "max_depth": 2, "learning_rate": .1},
    }
    return {
        kind: train_with_adapter(root, registry=registry, adapter_key=registry.resolve_training_model_kind(kind).descriptor.identity.key, model_kind=kind, seed=19, parameters=values)
        for kind, values in parameters.items()
    }


def test_registered_explainer_compatibility_matrix_replays_declared_pairs(tmp_path: Path) -> None:
    """Every registered explainer/run pair follows persisted capability truth."""
    _project(tmp_path)
    sample = {"temperature": 18.0, "torque": 34.0, "vibration": .3}
    runs = _runs(tmp_path)
    registry = builtin_runtime_registry()
    explainers = registry.component_descriptors("explainer")
    executed = 0

    for run in runs.values():
        decisions = {item.capability: item.status for item in negotiate_run_capabilities(run).decisions}
        for descriptor in explainers:
            key = descriptor.identity.key
            capability = "shap" if key == "shap" else key
            if decisions.get(capability) == "AVAILABLE":
                explanation = create_runtime_explanation(tmp_path, explainer_key=key, run_id=run.run_id, sample=sample)
                reopened = load_explanation(tmp_path, explanation.explanation_id)
                assert reopened.explainer_key == key
                assert check_explanation(tmp_path, explanation.explanation_id).validator_key == "native_explanation_validator"
                executed += 1
            else:
                with pytest.raises(EvidenceError, match="CAPABILITY_UNAVAILABLE"):
                    create_runtime_explanation(tmp_path, explainer_key=key, run_id=run.run_id, sample=sample)

    # The asserted count guards against an accidental capability-wide fallback.
    assert executed == 15
