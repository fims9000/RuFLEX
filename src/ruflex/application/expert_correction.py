from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from uuid import UUID

import numpy as np
import pandas as pd

from ruflex.application.datasets import load_dataset_contract, load_dataset_frame
from ruflex.application.fis import FISError, evaluate_fis, load_fis, persist_fis
from ruflex.core.enums import NormalizationMode
from ruflex.data.datasets import DatasetConfig, TabularDataset
from ruflex.domain.expert_correction import ExpertCorrectionResult, ExpertCorrectionRevision
from ruflex.domain.fis import FISSpec, SugenoConsequent


class ExpertCorrectionError(RuntimeError):
    pass


def _root(project_root: Path) -> Path:
    root = Path(project_root).resolve() / "analyses" / "expert-corrections"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".expert-correction-", suffix=".json", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _input_mapping(spec: FISSpec, frame: pd.DataFrame) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for variable in spec.inputs:
        column = variable.dataset_feature or variable.name
        if column not in frame.columns:
            raise ExpertCorrectionError(
                f"FIS input {variable.name!r} is not mapped to an available dataset column. "
                "Set dataset_feature or use the dataset column as the variable name."
            )
        if not pd.api.types.is_numeric_dtype(frame[column].dropna()):
            raise ExpertCorrectionError(f"Expert correction requires numeric input column {column!r}.")
        mapping[variable.name] = column
    return mapping


def _current_consequent_value(spec: FISSpec, rule_index: int, inputs: dict[str, float]) -> float:
    consequent = spec.rules[rule_index].sugeno_consequent
    if consequent is None:
        raise ExpertCorrectionError("Every Sugeno rule must have a consequent before correction.")
    if consequent.kind == "constant":
        assert consequent.constant is not None
        return float(consequent.constant)
    return float(consequent.intercept + sum(float(coefficient) * float(inputs[name]) for name, coefficient in consequent.coefficients.items()))


def _predict_rows(spec: FISSpec, rows: list[dict[str, float]]) -> np.ndarray:
    values: list[float] = []
    for row in rows:
        try:
            values.append(float(evaluate_fis(spec, row).output))
        except FISError as error:
            raise ExpertCorrectionError(f"FIS could not evaluate a TRAIN row during correction: {error}") from error
    return np.asarray(values, dtype=float)


