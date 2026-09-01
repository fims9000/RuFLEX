"""Versioned, declarative intended-use contracts for evaluation design."""

from __future__ import annotations

import json
import os
import tempfile

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error, precision_score, r2_score, recall_score
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ruflex.application.datasets import DatasetContract, load_dataset_frame


class GeneralizationContractError(ValueError):
    pass


class ContractFreezeError(GeneralizationContractError):
    pass


class ScopeRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str = Field(min_length=1)
    operator: Literal["in", "not_in", "between", "present", "custom"]
    value: Any = None
    rationale: str = Field(min_length=1)


class NoveltyAxis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    axis: Literal["entity", "time", "site", "device", "spatial", "regime", "custom"]
    expected_future_relation: str = Field(min_length=1)
    evaluation_requirement: str = Field(min_length=1)


class MetricConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: str = Field(min_length=1)
    comparator: Literal["ge", "le"]
    value: float
    scope: Literal["global", "subgroup", "domain", "policy"]


class ScopeDisposition(StrEnum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REVIEW = "REVIEW"


class ScopeClassification(BaseModel):
    disposition: ScopeDisposition
    reasons: list[str]


class SplitRecommendation(BaseModel):
    family: Literal["group", "temporal", "site", "spatial", "regime", "random"]
    rationale: str
    advisory: bool = True


class LintFinding(BaseModel):
    code: str
    severity: Literal["error", "warning"]
    message: str
    next_action: str


class ContractLintReport(BaseModel):
    contract_id: UUID
    findings: list[LintFinding]
    can_freeze: bool


class GeneralizationContract(BaseModel):
    """Human-readable scope contract; frozen instances are immutable evidence."""

    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    contract_id: UUID = Field(default_factory=uuid4)
    dataset_fingerprint: str
    intended_use: str = Field(min_length=1)
    novelty_axes: list[NoveltyAxis] = Field(min_length=1)
    supported_scope: list[ScopeRule] = Field(default_factory=list)
    forbidden_scope: list[ScopeRule] = Field(default_factory=list)
    required_subgroups: list[ScopeRule] = Field(default_factory=list)
    minimum_evidence: list[MetricConstraint] = Field(default_factory=list)
    unsupported_action: Literal["BLOCK", "REVIEW"] = "BLOCK"
    version: int = Field(default=1, ge=1)
    parent_contract_id: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    frozen_at: datetime | None = None

    @model_validator(mode="after")
    def no_duplicate_axes(self) -> "GeneralizationContract":
        if len({axis.axis for axis in self.novelty_axes}) != len(self.novelty_axes):
            raise GeneralizationContractError("Novelty axes must not be duplicated.")
        return self


_AXIS_KEY_HINTS: dict[str, tuple[str, ...]] = {
    "entity": ("entity", "patient", "subject", "group"),
    "time": ("time", "date", "timestamp", "month", "year"),
    "site": ("site", "hospital", "center", "location"),
    "device": ("device", "machine", "instrument", "scanner"),
    "spatial": ("spatial", "latitude", "longitude", "lat", "lon", "region", "location"),
    "regime": ("regime", "mode", "condition", "setting"),
}
_SPLIT_FAMILY = {"entity": "group", "time": "temporal", "site": "site", "spatial": "spatial", "regime": "regime", "device": "group", "custom": "random"}


def create_generalization_contract(dataset: DatasetContract, spec: dict[str, Any]) -> GeneralizationContract:
    """Create an unfrozen intended-use declaration tied to one dataset version."""
    payload = dict(spec)
    payload.pop("contract_id", None)
    payload.pop("created_at", None)
    payload["dataset_fingerprint"] = dataset.dataset_fingerprint
    payload.setdefault("schema_version", 1)
    payload.setdefault("version", 1)
    payload.setdefault("frozen_at", None)
    return GeneralizationContract.model_validate(payload)


def lint_generalization_contract(contract: GeneralizationContract, dataset: DatasetContract) -> ContractLintReport:
    findings: list[LintFinding] = []
    if contract.dataset_fingerprint != dataset.dataset_fingerprint:
        findings.append(LintFinding(code="DATASET_FINGERPRINT_MISMATCH", severity="error", message="The contract belongs to a different dataset version.", next_action="Create a new contract for this DatasetContract."))
    names = {name.lower() for name in (*dataset.feature_columns, *dataset.id_columns, dataset.target)}
    for axis in contract.novelty_axes:
        if axis.axis == "custom":
            if not any(rule.operator == "custom" for rule in (*contract.supported_scope, *contract.forbidden_scope)):
                findings.append(LintFinding(code="CUSTOM_AXIS_UNBOUND", severity="error", message="Custom novelty needs an explicit custom scope rule.", next_action="Add a serializable custom rule through a registered trusted plugin."))
            continue
        hints = _AXIS_KEY_HINTS[axis.axis]
        if not any(any(hint in name for hint in hints) for name in names):
            findings.append(LintFinding(code="MISSING_NOVELTY_KEY", severity="error", message=f"The {axis.axis} novelty axis has no matching dataset metadata key.", next_action=f"Add or map a {axis.axis} key before freezing this contract."))
    for rule in (*contract.supported_scope, *contract.forbidden_scope, *contract.required_subgroups):
        if rule.operator != "custom" and rule.field.lower() not in names:
            findings.append(LintFinding(code="MISSING_SCOPE_KEY", severity="error", message=f"Scope rule references absent key: {rule.field}.", next_action="Use a DatasetContract metadata key or revise the rule."))
    return ContractLintReport(contract_id=contract.contract_id, findings=findings, can_freeze=not any(item.severity == "error" for item in findings))


def recommend_split_families(contract: GeneralizationContract) -> list[SplitRecommendation]:
    recommendations: list[SplitRecommendation] = []
    for axis in contract.novelty_axes:
        family = _SPLIT_FAMILY[axis.axis]
        if family == "random":
            continue
        if family not in {item.family for item in recommendations}:
            recommendations.append(SplitRecommendation(family=family, rationale=f"{axis.axis.title()} novelty: {axis.evaluation_requirement}"))
    return recommendations or [SplitRecommendation(family="random", rationale="No structured novelty axis was declared; random splitting remains advisory only.")]


def classify_scope(contract: GeneralizationContract, sample_metadata: dict[str, Any]) -> ScopeClassification:
    for rule in contract.forbidden_scope:
        if _rule_matches(rule, sample_metadata):
            return ScopeClassification(disposition=ScopeDisposition.BLOCK, reasons=[f"Forbidden scope rule matched: {rule.field}."])
    if contract.supported_scope and not all(_rule_matches(rule, sample_metadata) for rule in contract.supported_scope):
        return ScopeClassification(disposition=ScopeDisposition(contract.unsupported_action), reasons=["Sample is outside declared supported scope."])
    missing = [rule.field for rule in contract.required_subgroups if rule.field not in sample_metadata]
    if missing:
        return ScopeClassification(disposition=ScopeDisposition.REVIEW, reasons=[f"Required subgroup metadata is missing: {', '.join(missing)}."])
    return ScopeClassification(disposition=ScopeDisposition.ALLOW, reasons=["Sample matches declared scope."])


def freeze_generalization_contract(contract: GeneralizationContract, dataset: DatasetContract) -> GeneralizationContract:
    if contract.frozen_at is not None:
        return contract
    report = lint_generalization_contract(contract, dataset)
    if not report.can_freeze:
        raise ContractFreezeError("Generalization contract cannot freeze: " + "; ".join(item.message for item in report.findings if item.severity == "error"))
    return contract.model_copy(update={"frozen_at": datetime.now(timezone.utc)})


def revise_generalization_contract(contract: GeneralizationContract, changes: dict[str, Any], *, allow_from_frozen: bool = False) -> GeneralizationContract:
    if contract.frozen_at is not None and not allow_from_frozen:
        raise ContractFreezeError("A frozen contract is immutable; create a new version instead.")
    payload = contract.model_dump(mode="python")
    payload.update(changes)
    payload.update({"contract_id": uuid4(), "parent_contract_id": contract.contract_id, "version": contract.version + 1, "created_at": datetime.now(timezone.utc), "frozen_at": None})
    return GeneralizationContract.model_validate(payload)


def persist_generalization_contract(project_root: Path, contract: GeneralizationContract) -> Path:
    root = Path(project_root).resolve() / "objects" / "protocols" / "generalization"
    root.mkdir(parents=True, exist_ok=True)
    destination = root / f"{contract.contract_id}.json"
    _atomic_json(destination, contract.model_dump(mode="json"))
    return destination


def load_generalization_contract(project_root: Path, contract_id: UUID) -> GeneralizationContract:
    path = Path(project_root) / "objects" / "protocols" / "generalization" / f"{contract_id}.json"
    return GeneralizationContract.model_validate_json(path.read_text(encoding="utf-8"))


def _rule_matches(rule: ScopeRule, metadata: dict[str, Any]) -> bool:
    if rule.field not in metadata:
        return False
    value = metadata[rule.field]
    if rule.operator == "present":
        return value is not None
    if rule.operator == "in":
        return value in rule.value
    if rule.operator == "not_in":
        return value not in rule.value
    if rule.operator == "between":
        lower, upper = rule.value
        return lower <= value <= upper
    return False


def _atomic_json(destination: Path, payload: dict[str, Any]) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=".generalization-", dir=destination.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, destination)
    finally:
        temp.unlink(missing_ok=True)


