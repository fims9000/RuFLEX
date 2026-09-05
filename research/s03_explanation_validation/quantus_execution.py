"""Frozen S03 Quantus execution semantics.

This module is deliberately research orchestration, not a shadow validator.
It evaluates a persisted :class:`ExplanationContract` against the exact model
the contract declares.  The product-native model replay and explainer builders
remain the source of prediction and attribution semantics.
"""
from __future__ import annotations

import contextlib
import hashlib
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator
from uuid import UUID

import numpy as np
import torch

from ruflex.application import evidence as product_evidence
from ruflex.application.training import load_training_run
from ruflex.data.datasets import NormalizationArtifact
from ruflex.domain.evidence import ExplanationContract

BASE_SEED = 3003
METRICS = ("faithfulness_correlation", "max_sensitivity")
TOLERANCE = 1e-12
_REPLAY_CACHE: dict[tuple[str, str, str, str, bytes], np.ndarray] = {}


def effective_seed(clean_artifact_key: str, metric_name: str) -> int:
    """Derive the frozen common-random-number seed for one clean parent."""
    if metric_name not in METRICS:
        raise ValueError(f"Unknown frozen Quantus metric: {metric_name}")
    payload = f"S03|R6|{BASE_SEED}|{clean_artifact_key}|{metric_name}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big", signed=False)


@contextlib.contextmanager
def controlled_rng(seed: int) -> Iterator[None]:
    """Snapshot/set/restore every RNG Quantus can affect in this process."""
    python_state = random.getstate()
    numpy_state = np.random.get_state()
    torch_state = torch.random.get_rng_state()
    cuda_states = torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None
    try:
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        yield
    finally:
        random.setstate(python_state)
        np.random.set_state(numpy_state)
        torch.random.set_rng_state(torch_state)
        if cuda_states is not None:
            torch.cuda.set_rng_state_all(cuda_states)


def _raw_from_normalized(run, normalized: np.ndarray) -> np.ndarray:
    artifact = NormalizationArtifact.from_dict(run.normalization)
    values = np.asarray(normalized, dtype=float)
    if artifact.mode.value == "none":
        return values
    if artifact.mode.value == "standard":
        return values * np.asarray(artifact.scale, dtype=float) + np.asarray(artifact.center, dtype=float)
    return values * (np.asarray(artifact.maximum, dtype=float) - np.asarray(artifact.minimum, dtype=float)) + np.asarray(artifact.minimum, dtype=float)


class _TargetAdapter(torch.nn.Module):
    """Quantus PyTorch adapter around the product-native declarative replay."""

    def __init__(self, project_root: Path, run) -> None:
        super().__init__()
        self.project_root = Path(project_root)
        self.run = run

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        matrix = inputs.detach().cpu().numpy().reshape(len(inputs), -1)
        probability = product_evidence._predict_normalized_batch(self.project_root, self.run, matrix)
        probability = np.clip(np.asarray(probability, dtype=np.float32), 0.0, 1.0)
        return torch.from_numpy(np.stack((1.0 - probability, probability), axis=1))


def _builder_for(contract: ExplanationContract) -> Callable:
    methods: dict[str, Callable] = {
        "train_reference_occlusion": product_evidence._build_occlusion_explanation,
        "integrated_gradients_train_reference": product_evidence._build_integrated_gradients_explanation,
        "gradient_shap_train_background": product_evidence._build_gradient_shap_explanation,
        "permutation_shap_train_background": product_evidence._build_permutation_shap_explanation,
        "tree_shap_train_background": product_evidence._build_tree_shap_explanation,
    }
    try:
        return methods[contract.method]
    except KeyError as error:
        raise ValueError(f"No frozen product-native Quantus replay for {contract.method!r}") from error


def max_sensitivity_applicability(contract: ExplanationContract, target_run) -> tuple[str, str]:
    """Return component applicability without executing or treating an error as detection."""
    supported = {
        "train_reference_occlusion": {"logistic_regression", "decision_tree", "random_forest", "gradient_boosting", "flat_neuro_fuzzy"},
        "integrated_gradients_train_reference": {"flat_neuro_fuzzy"},
        "gradient_shap_train_background": {"flat_neuro_fuzzy"},
        "permutation_shap_train_background": {"logistic_regression"},
        "tree_shap_train_background": {"decision_tree", "random_forest", "gradient_boosting"},
    }
    if contract.method not in supported:
        return "NOT_AVAILABLE", "No frozen product-native explanation replay is registered."
    if target_run.model_kind not in supported[contract.method]:
        return "NOT_APPLICABLE", "The declared target run is incompatible with the persisted explainer replay route."
    if tuple(contract.sample) != tuple(target_run.feature_columns):
        return "NOT_APPLICABLE", "The persisted sample representation does not match the declared target feature order."
    return "APPLICABLE", "Frozen product-native replay route is compatible with the declared target run."


def faithfulness_applicability(contract: ExplanationContract, target_run) -> tuple[str, str]:
    if tuple(contract.sample) != tuple(target_run.feature_columns):
        return "NOT_APPLICABLE", "The persisted sample representation does not match the declared target feature order."
    return "APPLICABLE", "Frozen product-native probability replay supports the declared target run."