def refit_sugeno_consequents(
    project_root: Path,
    *,
    locked_rule_ids: list[UUID] | None = None,
    seed: int = 42,
    validation_fraction: float = 0.2,
    test_fraction: float = 0.2,
    source_explanation_id: UUID | None = None,
) -> ExpertCorrectionResult:
    """Refit unlocked Sugeno consequents on TRAIN while preserving expert structure.

    The function intentionally does not tune membership functions, antecedents,
    rule weights, operators, validation performance, or final-test performance.
    This is a bounded correction mechanism rather than an unconstrained ANFIS
    retraining shortcut.
    """
    spec = load_fis(project_root)
    if spec.system_type != "sugeno":
        raise ExpertCorrectionError("Expert consequent refit is currently available only for a Type-1 Sugeno FIS.")
    source_hash = spec.semantic_hash
    if not source_hash:
        raise ExpertCorrectionError("The source FIS has no semantic hash.")
    if source_explanation_id is not None:
        # A provenance edge must never point at an invented evidence object.
        # The explanation may come from another compatible model, but it must
        # exist in this project if it is cited as the motivation for correction.
        from ruflex.application.evidence import load_explanation

        try:
            load_explanation(project_root, source_explanation_id)
        except (FileNotFoundError, OSError, ValueError) as error:
            raise ExpertCorrectionError(
                f"Source explanation does not exist in this project: {source_explanation_id}"
            ) from error

    frame = load_dataset_frame(project_root)
    contract = load_dataset_contract(project_root)
    if contract.target not in frame.columns:
        raise ExpertCorrectionError(f"Dataset target {contract.target!r} is unavailable.")
    if not pd.api.types.is_numeric_dtype(frame[contract.target].dropna()):
        raise ExpertCorrectionError("Expert correction requires a numeric target.")
    mapping = _input_mapping(spec, frame)
    feature_columns = tuple(dict.fromkeys(mapping.values()))
    split = TabularDataset.from_dataframe(frame).split(DatasetConfig(
        target_column=contract.target,
        feature_columns=feature_columns,
        validation_fraction=validation_fraction,
        test_fraction=test_fraction,
        normalization=NormalizationMode.NONE,
        fill_missing="median",
        random_state=seed,
    ))

    locked = set(locked_rule_ids or [])
    known_rule_ids = {rule.rule_id for rule in spec.rules}
    unknown = locked - known_rule_ids
    if unknown:
        raise ExpertCorrectionError(f"Unknown locked rule id(s): {sorted(str(value) for value in unknown)}")
    fitted_indices = [
        index for index, rule in enumerate(spec.rules)
        if rule.enabled and rule.rule_id not in locked
    ]
    if not fitted_indices:
        raise ExpertCorrectionError("At least one enabled Sugeno rule consequent must remain unlocked.")

    # Parameter layout is deterministic. Constant rules receive one parameter;
    # linear rules receive an intercept plus one coefficient for every FIS input.
    layout: list[tuple[int, str, str | None]] = []
    for rule_index in fitted_indices:
        consequent = spec.rules[rule_index].sugeno_consequent
        if consequent is None:
            raise ExpertCorrectionError("Every Sugeno rule must have a consequent before correction.")
        if consequent.kind == "constant":
            layout.append((rule_index, "constant", None))
        else:
            layout.append((rule_index, "intercept", None))
            for variable in spec.inputs:
                layout.append((rule_index, "coefficient", variable.name))

    design: list[list[float]] = []
    rhs: list[float] = []
    train_inputs: list[dict[str, float]] = []
    train_targets: list[float] = []
    skipped = 0
    for source_index in split.train_indices.tolist():
        row = frame.iloc[int(source_index)]
        inputs = {variable_name: float(row[column]) for variable_name, column in mapping.items()}
        target = float(row[contract.target])
        try:
            trace = evaluate_fis(spec, inputs).trace
        except FISError:
            skipped += 1
            continue
        weights = [float(rule.weighted_firing_strength) for rule in trace.rules]
        denominator = float(sum(weights))
        if denominator <= 1e-12:
            skipped += 1
            continue
        locked_contribution = 0.0
        for index, rule in enumerate(spec.rules):
            if not rule.enabled or rule.rule_id not in locked:
                continue
            locked_contribution += weights[index] * _current_consequent_value(spec, index, inputs)
        row_design: list[float] = []
        for rule_index, parameter_kind, variable_name in layout:
            weight = weights[rule_index]
            if parameter_kind in {"constant", "intercept"}:
                row_design.append(weight)
            else:
                assert variable_name is not None
                row_design.append(weight * float(inputs[variable_name]))
        design.append(row_design)
        rhs.append(target * denominator - locked_contribution)
        train_inputs.append(inputs)
        train_targets.append(target)

    if len(design) < max(2, len(layout)):
        raise ExpertCorrectionError(
            f"Only {len(design)} usable TRAIN rows are available for {len(layout)} fitted consequent parameters."
        )
    matrix = np.asarray(design, dtype=float)
    target_vector = np.asarray(rhs, dtype=float)
    if not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(target_vector)):
        raise ExpertCorrectionError("Expert correction design contains non-finite values.")
    solution, _, _, _ = np.linalg.lstsq(matrix, target_vector, rcond=None)

    updated = spec.model_copy(deep=True)
    parameters_by_rule: dict[int, dict[str, object]] = {}
    for value, (rule_index, parameter_kind, variable_name) in zip(solution.tolist(), layout, strict=True):
        bucket = parameters_by_rule.setdefault(rule_index, {"coefficients": {}})
        if parameter_kind == "constant":
            bucket["constant"] = float(value)
        elif parameter_kind == "intercept":
            bucket["intercept"] = float(value)
        else:
            assert variable_name is not None
            coefficients = bucket["coefficients"]
            assert isinstance(coefficients, dict)
            coefficients[variable_name] = float(value)
    for rule_index, bucket in parameters_by_rule.items():
        old = updated.rules[rule_index].sugeno_consequent
        assert old is not None
        if old.kind == "constant":
            updated.rules[rule_index].sugeno_consequent = SugenoConsequent(
                kind="constant", constant=float(bucket["constant"]), coefficients={}, intercept=0.0
            )
        else:
            updated.rules[rule_index].sugeno_consequent = SugenoConsequent(
                kind="linear",
                constant=None,
                coefficients={key: float(value) for key, value in dict(bucket["coefficients"]).items()},
                intercept=float(bucket["intercept"]),
            )

    before = _predict_rows(spec, train_inputs)
    after = _predict_rows(updated, train_inputs)
    targets = np.asarray(train_targets, dtype=float)
    rmse_before = float(np.sqrt(np.mean((before - targets) ** 2)))
    rmse_after = float(np.sqrt(np.mean((after - targets) ** 2)))

    # The correction itself is fitted on TRAIN only. Validation is evaluated
    # afterwards, without feeding its result back into fitting/selection, so the
    # user gets honest before/after evidence while the final test stays locked.
    column_index = {column: index for index, column in enumerate(split.feature_columns)}
    validation_inputs = [
        {
            variable_name: float(split.validation_features[row_index, column_index[column]])
            for variable_name, column in mapping.items()
        }
        for row_index in range(split.validation_features.shape[0])
    ]
    validation_targets = np.asarray(split.validation_targets, dtype=float).reshape(-1)
    if validation_inputs:
        validation_before = _predict_rows(spec, validation_inputs)
        validation_after = _predict_rows(updated, validation_inputs)
        validation_rmse_before = float(np.sqrt(np.mean((validation_before - validation_targets) ** 2)))
        validation_rmse_after = float(np.sqrt(np.mean((validation_after - validation_targets) ** 2)))
    else:
        validation_rmse_before = None
        validation_rmse_after = None

    saved = persist_fis(project_root, updated)
    assert saved.semantic_hash is not None
    correction = ExpertCorrectionRevision(
        fis_id=saved.fis_id,
        source_semantic_hash=source_hash,
        result_semantic_hash=saved.semantic_hash,
        dataset_fingerprint=contract.dataset_fingerprint,
        target=contract.target,
        split_seed=seed,
        validation_fraction=validation_fraction,
        test_fraction=test_fraction,
        train_row_count=len(train_inputs),
        skipped_row_count=skipped,
        locked_rule_ids=sorted(locked, key=str),
        fitted_rule_ids=[spec.rules[index].rule_id for index in fitted_indices],
        source_explanation_id=source_explanation_id,
        train_rmse_before=rmse_before,
        train_rmse_after=rmse_after,
        validation_row_count=len(validation_inputs),
        validation_rmse_before=validation_rmse_before,
        validation_rmse_after=validation_rmse_after,
    )
    _atomic_write(_root(project_root) / f"{correction.correction_id}.json", correction.model_dump_json(indent=2))
    _atomic_write(_root(project_root) / "active-correction.json", json.dumps({"correction_id": str(correction.correction_id)}, indent=2))
    return ExpertCorrectionResult(correction=correction, fis=saved)


def load_expert_correction(project_root: Path, correction_id: UUID) -> ExpertCorrectionRevision:
    return ExpertCorrectionRevision.model_validate_json((_root(project_root) / f"{correction_id}.json").read_text(encoding="utf-8"))


def load_latest_expert_correction(project_root: Path) -> ExpertCorrectionRevision:
    pointer = json.loads((_root(project_root) / "active-correction.json").read_text(encoding="utf-8"))
    return load_expert_correction(project_root, UUID(pointer["correction_id"]))