class SliceDefinition(BaseModel):
    """Serializable validation-slice definition.

    Slice evaluation is deliberately tied to source-row identity from the
    validation split.  RuFLEX never assumes that a validation-relative row
    number is an original dataset row.
    """

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["categorical", "numeric_range", "group", "temporal", "manual"]
    field: str | None = None
    values: list[str | int | float] = Field(default_factory=list)
    minimum: float | None = None
    maximum: float | None = None
    start: str | None = None
    end: str | None = None
    source_rows: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_definition(self) -> "SliceDefinition":
        if self.kind == "manual":
            if not self.source_rows:
                raise GeneralizationContractError("Manual slice requires at least one original source row id.")
            return self
        if not self.field:
            raise GeneralizationContractError(f"{self.kind} slice requires a dataset field.")
        if self.kind in {"categorical", "group"} and not self.values:
            raise GeneralizationContractError(f"{self.kind} slice requires one or more selected values.")
        if self.kind == "numeric_range" and self.minimum is None and self.maximum is None:
            raise GeneralizationContractError("numeric_range slice requires minimum and/or maximum.")
        if self.kind == "temporal" and self.start is None and self.end is None:
            raise GeneralizationContractError("temporal slice requires start and/or end.")
        return self


class SliceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    kind: str
    n: int = Field(ge=0)
    metric: str
    value: float | None
    overall_value: float
    delta_vs_overall: float | None
    status: Literal["OK", "WARN", "EMPTY"]
    warning: str | None = None
    scope_disposition: Literal["ALLOW", "REVIEW", "BLOCK", "UNDECLARED", "EMPTY"] = "UNDECLARED"
    scope_reasons: list[str] = Field(default_factory=list)


class SliceAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    analysis_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evaluation_id: UUID
    run_id: UUID
    dataset_fingerprint: str
    generalization_contract_id: UUID | None = None
    source_split: Literal["validation"] = "validation"
    test_status: Literal["LOCKED_NOT_EVALUATED"] = "LOCKED_NOT_EVALUATED"
    metric: str
    definitions: list[SliceDefinition]
    results: list[SliceResult]
    scientific_note: str = (
        "Slice metrics are computed only on the persisted validation evidence. "
        "They describe observed subgroup behavior and do not by themselves establish generalization beyond the declared contract."
    )


def _slice_root(project_root: Path) -> Path:
    root = Path(project_root).resolve() / "analyses" / "slices"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _slice_metric(task: str, metric: str, rows: pd.DataFrame) -> float:
    truth = rows["target"].to_numpy(dtype=float)
    if task == "binary_classification":
        labels = rows["predicted_label"].to_numpy(dtype=float).astype(int)
        target_labels = (truth >= 0.5).astype(int)
        if metric == "accuracy":
            return float(accuracy_score(target_labels, labels))
        if metric == "precision":
            return float(precision_score(target_labels, labels, zero_division=0))
        if metric == "recall":
            return float(recall_score(target_labels, labels, zero_division=0))
        if metric == "f1":
            return float(f1_score(target_labels, labels, zero_division=0))
        if metric == "brier":
            probabilities = rows["probability"].to_numpy(dtype=float)
            return float(np.mean((probabilities - target_labels) ** 2))
        raise GeneralizationContractError(f"Unsupported classification slice metric {metric!r}.")
    predictions = rows["prediction"].to_numpy(dtype=float)
    if metric == "mae":
        return float(mean_absolute_error(truth, predictions))
    if metric == "mse":
        return float(mean_squared_error(truth, predictions))
    if metric == "rmse":
        return float(np.sqrt(mean_squared_error(truth, predictions)))
    if metric == "r2":
        if len(rows) < 2:
            raise GeneralizationContractError("R2 requires at least two rows in a slice.")
        return float(r2_score(truth, predictions))
    raise GeneralizationContractError(f"Unsupported regression slice metric {metric!r}.")


