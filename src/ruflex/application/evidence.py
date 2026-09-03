from __future__ import annotations

import json
import hashlib
import math
import os
import tempfile
from pathlib import Path
from uuid import UUID

import numpy as np
import torch

from ruflex.application.artifacts import ArtifactRef, ArtifactStore
from ruflex.application.datasets import load_dataset_frame
from ruflex.application.training import load_training_run
from ruflex.core.enums import NormalizationMode
from ruflex.data.datasets import DatasetConfig, NormalizationArtifact, TabularDataset
from ruflex.domain.evidence import ExplanationCheck, ExplanationCheckItem, ExplanationContract, FeatureAttribution
from ruflex.models.flat_nf.model import FlatNeuroFuzzyModel
from ruflex.models.specs import ShallowModelSpec
from ruflex.plugins import PluginDescriptor, PluginRegistry


class EvidenceError(RuntimeError):
    pass


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".evidence-", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _explanations_root(project_root: Path) -> Path:
    root = Path(project_root).resolve() / "evidence" / "explanations"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _checks_root(project_root: Path) -> Path:
    root = Path(project_root).resolve() / "evidence" / "explanation-checks"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _stable_identity(prefix: str, payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(encoded).hexdigest()}"


def _normalization(run) -> NormalizationArtifact:
    return NormalizationArtifact.from_dict(run.normalization)


def _reference_raw_values(run) -> dict[str, float]:
    normalization = _normalization(run)
    if normalization.mode.value == "standard" and normalization.center is not None:
        return dict(zip(run.feature_columns, map(float, normalization.center), strict=True))
    if normalization.mode.value == "minmax" and normalization.minimum is not None and normalization.maximum is not None:
        return {
            name: float((low + high) / 2.0)
            for name, low, high in zip(run.feature_columns, normalization.minimum, normalization.maximum, strict=True)
        }
    return {name: 0.0 for name in run.feature_columns}


def _normalized_vector(run, sample: dict[str, float]) -> np.ndarray:
    missing = [name for name in run.feature_columns if name not in sample]
    extra = sorted(set(sample) - set(run.feature_columns))
    if missing or extra:
        raise EvidenceError(f"Sample mismatch. Missing={missing or 'none'}; unexpected={extra or 'none'}.")
    raw = np.asarray([[float(sample[name]) for name in run.feature_columns]], dtype=float)
    if not np.all(np.isfinite(raw)):
        raise EvidenceError("Explanation sample values must be finite numbers.")
    return _normalization(run).transform_array(raw)


def _sigmoid(value: float) -> float:
    value = float(np.clip(value, -60.0, 60.0))
    return float(1.0 / (1.0 + math.exp(-value)))


def _tree_leaf(tree: dict, vector: np.ndarray) -> int:
    node = 0
    while int(tree["children_left"][node]) != -1:
        feature = int(tree["feature_index"][node])
        threshold = float(tree["threshold"][node])
        node = int(tree["children_left"][node]) if float(vector[feature]) <= threshold else int(tree["children_right"][node])
    return node


def _tree_output(tree: dict, vector: np.ndarray, *, task: str) -> float:
    node = _tree_leaf(tree, vector)
    values = np.asarray(tree["values"][node], dtype=float).reshape(-1)
    if task == "binary_classification":
        if len(values) < 2:
            return float(values[-1])
        total = float(values.sum())
        return 0.5 if total <= 0 else float(values[1] / total)
    return float(values[0])


def _artifact_payload(project_root: Path, sha256: str) -> dict:
    with ArtifactStore(project_root).open(ArtifactRef(sha256=sha256)) as handle:
        return json.loads(handle.read().decode("utf-8"))


def _predict_classical(project_root: Path, run, sample: dict[str, float]) -> float:
    vector = _normalized_vector(run, sample).reshape(-1)
    payload = _artifact_payload(project_root, run.model_artifact_sha256)
    if run.model_kind in {"logistic_regression", "linear_regression"}:
        raw = float(np.dot(np.asarray(payload["coefficients"], dtype=float), vector) + float(payload["intercept"]))
        return _sigmoid(raw) if run.task == "binary_classification" else raw
    if run.model_kind == "decision_tree":
        return _tree_output(payload["tree"], vector, task=run.task)
    if run.model_kind == "random_forest":
        predictions = [_tree_output(tree, vector, task=run.task) for tree in payload["trees"]]
        return float(np.mean(predictions))
    if run.model_kind == "gradient_boosting":
        initial = payload.get("initial_raw_prediction")
        if initial is None:
            raise EvidenceError("This legacy Gradient Boosting artifact predates reproducible ensemble inference evidence. Retrain the model revision first.")
        raw = float(initial) + float(payload["parameters"]["learning_rate"]) * sum(
            _tree_output(tree, vector, task="regression") for tree in payload["trees"]
        )
        return _sigmoid(raw) if run.task == "binary_classification" else raw
    raise EvidenceError(f"Safe declarative prediction is unavailable for model kind {run.model_kind!r}.")


def _load_anfis_model(project_root: Path, run) -> FlatNeuroFuzzyModel:
    spec = ShallowModelSpec.from_dict(run.model_spec)
    model = FlatNeuroFuzzyModel(spec)
    with ArtifactStore(project_root).open(ArtifactRef(sha256=run.model_artifact_sha256)) as handle:
        raw = handle.read()
    with tempfile.NamedTemporaryFile(prefix="ruflex-evidence-", suffix=".pt", delete=False) as temporary:
        temporary.write(raw)
        path = Path(temporary.name)
    try:
        model.load_bundle(path)
    finally:
        path.unlink(missing_ok=True)
    return model