def component_applicability(contract: ExplanationContract, target_run) -> dict[str, dict[str, str]]:
    state, reason = faithfulness_applicability(contract, target_run)
    sensitivity_state, sensitivity_reason = max_sensitivity_applicability(contract, target_run)
    return {
        "faithfulness_correlation": {"state": state, "reason": reason},
        "max_sensitivity": {"state": sensitivity_state, "reason": sensitivity_reason},
    }


def _explain_batch(project_root: Path, run, contract: ExplanationContract, inputs: np.ndarray) -> np.ndarray:
    builder = _builder_for(contract)
    raw = _raw_from_normalized(run, np.asarray(inputs, dtype=float).reshape(len(inputs), -1))
    params = dict(contract.generation_parameters)
    cache_prefix = (str(Path(project_root).resolve()), str(run.run_id), contract.method, repr(sorted(params.items())))
    values: list[np.ndarray] = []
    for row in raw:
        key = (*cache_prefix, np.asarray(row, dtype=np.float64).tobytes())
        cached = _REPLAY_CACHE.get(key)
        if cached is not None:
            values.append(cached)
            continue
        sample = {feature: float(row[index]) for index, feature in enumerate(run.feature_columns)}
        if contract.method == "train_reference_occlusion":
            replay = builder(project_root, run.run_id, sample)
        elif contract.method == "integrated_gradients_train_reference":
            replay = builder(project_root, run.run_id, sample, steps=int(params["steps"]))
        elif contract.method == "gradient_shap_train_background":
            replay = builder(project_root, run.run_id, sample, background_count=int(params["background_count"]))
        elif contract.method == "permutation_shap_train_background":
            replay = builder(project_root, run.run_id, sample, background_count=int(params["background_count"]), max_evals=int(params["max_evals"]))
        else:
            replay = builder(project_root, run.run_id, sample, background_count=int(params.get("background_count", 32)), feature_perturbation=str(params["feature_perturbation"]))
        attribution = np.asarray([item.attribution for item in replay.attributions], dtype=float)
        _REPLAY_CACHE[key] = attribution
        values.append(attribution)
    return np.asarray(values, dtype=float).reshape(len(values), 1, -1)


@dataclass(frozen=True)
class QuantusMetricResult:
    metric_name: str
    state: str
    reason: str
    effective_seed: int
    value: float | None
    target_run_id: str


def evaluate_metric(project_root: Path, contract: ExplanationContract, *, clean_artifact_key: str, metric_name: str) -> QuantusMetricResult:
    """Run exactly one frozen metric against the contract-declared target run.

    ExplanationContract explanations represent the binary positive-class
    probability, so Quantus always evaluates output class ``1``. This is a
    contract-output convention, never a result-dependent class choice.
    """
    import quantus

    target_run = load_training_run(project_root, contract.run_id)
    states = component_applicability(contract, target_run)
    state = states[metric_name]
    seed = effective_seed(clean_artifact_key, metric_name)
    if state["state"] != "APPLICABLE":
        return QuantusMetricResult(metric_name, state["state"], state["reason"], seed, None, str(target_run.run_id))
    normalized = product_evidence._normalized_vector(target_run, contract.sample).astype(np.float32).reshape(1, 1, -1)
    attribution = np.asarray([item.attribution for item in contract.attributions], dtype=np.float32).reshape(1, 1, -1)
    model = _TargetAdapter(project_root, target_run).eval()
    target = np.asarray([1], dtype=int)
    try:
        with controlled_rng(seed):
            if metric_name == "faithfulness_correlation":
                metric = quantus.FaithfulnessCorrelation(nr_runs=10, subset_size=1, perturb_baseline="mean", return_aggregate=False, disable_warnings=True)
                values = metric(model=model, x_batch=normalized, y_batch=target, a_batch=attribution, softmax=False, channel_first=True)
            elif metric_name == "max_sensitivity":
                metric = quantus.MaxSensitivity(nr_samples=10, lower_bound=0.0, upper_bound=0.05, disable_warnings=True)
                values = metric(model=model, x_batch=normalized, y_batch=target, a_batch=attribution, softmax=False, channel_first=True,
                                explain_func=lambda *, model, inputs, targets, **_kwargs: _explain_batch(project_root, target_run, contract, inputs))
            else:
                raise ValueError(metric_name)
    except (AssertionError, ValueError, RuntimeError) as error:
        return QuantusMetricResult(metric_name, "NOT_AVAILABLE", f"Quantus route rejected this persisted attribution: {type(error).__name__}:{error}", seed, None, str(target_run.run_id))
    value = float(np.asarray(values, dtype=float).reshape(-1)[0])
    if not np.isfinite(value):
        return QuantusMetricResult(metric_name, "NOT_AVAILABLE", "Quantus returned a non-finite value under the frozen route.", seed, None, str(target_run.run_id))
    return QuantusMetricResult(metric_name, "APPLICABLE", "Frozen Quantus execution completed.", seed, value, str(target_run.run_id))