def _slice_mask(definition: SliceDefinition, evidence: pd.DataFrame) -> pd.Series:
    if definition.kind == "manual":
        return evidence["source_row"].isin(definition.source_rows)
    assert definition.field is not None
    if definition.field not in evidence.columns:
        raise GeneralizationContractError(f"Slice field {definition.field!r} is not available in the persisted dataset.")
    series = evidence[definition.field]
    if definition.kind in {"categorical", "group"}:
        # Compare through string representation so categorical values loaded from
        # CSV/XLSX remain stable across pandas numeric/string inference.
        allowed = {str(value) for value in definition.values}
        return series.map(str).isin(allowed)
    if definition.kind == "numeric_range":
        numeric = pd.to_numeric(series, errors="coerce")
        mask = pd.Series(True, index=evidence.index)
        if definition.minimum is not None:
            mask &= numeric >= definition.minimum
        if definition.maximum is not None:
            mask &= numeric <= definition.maximum
        return mask.fillna(False)
    if definition.kind == "temporal":
        temporal = pd.to_datetime(series, errors="coerce", utc=True)
        mask = pd.Series(True, index=evidence.index)
        if definition.start is not None:
            mask &= temporal >= pd.Timestamp(definition.start, tz="UTC")
        if definition.end is not None:
            mask &= temporal <= pd.Timestamp(definition.end, tz="UTC")
        return mask.fillna(False)
    raise GeneralizationContractError(f"Unsupported slice kind {definition.kind!r}.")


def _scope_summary(contract: GeneralizationContract | None, rows: pd.DataFrame) -> tuple[str, list[str]]:
    if rows.empty:
        return "EMPTY", ["No validation rows matched this slice, so deployment scope cannot be classified."]
    if contract is None:
        return "UNDECLARED", ["No GeneralizationContract is linked to this Slice Analysis."]
    dispositions: list[ScopeDisposition] = []
    reasons: list[str] = []
    for _, row in rows.iterrows():
        classification = classify_scope(contract, row.to_dict())
        dispositions.append(classification.disposition)
        for reason in classification.reasons:
            if reason not in reasons:
                reasons.append(reason)
    if ScopeDisposition.BLOCK in dispositions:
        return "BLOCK", reasons or ["At least one validation row matches forbidden scope."]
    if ScopeDisposition.REVIEW in dispositions:
        return "REVIEW", reasons or ["At least one validation row requires review under the declared scope contract."]
    return "ALLOW", reasons or ["All matched validation rows are inside declared supported scope."]