def _predict_anfis(project_root: Path, run, sample: dict[str, float]) -> float:
    vector = _normalized_vector(run, sample)
    model = _load_anfis_model(project_root, run)
    prediction = float(np.asarray(model.predict(vector), dtype=float).reshape(-1)[0])
    return _sigmoid(prediction) if run.task == "binary_classification" else prediction


def _differentiable_output(model: FlatNeuroFuzzyModel, run, inputs: torch.Tensor) -> torch.Tensor:
    if model.backend_model is None:
        raise EvidenceError("The neuro-fuzzy bundle did not restore a differentiable backend model.")
    raw = model.backend_model(inputs).reshape(-1)
    return torch.sigmoid(raw) if run.task == "binary_classification" else raw


def _training_background_normalized(project_root: Path, run, *, maximum: int = 32) -> np.ndarray:
    frame = load_dataset_frame(project_root)
    split = TabularDataset.from_dataframe(frame).split(DatasetConfig(
        target_column=run.target,
        feature_columns=tuple(run.feature_columns),
        validation_fraction=run.split.validation_fraction,
        test_fraction=run.split.test_fraction,
        normalization=NormalizationMode.STANDARD,
        fill_missing="median",
        random_state=run.split.split_seed if run.split.split_seed is not None else run.seed,
    ))
    values = np.asarray(split.train_features, dtype=np.float32)
    if len(values) <= maximum:
        return values
    rng = np.random.default_rng(run.seed + 1907)
    return values[np.sort(rng.choice(len(values), size=maximum, replace=False))]


def predict_run_sample(project_root: Path, run_id: UUID, sample: dict[str, float]) -> float:
    run = load_training_run(project_root, run_id)
    if run.model_kind == "flat_neuro_fuzzy":
        return _predict_anfis(project_root, run, sample)
    return _predict_classical(project_root, run, sample)


def _predict_normalized_batch(project_root: Path, run, values: np.ndarray) -> np.ndarray:
    matrix = np.asarray(values, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    if matrix.shape[1] != len(run.feature_columns):
        raise EvidenceError("Explanation predictor received an incompatible feature matrix.")
    if run.model_kind == "flat_neuro_fuzzy":
        model = _load_anfis_model(project_root, run)
        raw = np.asarray(model.predict(matrix), dtype=float).reshape(-1)
        return 1.0 / (1.0 + np.exp(-np.clip(raw, -60.0, 60.0))) if run.task == "binary_classification" else raw
    payload = _artifact_payload(project_root, run.model_artifact_sha256)
    if run.model_kind in {"logistic_regression", "linear_regression"}:
        coefficients = np.asarray(payload["coefficients"], dtype=float).reshape(-1)
        raw = matrix @ coefficients + float(payload["intercept"])
        return 1.0 / (1.0 + np.exp(-np.clip(raw, -60.0, 60.0))) if run.task == "binary_classification" else raw
    if run.model_kind == "decision_tree":
        return np.asarray([_tree_output(payload["tree"], row, task=run.task) for row in matrix], dtype=float)
    if run.model_kind == "random_forest":
        return np.asarray([
            float(np.mean([_tree_output(tree, row, task=run.task) for tree in payload["trees"]]))
            for row in matrix
        ], dtype=float)
    if run.model_kind == "gradient_boosting":
        initial = payload.get("initial_raw_prediction")
        if initial is None:
            raise EvidenceError("This legacy Gradient Boosting artifact predates reproducible ensemble inference evidence. Retrain the model revision first.")
        raw_values = np.asarray([
            float(initial) + float(payload["parameters"]["learning_rate"]) * sum(
                _tree_output(tree, row, task="regression") for tree in payload["trees"]
            )
            for row in matrix
        ], dtype=float)
        return 1.0 / (1.0 + np.exp(-np.clip(raw_values, -60.0, 60.0))) if run.task == "binary_classification" else raw_values
    raise EvidenceError(f"SHAP prediction is unavailable for model kind {run.model_kind!r}.")


def _build_occlusion_explanation(project_root: Path, run_id: UUID, sample: dict[str, float]) -> ExplanationContract:
    run = load_training_run(project_root, run_id)
    if set(sample) != set(run.feature_columns):
        missing = sorted(set(run.feature_columns) - set(sample))
        extra = sorted(set(sample) - set(run.feature_columns))
        raise EvidenceError(f"Sample mismatch. Missing={missing or 'none'}; unexpected={extra or 'none'}.")
    prediction = predict_run_sample(project_root, run_id, sample)
    reference = _reference_raw_values(run)
    attributions: list[FeatureAttribution] = []
    for feature in run.feature_columns:
        occluded = dict(sample)
        occluded[feature] = reference[feature]
        occluded_prediction = predict_run_sample(project_root, run_id, occluded)
        attributions.append(FeatureAttribution(
            feature=feature,
            observed_value=float(sample[feature]),
            reference_value=float(reference[feature]),
            attribution=float(prediction - occluded_prediction),
            occluded_prediction=float(occluded_prediction),
        ))
    explanation = ExplanationContract(
        run_id=run.run_id,
        model_kind=run.model_kind,
        model_artifact_sha256=run.model_artifact_sha256,
        sample={name: float(sample[name]) for name in run.feature_columns},
        target=run.target,
        generation_parameters={"route": "deterministic_exact"},
        prediction=prediction,
        reference_definition="Per-feature train-derived preprocessing reference (training mean for standardization).",
        assumptions=[
            "The persisted model artifact and preprocessing identity match the selected TrainingRun.",
            "One feature is replaced at a time while all other observed feature values remain fixed.",
        ],
        limitations=[
            "Occlusion effects need not add up to the prediction.",
            "Correlated or constrained features can make one-at-a-time replacement unrealistic.",
            "The attribution is not causal evidence.",
        ],
        attributions=attributions,
    )
    return explanation


def _build_integrated_gradients_explanation(
    project_root: Path,
    run_id: UUID,
    sample: dict[str, float],
    *,
    steps: int = 64,
) -> ExplanationContract:
    run = load_training_run(project_root, run_id)
    if run.model_kind != "flat_neuro_fuzzy":
        raise EvidenceError("Integrated Gradients requires a model with gradient access; this Product V1 implementation supports ANFIS / Flat neuro-fuzzy runs.")
    if steps < 8 or steps > 512:
        raise EvidenceError("Integrated Gradients steps must lie between 8 and 512.")
    _normalized_vector(run, sample)  # validates feature identity and finite input
    reference = _reference_raw_values(run)
    x_np = _normalized_vector(run, sample).astype(np.float32)
    baseline_np = _normalized_vector(run, reference).astype(np.float32)
    model = _load_anfis_model(project_root, run)
    x = torch.as_tensor(x_np, dtype=torch.float32)
    baseline = torch.as_tensor(baseline_np, dtype=torch.float32)
    delta = x - baseline
    gradients: list[torch.Tensor] = []
    for alpha in torch.linspace(0.0, 1.0, steps + 1):
        point = (baseline + alpha * delta).detach().clone().requires_grad_(True)
        output = _differentiable_output(model, run, point)[0]
        gradient = torch.autograd.grad(output, point, retain_graph=False, create_graph=False)[0]
        gradients.append(gradient.detach())
    stacked = torch.stack(gradients, dim=0)
    # Trapezoidal integration along the straight baseline→sample path.
    average_gradient = ((stacked[:-1] + stacked[1:]) / 2.0).mean(dim=0)
    attribution_values = (delta * average_gradient).detach().cpu().numpy().reshape(-1)
    with torch.no_grad():
        prediction = float(_differentiable_output(model, run, x)[0].cpu())
        base_value = float(_differentiable_output(model, run, baseline)[0].cpu())
    reconstructed = base_value + float(np.sum(attribution_values))
    attributions = [
        FeatureAttribution(
            feature=feature,
            observed_value=float(sample[feature]),
            reference_value=float(reference[feature]),
            attribution=float(attribution_values[index]),
        )
        for index, feature in enumerate(run.feature_columns)
    ]
    return ExplanationContract(
        run_id=run.run_id,
        model_kind=run.model_kind,
        model_artifact_sha256=run.model_artifact_sha256,
        sample={name: float(sample[name]) for name in run.feature_columns},
        target=run.target,
        generation_parameters={"steps": steps},
        family="integrated_gradients",
        method="integrated_gradients_train_reference",
        prediction=prediction,
        base_value=base_value,
        completeness_error=abs(prediction - reconstructed),
        reference_definition="Single train-derived preprocessing reference; straight-line path to the observed sample.",
        assumptions=[
            "The restored ANFIS backend is differentiable with respect to the normalized input features.",
            f"Attributions numerically integrate {steps} path intervals from the train-derived reference to the sample.",
        ],
        limitations=[
            "Integrated Gradients depends on the chosen baseline.",
            "Attribution is not causal evidence and does not quantify predictive uncertainty.",
        ],
        attributions=attributions,
        scientific_note="Integrated Gradients is a gradient-based post-hoc attribution. RuFLEX reports its baseline and numerical completeness error; it is not an exact fuzzy-rule trace.",
    )


def _build_gradient_shap_explanation(
    project_root: Path,
    run_id: UUID,
    sample: dict[str, float],
    *,
    background_count: int = 24,
) -> ExplanationContract:
    run = load_training_run(project_root, run_id)
    if run.model_kind != "flat_neuro_fuzzy":
        raise EvidenceError("GradientSHAP requires gradient access; this Product V1 implementation supports ANFIS / Flat neuro-fuzzy runs.")
    _normalized_vector(run, sample)
    model = _load_anfis_model(project_root, run)
    x_np = _normalized_vector(run, sample).astype(np.float32)
    background = _training_background_normalized(project_root, run, maximum=max(8, min(background_count, 64)))
    if len(background) == 0:
        raise EvidenceError("GradientSHAP requires at least one train-partition background sample.")
    x = torch.as_tensor(x_np, dtype=torch.float32)
    rng = np.random.default_rng(run.seed + 2701)
    contributions: list[np.ndarray] = []
    base_values: list[float] = []
    for baseline_np in background:
        baseline = torch.as_tensor(baseline_np.reshape(1, -1), dtype=torch.float32)
        alpha = float(rng.uniform(0.0, 1.0))
        point = (baseline + alpha * (x - baseline)).detach().clone().requires_grad_(True)
        output = _differentiable_output(model, run, point)[0]
        gradient = torch.autograd.grad(output, point, retain_graph=False, create_graph=False)[0]
        contributions.append(((x - baseline) * gradient).detach().cpu().numpy().reshape(-1))
        with torch.no_grad():
            base_values.append(float(_differentiable_output(model, run, baseline)[0].cpu()))
    attribution_values = np.mean(np.stack(contributions, axis=0), axis=0)
    base_value = float(np.mean(base_values))
    with torch.no_grad():
        prediction = float(_differentiable_output(model, run, x)[0].cpu())
    reference = _reference_raw_values(run)
    reconstructed = base_value + float(np.sum(attribution_values))
    attributions = [
        FeatureAttribution(
            feature=feature,
            observed_value=float(sample[feature]),
            reference_value=float(reference[feature]),
            attribution=float(attribution_values[index]),
        )
        for index, feature in enumerate(run.feature_columns)
    ]
    return ExplanationContract(
        run_id=run.run_id,
        model_kind=run.model_kind,
        model_artifact_sha256=run.model_artifact_sha256,
        sample={name: float(sample[name]) for name in run.feature_columns},
        target=run.target,
        generation_parameters={"background_count": background_count},
        family="gradient_shap",
        method="gradient_shap_train_background",
        prediction=prediction,
        base_value=base_value,
        completeness_error=abs(prediction - reconstructed),
        reference_definition=f"Expected-gradient background from {len(background)} train-partition samples selected deterministically from run seed {run.seed}.",
        assumptions=[
            "Only train-partition samples are used as GradientSHAP background.",
            "The restored ANFIS backend is differentiable with respect to inputs.",
        ],
        limitations=[
            "This finite expected-gradients estimate is approximate and can vary with background choice.",
            "GradientSHAP attribution is not causal evidence and is separate from uncertainty estimation.",
        ],
        attributions=attributions,
        scientific_note="GradientSHAP is reported as approximate gradient-based post-hoc attribution using a deterministic train-only background. It is not an exact computation trace.",
    )


def _tree_shap_tree(tree: dict, *, task: str, scaling: float = 1.0, raw_tree_output: bool = False) -> dict:
    """Translate a safe RuFLEX declarative tree to SHAP's in-memory tree schema.

    This does not unpickle or execute user-provided code.  Classification tree
    counts are converted to class probabilities before SHAP aggregation; raw
    regression-tree outputs are retained for gradient boosting.
    """
    children_left = np.asarray(tree["children_left"], dtype=np.int32)
    children_right = np.asarray(tree["children_right"], dtype=np.int32)
    features = np.asarray(tree["feature_index"], dtype=np.int32)
    thresholds = np.asarray(tree["threshold"], dtype=np.float64)
    values = np.asarray(tree["values"], dtype=np.float64)
    if values.ndim == 1:
        values = values[:, None]
    if task == "binary_classification" and not raw_tree_output:
        totals = values.sum(axis=1, keepdims=True)
        values = np.divide(values, totals, out=np.zeros_like(values), where=totals > 0)
    elif values.shape[1] != 1:
        values = values[:, :1]
    values = values * float(scaling)
    weights = np.asarray(tree.get("samples", np.ones(len(children_left))), dtype=np.float64)
    return {
        "children_left": children_left,
        "children_right": children_right,
        "children_default": children_left.copy(),
        "features": features,
        "thresholds": thresholds,
        "values": values,
        "node_sample_weight": weights,
    }


def _gradient_boosting_raw_batch(payload: dict, values: np.ndarray) -> np.ndarray:
    matrix = np.asarray(values, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    initial = payload.get("initial_raw_prediction")
    if initial is None:
        raise EvidenceError(
            "This legacy Gradient Boosting artifact predates reproducible ensemble inference evidence. Retrain the model revision first."
        )
    learning_rate = float(payload["parameters"]["learning_rate"])
    return np.asarray([
        float(initial) + learning_rate * sum(_tree_output(tree, row, task="regression") for tree in payload["trees"])
        for row in matrix
    ], dtype=float)


def _build_tree_shap_explanation(
    project_root: Path,
    run_id: UUID,
    sample: dict[str, float],
    *,
    background_count: int = 32,
    feature_perturbation: str = "tree_path_dependent",
) -> ExplanationContract:
    """Compute model-specific TreeSHAP from RuFLEX declarative tree artifacts.

    TreeSHAP is still a POST-HOC ATTRIBUTION object.  It must not be confused
    with the exact execution path of a Decision Tree or a constituent path of
    an ensemble.
    """
    try:
        import shap
    except ImportError as error:
        raise EvidenceError("TreeSHAP requires shap>=0.50 from the RuFLEX project dependencies.") from error

    run = load_training_run(project_root, run_id)
    if run.model_kind not in {"decision_tree", "random_forest", "gradient_boosting"}:
        raise EvidenceError("TreeSHAP is available only for persisted tree-model artifacts.")
    x = _normalized_vector(run, sample).astype(float)
    if feature_perturbation != "tree_path_dependent":
        raise EvidenceError(
            "Declarative TreeSHAP supports only tree_path_dependent perturbation. "
            "The interventional multi-output route does not preserve the persisted classifier output."
        )
    payload = _artifact_payload(project_root, run.model_artifact_sha256)

    if run.model_kind == "decision_tree":
        trees = [_tree_shap_tree(payload["tree"], task=run.task)]
        base_offset = np.zeros(2, dtype=float) if run.task == "binary_classification" else 0.0
        tree_output = "probability" if run.task == "binary_classification" else "raw_value"
        objective = "binary_crossentropy" if run.task == "binary_classification" else "squared_error"
        prediction = float(_predict_normalized_batch(project_root, run, x)[0])
        output_space = "probability" if run.task == "binary_classification" else "prediction"
    elif run.model_kind == "random_forest":
        raw_trees = payload.get("trees") or []
        if not raw_trees:
            raise EvidenceError("Random Forest artifact contains no constituent trees.")
        scale = 1.0 / len(raw_trees)
        trees = [_tree_shap_tree(tree, task=run.task, scaling=scale) for tree in raw_trees]
        base_offset = np.zeros(2, dtype=float) if run.task == "binary_classification" else 0.0
        tree_output = "probability" if run.task == "binary_classification" else "raw_value"
        objective = "binary_crossentropy" if run.task == "binary_classification" else "squared_error"
        prediction = float(_predict_normalized_batch(project_root, run, x)[0])
        output_space = "probability" if run.task == "binary_classification" else "prediction"
    else:
        learning_rate = float(payload["parameters"]["learning_rate"])
        trees = [
            _tree_shap_tree(tree, task="regression", scaling=learning_rate, raw_tree_output=True)
            for tree in payload.get("trees", [])
        ]
        if not trees:
            raise EvidenceError("Gradient Boosting artifact contains no constituent trees.")
        base_offset = float(payload.get("initial_raw_prediction"))
        tree_output = "raw_value"
        objective = "binary_crossentropy" if run.task == "binary_classification" else "squared_error"
        prediction = float(_gradient_boosting_raw_batch(payload, x)[0])
        output_space = "raw_score" if run.task == "binary_classification" else "prediction"

    model = {
        "trees": trees,
        "base_offset": base_offset,
        "tree_output": tree_output,
        "objective": objective,
        "internal_dtype": np.float64,
        "input_dtype": np.float64,
    }
    explainer = shap.TreeExplainer(
        model,
        feature_perturbation=feature_perturbation,
        model_output="raw",
    )
    result = explainer(x, check_additivity=True)
    result_values = np.asarray(result.values, dtype=float)
    result_base = np.asarray(result.base_values, dtype=float)
    if run.task == "binary_classification" and run.model_kind in {"decision_tree", "random_forest"}:
        # The declarative classifier tree stores [P(class 0), P(class 1)].
        values = result_values[0, :, 1]
        base_value = float(result_base.reshape(-1)[1])
    else:
        values = result_values.reshape(1, len(run.feature_columns), -1)[0, :, 0]
        base_value = float(result_base.reshape(-1)[0])

    completeness_error = abs(prediction - (base_value + float(values.sum())))
    reference = _reference_raw_values(run)
    attributions = [
        FeatureAttribution(
            feature=feature,
            observed_value=float(sample[feature]),
            reference_value=float(reference[feature]),
            attribution=float(values[index]),
        )
        for index, feature in enumerate(run.feature_columns)
    ]
    if run.model_kind == "gradient_boosting" and run.task == "binary_classification":
        output_note = (
            "For binary Gradient Boosting, TreeSHAP explains the additive raw decision score before the sigmoid probability transform. "
            "This preserves exact additive attribution in the model's tree-additive output space."
        )
    else:
        output_note = (
            "TreeSHAP explains the persisted model output in probability space for binary Decision Tree/Random Forest models "
            "and prediction space for regression models."
        )
    return ExplanationContract(
        run_id=run.run_id,
        model_kind=run.model_kind,
        model_artifact_sha256=run.model_artifact_sha256,
        sample={name: float(sample[name]) for name in run.feature_columns},
        target=run.target,
        generation_parameters={"feature_perturbation": feature_perturbation},
        family="tree_shap",
        method="tree_shap_train_background",
        prediction=prediction,
        output_space=output_space,
        base_value=base_value,
        completeness_error=completeness_error,
        reference_definition=(
            "TreeSHAP uses the persisted train-partition tree-node frequencies with tree-path-dependent perturbation. "
            "The displayed per-feature reference value is the train-derived normalization center and is not a finite SHAP background subset."
        ),
        assumptions=[
            "The persisted declarative tree artifact exactly represents the trained tree ensemble used for inference.",
            "Tree-path-dependent expectations use the persisted training-node frequencies without reading validation or test rows.",
        ],
        limitations=[
            "TreeSHAP is an additive post-hoc attribution, not a causal effect and not uncertainty estimation.",
            "A Decision Tree exact execution path is a separate structural evidence object from TreeSHAP attribution.",
            "For ensembles, no single constituent tree path is presented as an exact explanation of the ensemble prediction.",
            output_note,
        ],
        attributions=attributions,
        scientific_note=(
            "TreeSHAP is stored as POST-HOC ATTRIBUTION with a train-only background and numerical additivity check. "
            "It is not the exact execution trace. " + output_note
        ),
    )


def create_tree_shap_explanation(
    project_root: Path,
    run_id: UUID,
    sample: dict[str, float],
    *,
    background_count: int = 32,
    feature_perturbation: str = "tree_path_dependent",
) -> ExplanationContract:
    return _persist_explanation(project_root, _build_tree_shap_explanation(
        project_root,
        run_id,
        sample,
        background_count=background_count,
        feature_perturbation=feature_perturbation,
    ))


def _build_permutation_shap_explanation(
    project_root: Path,
    run_id: UUID,
    sample: dict[str, float],
    *,
    background_count: int = 24,
    max_evals: int | None = None,
) -> ExplanationContract:
    try:
        import shap
    except ImportError as error:
        raise EvidenceError("SHAP is not installed. Install the RuFLEX project dependencies including shap>=0.50.") from error
    run = load_training_run(project_root, run_id)
    x = _normalized_vector(run, sample).astype(float)
    background = _training_background_normalized(project_root, run, maximum=max(8, min(background_count, 64))).astype(float)
    if len(background) == 0:
        raise EvidenceError("SHAP requires a non-empty train-partition background.")
    predictor = lambda matrix: _predict_normalized_batch(project_root, run, np.asarray(matrix, dtype=float))
    explainer = shap.Explainer(
        predictor,
        background,
        feature_names=list(run.feature_columns),
        algorithm="permutation",
        seed=run.seed,
    )
    max_evals = max_evals if max_evals is not None else max(2 * len(run.feature_columns) + 1, 12 * len(run.feature_columns) + 1)
    if max_evals < 2 * len(run.feature_columns) + 1:
        raise EvidenceError("Permutation SHAP max_evals must support every feature.")
    result = explainer(x, max_evals=max_evals, silent=True)
    values = np.asarray(result.values, dtype=float).reshape(-1)
    base_value = float(np.asarray(result.base_values, dtype=float).reshape(-1)[0])
    prediction = float(predictor(x)[0])
    reference = _reference_raw_values(run)
    completeness_error = abs(prediction - (base_value + float(values.sum())))
    attributions = [
        FeatureAttribution(
            feature=feature,
            observed_value=float(sample[feature]),
            reference_value=float(reference[feature]),
            attribution=float(values[index]),
        )
        for index, feature in enumerate(run.feature_columns)
    ]
    return ExplanationContract(
        run_id=run.run_id,
        model_kind=run.model_kind,
        model_artifact_sha256=run.model_artifact_sha256,
        sample={name: float(sample[name]) for name in run.feature_columns},
        target=run.target,
        generation_parameters={"background_count": background_count, "max_evals": max_evals},
        family="shap",
        method="permutation_shap_train_background",
        prediction=prediction,
        base_value=base_value,
        completeness_error=completeness_error,
        reference_definition=f"Permutation SHAP background uses {len(background)} deterministic train-partition samples in the persisted preprocessing representation.",
        assumptions=[
            "The prediction callable exactly replays the persisted RuFLEX model artifact and preprocessing semantics.",
            "Only the training partition is used as the SHAP background distribution.",
        ],
        limitations=[
            "Permutation SHAP is model-agnostic and can be slower than model-specific TreeSHAP.",
            "Feature dependence in the background distribution can affect attribution interpretation.",
            "SHAP values are post-hoc associations, not causal effects or uncertainty estimates.",
        ],
        attributions=attributions,
        scientific_note="Permutation SHAP is stored as POST-HOC ATTRIBUTION with an explicit train-only background and numerical additivity check. It is not an exact model execution trace.",
    )


def create_permutation_shap_explanation(project_root: Path, run_id: UUID, sample: dict[str, float], *, background_count: int = 24, max_evals: int | None = None) -> ExplanationContract:
    return _persist_explanation(project_root, _build_permutation_shap_explanation(project_root, run_id, sample, background_count=background_count, max_evals=max_evals))


def _persist_explanation(project_root: Path, explanation: ExplanationContract) -> ExplanationContract:
    run = load_training_run(project_root, explanation.run_id)
    explanation = explanation.model_copy(update={
        "preprocessing_identity": explanation.preprocessing_identity or _stable_identity("preprocessing", run.normalization),
        "preprocessing_artifact_sha256": explanation.preprocessing_artifact_sha256 or run.preprocessing_artifact_sha256,
        "feature_order_identity": explanation.feature_order_identity or _stable_identity("feature-order", list(run.feature_columns)),
        "sample_identity": explanation.sample_identity or _stable_identity(
            "explanation-sample",
            {"run_id": str(run.run_id), "sample": explanation.sample, "target": explanation.target},
        ),
        "reference_identity": explanation.reference_identity or _stable_identity(
            "explanation-reference",
            {"run_id": str(run.run_id), "method": explanation.method, "reference_definition": explanation.reference_definition},
        ),
    })
    destination = _explanations_root(project_root) / f"{explanation.explanation_id}.json"
    _atomic_write_text(destination, explanation.model_dump_json(indent=2))
    _atomic_write_text(_explanations_root(project_root) / "active-explanation.json", json.dumps({"explanation_id": str(explanation.explanation_id)}, indent=2))
    return explanation


def create_integrated_gradients_explanation(project_root: Path, run_id: UUID, sample: dict[str, float], *, steps: int = 64) -> ExplanationContract:
    return _persist_explanation(project_root, _build_integrated_gradients_explanation(project_root, run_id, sample, steps=steps))


def create_gradient_shap_explanation(project_root: Path, run_id: UUID, sample: dict[str, float], *, background_count: int = 24) -> ExplanationContract:
    return _persist_explanation(project_root, _build_gradient_shap_explanation(project_root, run_id, sample, background_count=background_count))


def create_occlusion_explanation(project_root: Path, run_id: UUID, sample: dict[str, float]) -> ExplanationContract:
    return _persist_explanation(project_root, _build_occlusion_explanation(project_root, run_id, sample))


def load_explanation(project_root: Path, explanation_id: UUID) -> ExplanationContract:
    return ExplanationContract.model_validate_json((_explanations_root(project_root) / f"{explanation_id}.json").read_text(encoding="utf-8"))


def load_latest_explanation(project_root: Path) -> ExplanationContract:
    pointer = json.loads((_explanations_root(project_root) / "active-explanation.json").read_text(encoding="utf-8"))
    return load_explanation(project_root, UUID(pointer["explanation_id"]))


class NativeExplanationValidatorAdapter:
    """Product-native validator with explicit applicability and provenance."""

    key = "native_explanation_validator"
    version = "1"

    def applicability(self, explanation: ExplanationContract) -> tuple[str, str | None]:
        if explanation.exactness != "post_hoc":
            return "NOT_APPLICABLE", "Native post-hoc checks require a post-hoc ExplanationContract."
        return "APPLICABLE", None

    def validate(self, project_root: Path, explanation_id: UUID) -> ExplanationCheck:
        return _native_check_explanation(project_root, explanation_id, validator_key=self.key)


_validator_plugins = PluginRegistry()
_validator_plugins.register(
    PluginDescriptor(
        key=NativeExplanationValidatorAdapter.key,
        version=NativeExplanationValidatorAdapter.version,
        kind="explanation_validator",
        capabilities={"provenance_identity": True, "replay_integrity": True, "quantitative_quality": True},
        config_schema={"type": "object", "additionalProperties": False},
        input_schema={"explanation_id": "UUID", "project_root": "canonical_project_root"},
        output_schema={"ExplanationCheck": "schema_version=2"},
    ),
    NativeExplanationValidatorAdapter(),
)


def list_explanation_validator_plugins() -> list[PluginDescriptor]:
    """Read-only descriptor inventory for the Studio and SDK boundary."""

    return _validator_plugins.list_descriptors()


def check_explanation(project_root: Path, explanation_id: UUID) -> ExplanationCheck:
    """Run the registered product-native validator through the adapter boundary."""

    validator = _validator_plugins.implementation("native_explanation_validator")
    return validator.validate(project_root, explanation_id)  # type: ignore[union-attr]


def _native_check_explanation(project_root: Path, explanation_id: UUID, *, validator_key: str) -> ExplanationCheck:
    explanation = load_explanation(project_root, explanation_id)
    run = load_training_run(project_root, explanation.run_id)
    checks: list[ExplanationCheckItem] = []
    checks.append(ExplanationCheckItem(
        name="model_identity",
        status="PASS" if run.model_artifact_sha256 == explanation.model_artifact_sha256 else "FAIL",
        detail="Explanation artifact hash matches its TrainingRun." if run.model_artifact_sha256 == explanation.model_artifact_sha256 else "Model artifact identity changed.",
    ))
    expected_preprocessing = _stable_identity("preprocessing", run.normalization)
    checks.append(ExplanationCheckItem(
        name="preprocessing_identity",
        status="WARN" if explanation.preprocessing_identity is None else ("PASS" if explanation.preprocessing_identity == expected_preprocessing else "FAIL"),
        detail=(
            "Legacy explanation predates persisted preprocessing identity." if explanation.preprocessing_identity is None
            else "Persisted preprocessing identity matches the TrainingRun." if explanation.preprocessing_identity == expected_preprocessing
            else "Persisted preprocessing identity does not match the TrainingRun."
        ),
    ))
    checks.append(ExplanationCheckItem(
        name="preprocessing_artifact",
        status="WARN" if explanation.preprocessing_artifact_sha256 is None else ("PASS" if explanation.preprocessing_artifact_sha256 == run.preprocessing_artifact_sha256 else "FAIL"),
        detail=(
            "Legacy explanation predates the preprocessing artifact binding." if explanation.preprocessing_artifact_sha256 is None
            else "Persisted preprocessing artifact matches the TrainingRun." if explanation.preprocessing_artifact_sha256 == run.preprocessing_artifact_sha256
            else "Persisted preprocessing artifact does not match the TrainingRun."
        ),
    ))
    expected_feature_order = _stable_identity("feature-order", list(run.feature_columns))
    checks.append(ExplanationCheckItem(
        name="feature_order_identity",
        status="WARN" if explanation.feature_order_identity is None else ("PASS" if explanation.feature_order_identity == expected_feature_order else "FAIL"),
        detail=(
            "Legacy explanation predates persisted feature-order identity." if explanation.feature_order_identity is None
            else "Persisted feature order matches the TrainingRun." if explanation.feature_order_identity == expected_feature_order
            else "Persisted feature order does not match the TrainingRun."
        ),
    ))
    expected_sample = _stable_identity(
        "explanation-sample",
        {"run_id": str(run.run_id), "sample": explanation.sample, "target": explanation.target},
    )
    checks.append(ExplanationCheckItem(
        name="sample_target_identity",
        status="WARN" if explanation.sample_identity is None else ("PASS" if explanation.sample_identity == expected_sample and explanation.target == run.target else "FAIL"),
        detail=(
            "Legacy explanation predates persisted sample identity." if explanation.sample_identity is None
            else "Sample and target identity match the persisted explanation contract." if explanation.sample_identity == expected_sample and explanation.target == run.target
            else "Sample/target identity no longer matches the TrainingRun contract."
        ),
    ))
    expected_reference = _stable_identity(
        "explanation-reference",
        {"run_id": str(run.run_id), "method": explanation.method, "reference_definition": explanation.reference_definition},
    )
    checks.append(ExplanationCheckItem(
        name="reference_identity",
        status="WARN" if explanation.reference_identity is None else ("PASS" if explanation.reference_identity == expected_reference else "FAIL"),
        detail=(
            "Legacy explanation predates persisted reference identity." if explanation.reference_identity is None
            else "Reference/background declaration is unchanged." if explanation.reference_identity == expected_reference
            else "Reference/background declaration changed after the explanation was persisted."
        ),
    ))
    # A contract whose run/model binding already failed must not attempt a
    # method-specific replay on an incompatible model.  Such a replay could
    # turn a correctly localized provenance failure into an implementation
    # exception (for example Integrated Gradients against a tree run).
    identity_failed = any(item.status == "FAIL" for item in checks)
    if identity_failed:
        checks.append(ExplanationCheckItem(
            name="repeatability", status="N/A",
            detail="Replay was intentionally not attempted because required persisted identity/provenance checks failed.",
        ))
    else:
        params = explanation.generation_parameters
        if explanation.method == "train_reference_occlusion":
            replay = _build_occlusion_explanation(project_root, explanation.run_id, explanation.sample)
        elif explanation.method == "integrated_gradients_train_reference":
            replay = _build_integrated_gradients_explanation(project_root, explanation.run_id, explanation.sample, steps=int(params.get("steps", 64)))
        elif explanation.method == "gradient_shap_train_background":
            replay = _build_gradient_shap_explanation(project_root, explanation.run_id, explanation.sample, background_count=int(params.get("background_count", 24)))
        elif explanation.method == "permutation_shap_train_background":
            replay = _build_permutation_shap_explanation(project_root, explanation.run_id, explanation.sample, background_count=int(params.get("background_count", 24)), max_evals=int(params["max_evals"]) if "max_evals" in params else None)
        elif explanation.method == "tree_shap_train_background":
            replay = _build_tree_shap_explanation(
                project_root,
                explanation.run_id,
                explanation.sample,
                background_count=int(params.get("background_count", 32)),
                feature_perturbation=str(params.get("feature_perturbation", "tree_path_dependent")),
            )
        else:
            raise EvidenceError(f"No validation replay is registered for explanation method {explanation.method!r}.")
        same_prediction = math.isclose(replay.prediction, explanation.prediction, rel_tol=1e-7, abs_tol=1e-7)
        replay_by_feature = {item.feature: item.attribution for item in replay.attributions}
        same_attributions = all(
            feature in replay_by_feature and math.isclose(item.attribution, replay_by_feature[feature], rel_tol=1e-8, abs_tol=1e-8)
            for feature, item in ((item.feature, item) for item in explanation.attributions)
        )
        checks.append(ExplanationCheckItem(
            name="repeatability",
            status="PASS" if same_prediction and same_attributions else "FAIL",
            detail=f"Repeated deterministic {explanation.family} computation reproduces prediction and feature effects." if same_prediction and same_attributions else f"Repeated {explanation.family} computation did not reproduce the stored explanation.",
        ))
    if explanation.completeness_error is None:
        checks.append(ExplanationCheckItem(
            name="additivity",
            status="N/A",
            detail="This explanation family does not make an additive completeness claim.",
        ))
    else:
        tolerance = 5e-5 if explanation.family == "tree_shap" else (5e-3 if explanation.family in {"integrated_gradients", "shap"} else 5e-2)
        checks.append(ExplanationCheckItem(
            name="numerical_completeness",
            status="PASS" if explanation.completeness_error <= tolerance else "WARN",
            detail=f"|prediction - (base + sum attributions)| = {explanation.completeness_error:.6g}; tolerance {tolerance:.6g} for {explanation.family}.",
        ))
    checks.append(ExplanationCheckItem(
        name="causal_validity",
        status="N/A",
        detail=f"No causal validity claim is implied by post-hoc {explanation.family} attribution.",
    ))
    if any(item.status == "FAIL" for item in checks):
        status = "FAILED"
    elif any(item.status == "WARN" for item in checks):
        status = "WARNING"
    else:
        status = "PASSED_AVAILABLE_CHECKS"
    categories = {
        "repeatability": "replay_integrity",
        "additivity": "quantitative_quality",
        "numerical_completeness": "quantitative_quality",
        "causal_validity": "claim_boundary",
    }
    checks = [item.model_copy(update={"category": categories.get(item.name, "provenance_identity"), "validator_key": validator_key}) for item in checks]
    result = ExplanationCheck(schema_version=2, explanation_id=explanation.explanation_id, run_id=explanation.run_id, status=status, checks=checks)
    _atomic_write_text(_checks_root(project_root) / f"{result.check_id}.json", result.model_dump_json(indent=2))
    _atomic_write_text(_checks_root(project_root) / "active-check.json", json.dumps({"check_id": str(result.check_id)}, indent=2))
    return result


def load_explanation_check(project_root: Path, check_id: UUID) -> ExplanationCheck:
    return ExplanationCheck.model_validate_json((_checks_root(project_root) / f"{check_id}.json").read_text(encoding="utf-8"))


def load_latest_explanation_check(project_root: Path) -> ExplanationCheck:
    pointer = json.loads((_checks_root(project_root) / "active-check.json").read_text(encoding="utf-8"))
    return load_explanation_check(project_root, UUID(pointer["check_id"]))