def create_slice_analysis(
    project_root: Path,
    *,
    evaluation_id: UUID,
    definitions: list[SliceDefinition],
    metric: str | None = None,
    generalization_contract_id: UUID | None = None,
) -> SliceAnalysis:
    from ruflex.application.training import load_validation_evaluation

    if not definitions:
        raise GeneralizationContractError("Slice Lab requires at least one slice definition.")
    evaluation = load_validation_evaluation(project_root, evaluation_id)
    if not evaluation.prediction_preview:
        raise GeneralizationContractError("The selected Evaluation has no persisted validation prediction evidence.")
    if any(row.source_row is None for row in evaluation.prediction_preview):
        raise GeneralizationContractError(
            "This Evaluation predates source-row provenance. Retrain/re-evaluate the model revision before Slice Lab; validation-relative row numbers are not treated as dataset row ids."
        )
    frame = load_dataset_frame(project_root)
    contract: GeneralizationContract | None = None
    if generalization_contract_id is not None:
        contract = load_generalization_contract(project_root, generalization_contract_id)
        if contract.dataset_fingerprint != evaluation.dataset_fingerprint:
            raise GeneralizationContractError(
                "The active GeneralizationContract belongs to a different dataset revision than the selected Evaluation."
            )
    dataset_rows: list[dict[str, Any]] = []
    for row in evaluation.prediction_preview:
        assert row.source_row is not None
        if row.source_row < 0 or row.source_row >= len(frame):
            raise GeneralizationContractError("Persisted validation source-row identity is outside the current dataset artifact.")
        source = frame.iloc[row.source_row].to_dict()
        source.update({
            "source_row": int(row.source_row),
            "target": float(row.target),
            "prediction": float(row.prediction),
            "probability": None if row.probability is None else float(row.probability),
            "predicted_label": row.predicted_label,
            "residual": row.residual,
        })
        dataset_rows.append(source)
    evidence = pd.DataFrame(dataset_rows)
    resolved_metric = metric or ("f1" if evaluation.task == "binary_classification" else "rmse")
    overall = _slice_metric(evaluation.task, resolved_metric, evidence)
    results: list[SliceResult] = []
    for definition in definitions:
        selected = evidence.loc[_slice_mask(definition, evidence)].copy()
        if selected.empty:
            disposition, scope_reasons = _scope_summary(contract, selected)
            results.append(SliceResult(
                name=definition.name, kind=definition.kind, n=0, metric=resolved_metric, value=None,
                overall_value=overall, delta_vs_overall=None, status="EMPTY",
                warning="No validation rows matched this slice.",
                scope_disposition=disposition, scope_reasons=scope_reasons,
            ))
            continue
        try:
            value = _slice_metric(evaluation.task, resolved_metric, selected)
        except GeneralizationContractError as error:
            disposition, scope_reasons = _scope_summary(contract, selected)
            results.append(SliceResult(
                name=definition.name, kind=definition.kind, n=len(selected), metric=resolved_metric, value=None,
                overall_value=overall, delta_vs_overall=None, status="WARN", warning=str(error),
                scope_disposition=disposition, scope_reasons=scope_reasons,
            ))
            continue
        warning = "Small validation slice; interpret the metric cautiously." if len(selected) < 10 else None
        disposition, scope_reasons = _scope_summary(contract, selected)
        results.append(SliceResult(
            name=definition.name,
            kind=definition.kind,
            n=len(selected),
            metric=resolved_metric,
            value=value,
            overall_value=overall,
            delta_vs_overall=float(value - overall),
            status="WARN" if warning else "OK",
            warning=warning,
            scope_disposition=disposition,
            scope_reasons=scope_reasons,
        ))
    analysis = SliceAnalysis(
        evaluation_id=evaluation.evaluation_id,
        run_id=evaluation.run_id,
        dataset_fingerprint=evaluation.dataset_fingerprint or "unknown",
        generalization_contract_id=generalization_contract_id,
        metric=resolved_metric,
        definitions=definitions,
        results=results,
    )
    root = _slice_root(project_root)
    _atomic_json(root / f"{analysis.analysis_id}.json", analysis.model_dump(mode="json"))
    _atomic_json(root / "active-slice-analysis.json", {"analysis_id": str(analysis.analysis_id)})
    return analysis


def load_slice_analysis(project_root: Path, analysis_id: UUID) -> SliceAnalysis:
    return SliceAnalysis.model_validate_json((_slice_root(project_root) / f"{analysis_id}.json").read_text(encoding="utf-8"))


def load_latest_slice_analysis(project_root: Path) -> SliceAnalysis:
    pointer = json.loads((_slice_root(project_root) / "active-slice-analysis.json").read_text(encoding="utf-8"))
    return load_slice_analysis(project_root, UUID(pointer["analysis_id"]))
