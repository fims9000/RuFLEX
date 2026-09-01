from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from ruflex.application.artifacts import ArtifactMetadata, ArtifactRef, ArtifactStore
from ruflex.application.datasets import DatasetContract, load_dataset_contract, load_dataset_frame
from ruflex.domain.fis import (
    AntecedentClause,
    FISEvaluation,
    FISSpec,
    FISTrace,
    CentroidSampling,
    FuzzyRule,
    FuzzyVariable,
    MembershipFunction,
    MembershipTrace,
    ResponseSurface,
    ResponseSurfaceSample,
    RuleTrace,
)


class FISError(ValueError):
    pass


def diagnose_fis(spec: FISSpec, *, samples: int = 201) -> list[dict[str, object]]:
    """Return non-destructive structural diagnostics for the executable FIS."""
    if samples < 11:
        raise FISError("Diagnostics require at least 11 samples per variable.")
    findings: list[dict[str, object]] = []
    for variable in [*spec.inputs, spec.output]:
        values = np.linspace(variable.minimum, variable.maximum, samples)
        degrees = np.array([membership_degree(values, term) for term in variable.terms])
        coverage = degrees.max(axis=0)
        uncovered = coverage < 0.01
        if np.any(uncovered):
            indices = np.where(uncovered)[0]
            findings.append({"code": "UNCOVERED_INTERVAL", "severity": "warning", "variable": variable.name,
                             "message": f"{variable.name} has an uncovered interval.",
                             "range": [float(values[indices[0]]), float(values[indices[-1]])]})
        for index, term in enumerate(variable.terms):
            if float(degrees[index].max()) < 0.01:
                findings.append({"code": "NEVER_ACTIVE_TERM", "severity": "warning", "variable": variable.name,
                                 "term": term.name, "message": f"{variable.name}.{term.name} is never active in its declared range."})
            if term.kind in {"triangular", "trapezoidal"} and len(set(term.parameters)) == 1:
                findings.append({"code": "DEGENERATE_MF", "severity": "warning", "variable": variable.name,
                                 "term": term.name, "message": f"{variable.name}.{term.name} has zero support."})
        for left in range(len(variable.terms)):
            for right in range(left + 1, len(variable.terms)):
                overlap = float(np.minimum(degrees[left], degrees[right]).max())
                if overlap >= 0.9:
                    findings.append({"code": "EXCESSIVE_OVERLAP", "severity": "warning", "variable": variable.name,
                                     "terms": [variable.terms[left].name, variable.terms[right].name],
                                     "message": f"{variable.name}.{variable.terms[left].name} and {variable.terms[right].name} overlap by {overlap:.0%}."})
                if np.allclose(degrees[left], degrees[right], atol=1e-8, rtol=1e-8):
                    findings.append({"code": "NEAR_DUPLICATE_TERM", "severity": "warning", "variable": variable.name,
                                     "terms": [variable.terms[left].name, variable.terms[right].name],
                                     "message": f"{variable.name}.{variable.terms[left].name} and {variable.terms[right].name} are near-duplicates."})
    return findings


def triangular_membership(value: float | np.ndarray, parameters: tuple[float, float, float]) -> float | np.ndarray:
    a, b, c = parameters
    x = np.asarray(value, dtype=float)
    result = np.zeros_like(x, dtype=float)
    if b > a:
        left = (x - a) / (b - a)
        result = np.maximum(result, np.where((x >= a) & (x <= b), left, 0.0))
    else:
        result = np.maximum(result, np.where(x == b, 1.0, 0.0))
    if c > b:
        right = (c - x) / (c - b)
        result = np.maximum(result, np.where((x >= b) & (x <= c), right, 0.0))
    else:
        result = np.maximum(result, np.where(x == b, 1.0, 0.0))
    result = np.clip(result, 0.0, 1.0)
    if np.isscalar(value):
        return float(result)
    return result


def membership_degree(value: float | np.ndarray, term: MembershipFunction) -> float | np.ndarray:
    x = np.asarray(value, dtype=float)
    p = term.parameters
    if term.kind == "triangular": result = triangular_membership(x, p)  # type: ignore[arg-type]
    elif term.kind == "trapezoidal":
        a, b, c, d = p; result = np.maximum(0.0, np.minimum(np.minimum((x-a)/max(b-a, 1e-12), 1.0), np.minimum((d-x)/max(d-c, 1e-12), 1.0)))
    elif term.kind == "gaussian":
        center, sigma = p; result = np.exp(-0.5 * ((x-center)/sigma)**2)
    elif term.kind == "bell":
        width, shape, center = p; result = 1.0/(1.0+np.abs((x-center)/width)**(2*shape))
    elif term.kind == "sigmoid":
        slope, center = p; result = 1.0/(1.0+np.exp(-np.clip(slope*(x-center), -60, 60)))
    elif term.kind == "s_shape":
        a, b = p; t=np.clip((x-a)/max(b-a,1e-12),0,1); result=np.where(t<=.5,2*t*t,1-2*(1-t)*(1-t))
    elif term.kind == "z_shape":
        a, b = p; t=np.clip((x-a)/max(b-a,1e-12),0,1); result=np.where(t<=.5,1-2*t*t,2*(1-t)*(1-t))
    else:
        a,b,c,d=p; left=membership_degree(x, MembershipFunction(name="_",kind="s_shape",parameters=(a,b))); right=membership_degree(x, MembershipFunction(name="_",kind="z_shape",parameters=(c,d))); result=np.minimum(left,right)
    return float(result) if np.isscalar(value) else result


def _canonical_payload(spec: FISSpec) -> dict:
    """Return inference semantics only. Editor/training locks are not predictions.

    Variable/term locks are workflow metadata. Changing a lock must not make an
    otherwise identical fuzzy system look like a different executable model.
    """
    payload = spec.model_dump(mode="json")
    payload["semantic_hash"] = None
    for variable in [*payload["inputs"], payload["output"]]:
        variable.pop("locked", None)
        for term in variable.get("terms", []):
            term.pop("locked", None)
    return payload


def _rc21_semantic_hash(spec: FISSpec) -> str:
    """RC2.1 semantic identity before centroid quadrature was explicit."""
    payload = _canonical_payload(spec)
    payload["schema_version"] = 1
    payload["operators"].pop("centroid_resolution", None)
    payload["operators"].pop("centroid_sampling", None)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _legacy_semantic_hash(spec: FISSpec) -> str:
    """Hash format used before MembershipFunction.locked was persisted.

    Legacy FuzzyVariable.locked remains in this payload because older RuFLEX
    revisions included it in the semantic hash. This compatibility path lets
    existing projects open and migrate on their next save.
    """
    payload = spec.model_dump(mode="json")
    payload["semantic_hash"] = None
    payload["schema_version"] = 1
    payload["operators"].pop("centroid_resolution", None)
    payload["operators"].pop("centroid_sampling", None)
    for variable in [*payload["inputs"], payload["output"]]:
        for term in variable.get("terms", []):
            term.pop("locked", None)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def semantic_hash(spec: FISSpec) -> str:
    encoded = json.dumps(_canonical_payload(spec), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def with_semantic_hash(spec: FISSpec) -> FISSpec:
    return spec.model_copy(update={"semantic_hash": semantic_hash(spec)})


def centroid_sample_coordinates(minimum: float, maximum: float, resolution: int, sampling: CentroidSampling) -> tuple[np.ndarray, float]:
    """Return the exact declared sample coordinates and their spacing.

    ``inclusive_nodes`` preserves RC2.1: N endpoint-inclusive nodes.  The
    canonical ``midpoint_cells`` convention samples the centre of N equal
    cells, matching FuzzyLite's centroid quadrature semantics.
    """
    if not minimum < maximum:
        raise FISError("Centroid output domain must have a positive width.")
    if sampling is CentroidSampling.INCLUSIVE_NODES:
        if resolution < 2:
            raise FISError("Inclusive-node centroid sampling requires resolution >= 2.")
        dx = (maximum - minimum) / (resolution - 1)
        return minimum + np.arange(resolution, dtype=float) * dx, dx
    if resolution < 1:
        raise FISError("Midpoint-cell centroid sampling requires resolution >= 1.")
    dx = (maximum - minimum) / resolution
    return minimum + (np.arange(resolution, dtype=float) + 0.5) * dx, dx


def reconstruct_mamdani_centroid_trace(trace: FISTrace) -> float:
    """Independently reconstruct a declared sampled centroid from trace evidence."""
    if trace.inference_kind != "mamdani":
        raise FISError("Centroid reconstruction requires a Mamdani trace.")
    if trace.output_domain is None or trace.centroid_resolution is None or trace.centroid_sampling is None:
        raise FISError("Mamdani trace lacks explicit centroid sampling evidence.")
    expected, _ = centroid_sample_coordinates(*trace.output_domain, trace.centroid_resolution, trace.centroid_sampling)
    grid = np.asarray(trace.output_grid, dtype=float)
    aggregate = np.asarray(trace.aggregated_membership, dtype=float)
    if grid.shape != expected.shape or aggregate.shape != expected.shape or not np.allclose(grid, expected, atol=1e-14, rtol=0.0):
        raise FISError("Trace sample coordinates do not match its declared centroid sampling semantics.")
    denominator = float(aggregate.sum())
    if denominator <= 1e-12:
        raise FISError("Trace has no aggregate membership support for centroid reconstruction.")
    return float((grid * aggregate).sum() / denominator)


def _normalize_loaded_fis_payload(payload: dict[str, object]) -> dict[str, object]:
    """Migrate a persisted pre-1.0.1 FIS without reinterpreting its output."""
    normalized = dict(payload)
    operators = dict(normalized.get("operators") or {})
    if "centroid_sampling" not in operators:
        operators["centroid_sampling"] = CentroidSampling.INCLUSIVE_NODES.value
    if "centroid_resolution" not in operators:
        operators["centroid_resolution"] = 401
    normalized["operators"] = operators
    normalized["schema_version"] = max(int(normalized.get("schema_version", 1)), 2)
    return normalized


def _load_fis_payload(path: Path) -> FISSpec:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise FISError("FIS document must be a JSON object.")
    spec = FISSpec.model_validate(_normalize_loaded_fis_payload(raw))
    expected = semantic_hash(spec)
    accepted = {expected, _rc21_semantic_hash(spec), _legacy_semantic_hash(spec)}
    if spec.semantic_hash not in accepted:
        raise FISError("FIS semantic hash mismatch; the saved model may have been modified outside RuFLEX.")
    return spec.model_copy(update={"semantic_hash": expected})


def _safe_numeric_range(series: pd.Series) -> tuple[float, float]:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return 0.0, 1.0
    lo = float(numeric.min())
    hi = float(numeric.max())
    if not math.isfinite(lo) or not math.isfinite(hi):
        return 0.0, 1.0
    if lo == hi:
        pad = max(abs(lo) * 0.1, 1.0)
        return lo - pad, hi + pad
    pad = (hi - lo) * 0.05
    return lo - pad, hi + pad


def _three_terms(minimum: float, maximum: float) -> list[MembershipFunction]:
    span = maximum - minimum
    midpoint = minimum + span / 2.0
    return [
        MembershipFunction(name="Low", parameters=(minimum, minimum, midpoint)),
        MembershipFunction(name="Medium", parameters=(minimum, midpoint, maximum)),
        MembershipFunction(name="High", parameters=(midpoint, maximum, maximum)),
    ]


def create_default_fis(project_root: Path, *, name: str = "Risk FIS", input_columns: list[str] | None = None) -> FISSpec:
    root = Path(project_root)
    contract: DatasetContract = load_dataset_contract(root)
    frame = load_dataset_frame(root)
    candidates = input_columns or [column for column in contract.feature_columns if pd.api.types.is_numeric_dtype(frame[column])]
    candidates = candidates[:3]
    if not candidates:
        raise FISError("Create a dataset contract with at least one numeric feature before building a FIS.")
    inputs: list[FuzzyVariable] = []
    for column in candidates:
        minimum, maximum = _safe_numeric_range(frame[column])
        inputs.append(FuzzyVariable(name=column, minimum=minimum, maximum=maximum, terms=_three_terms(minimum, maximum)))
    output = FuzzyVariable(name=f"{contract.target}_score", minimum=0.0, maximum=1.0, terms=_three_terms(0.0, 1.0), role="output")
    rules = []
    for term in ("Low", "Medium", "High"):
        rules.append(
            FuzzyRule(
                name=f"All {term.lower()} → {term.lower()}",
                clauses=[AntecedentClause(variable=variable.name, term=term) for variable in inputs],
                connector="and",
                output_term=term,
            )
        )
    spec = with_semantic_hash(FISSpec(name=name, inputs=inputs, output=output, rules=rules))
    persist_fis(root, spec)
    return spec


def persist_fis(project_root: Path, spec: FISSpec) -> FISSpec:
    root = Path(project_root).resolve() / "models" / "fis"
    root.mkdir(parents=True, exist_ok=True)
    normalized = with_semantic_hash(spec)
    destination = root / f"{normalized.fis_id}.json"
    fd, temporary_name = tempfile.mkstemp(prefix=".fis-", suffix=".json", dir=root)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(normalized.model_dump_json(indent=2))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    (root / "active.txt").write_text(str(normalized.fis_id), encoding="utf-8")
    revision_root = root / "revisions" / str(normalized.fis_id)
    revision_root.mkdir(parents=True, exist_ok=True)
    if not any(path.stem.endswith((normalized.semantic_hash or "")[:16]) for path in revision_root.glob("*.json")):
        ordinal = len(list(revision_root.glob("*.json"))) + 1
        revision_destination = revision_root / f"{ordinal:06d}-{(normalized.semantic_hash or '')[:16]}.json"
        fd, temporary_name = tempfile.mkstemp(prefix=".revision-", suffix=".json", dir=revision_root)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(normalized.model_dump_json(indent=2))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, revision_destination)
        finally:
            temporary_path.unlink(missing_ok=True)
    return normalized


def list_fis_revisions(project_root: Path, fis_id: str | None = None) -> list[FISSpec]:
    root = Path(project_root).resolve() / "models" / "fis"
    if fis_id is None:
        fis_id = (root / "active.txt").read_text(encoding="utf-8").strip()
    revision_root = root / "revisions" / fis_id
    if not revision_root.is_dir():
        # Projects saved before revision history still expose the active model.
        return [load_fis(project_root, fis_id)]
    revisions = [_load_fis_payload(path) for path in sorted(revision_root.glob("*.json"))]
    normalized_revisions: list[FISSpec] = []
    for revision in revisions:
        normalized_revisions.append(revision)
    return normalized_revisions


def load_fis(project_root: Path, fis_id: str | None = None) -> FISSpec:
    root = Path(project_root).resolve() / "models" / "fis"
    if fis_id is None:
        active_path = root / "active.txt"
        if not active_path.is_file():
            raise FileNotFoundError("No active FIS has been created.")
        fis_id = active_path.read_text(encoding="utf-8").strip()
    path = root / f"{fis_id}.json"
    return _load_fis_payload(path)


def _term(variable: FuzzyVariable, name: str) -> MembershipFunction:
    for term in variable.terms:
        if term.name == name:
            return term
    raise FISError(f"Unknown term {name!r} on variable {variable.name!r}.")


def _t_norm(values: Iterable[float], operator: str) -> float:
    values = list(values)
    if not values:
        return 0.0
    result = values[0]
    for value in values[1:]:
        if operator == "min": result = min(result, value)
        elif operator == "product": result *= value
        elif operator == "lukasiewicz": result = max(0.0, result + value - 1.0)
        elif operator == "hamacher": result = (result * value) / max(1e-12, result + value - result * value)
        else: result = (result * value) / max(1e-12, 2.0 - (result + value - result * value))
    return float(np.clip(result, 0.0, 1.0))


def _s_norm(values: Iterable[float], operator: str) -> float:
    values = list(values)
    if not values:
        return 0.0
    result = values[0]
    for value in values[1:]:
        if operator == "max": result = max(result, value)
        elif operator == "probabilistic_sum": result = result + value - result * value
        elif operator == "bounded_sum": result = min(1.0, result + value)
        elif operator == "hamacher": result = (result + value - 2.0 * result * value) / max(1e-12, 1.0 - result * value)
        else: result = (result + value) / max(1e-12, 1.0 + result * value)
    return float(np.clip(result, 0.0, 1.0))


def _aggregate_rule(rule: FuzzyRule, clause_values: Iterable[float], operators: object) -> float:
    return _t_norm(clause_values, operators.and_operator) if rule.connector == "and" else _s_norm(clause_values, operators.or_operator)


def _sugeno_value(rule: FuzzyRule, inputs: dict[str, float]) -> float:
    consequent = rule.sugeno_consequent
    if consequent is None:  # guarded by FISSpec; retain a fail-closed service boundary.
        raise FISError(f"Sugeno rule {rule.name!r} has no consequent.")
    if consequent.kind == "constant":
        assert consequent.constant is not None
        return float(consequent.constant)
    return float(consequent.intercept + sum(coefficient * inputs[name] for name, coefficient in consequent.coefficients.items()))


def evaluate_response_surface(
    spec: FISSpec,
    *,
    x_variable: str,
    y_variable: str,
    fixed_inputs: dict[str, float] | None = None,
    resolution: int = 31,
) -> ResponseSurface:
    """Evaluate the current canonical FIS on a two-dimensional control grid.

    This intentionally routes each cell through ``evaluate_fis`` rather than a
    frontend approximation, preserving the same operator and inference
    semantics that Run and Trace use.
    """
    if not 2 <= resolution <= 101:
        raise FISError("Response-surface resolution must be between 2 and 101.")
    input_map = {variable.name: variable for variable in spec.inputs}
    if x_variable not in input_map or y_variable not in input_map or x_variable == y_variable:
        raise FISError("Choose two distinct input variables for a response surface.")
    supplied = dict(fixed_inputs or {})
    unexpected = set(supplied) - set(input_map)
    if unexpected:
        raise FISError(f"Response surface fixed inputs contain unknown variables: {sorted(unexpected)}.")
    for name, variable in input_map.items():
        if name not in {x_variable, y_variable}:
            supplied.setdefault(name, (variable.minimum + variable.maximum) / 2.0)
            if not variable.minimum <= supplied[name] <= variable.maximum:
                raise FISError(f"Fixed value for {name!r} is outside its declared range.")
    x_values = np.linspace(input_map[x_variable].minimum, input_map[x_variable].maximum, resolution)
    y_values = np.linspace(input_map[y_variable].minimum, input_map[y_variable].maximum, resolution)
    samples: list[ResponseSurfaceSample] = []
    for x_value in x_values:
        for y_value in y_values:
            inputs = {**supplied, x_variable: float(x_value), y_variable: float(y_value)}
            try:
                output = evaluate_fis(spec, inputs).output
            except FISError as error:
                if "No rule produced a non-zero consequent" not in str(error):
                    raise
                output = None
            samples.append(ResponseSurfaceSample(x=float(x_value), y=float(y_value), output=output))
    normalized = with_semantic_hash(spec)
    return ResponseSurface(
        fis_id=normalized.fis_id, semantic_hash=normalized.semantic_hash or semantic_hash(normalized),
        x_variable=x_variable, y_variable=y_variable, fixed_inputs={key: float(value) for key, value in supplied.items()},
        resolution=resolution, samples=samples,
    )


def evaluate_fis(spec: FISSpec, inputs: dict[str, float], *, grid_size: int | None = None) -> FISEvaluation:
    normalized = with_semantic_hash(spec)
    input_map = {variable.name: variable for variable in normalized.inputs}
    missing = sorted(set(input_map) - set(inputs))
    extra = sorted(set(inputs) - set(input_map))
    if missing or extra:
        raise FISError(f"Input mismatch. Missing={missing or 'none'}; unexpected={extra or 'none'}.")

    memberships: list[MembershipTrace] = []
    membership_lookup: dict[tuple[str, str], float] = {}
    for name, variable in input_map.items():
        value = float(inputs[name])
        if not variable.minimum <= value <= variable.maximum:
            raise FISError(
                f"Input {name!r}={value} is outside the declared range [{variable.minimum}, {variable.maximum}]."
            )
        values: dict[str, float] = {}
        for term in variable.terms:
            degree = float(membership_degree(value, term))
            values[term.name] = degree
            membership_lookup[(name, term.name)] = degree
        memberships.append(MembershipTrace(variable=name, value=value, memberships=values))

    rule_traces: list[RuleTrace] = []
    if normalized.system_type == "sugeno":
        numerator = 0.0
        denominator = 0.0
        for rule in normalized.rules:
            clause_values = {
                f"{clause.variable}.{clause.term}": membership_lookup[(clause.variable, clause.term)]
                for clause in rule.clauses
            }
            firing = _aggregate_rule(rule, clause_values.values(), normalized.operators) if rule.enabled else 0.0
            weighted = firing * rule.weight
            consequent_value = _sugeno_value(rule, inputs)
            numerator += weighted * consequent_value
            denominator += weighted
            rule_traces.append(
                RuleTrace(
                    rule_id=rule.rule_id, name=rule.name, enabled=rule.enabled, connector=rule.connector,
                    clause_values=clause_values, firing_strength=firing, weight=rule.weight,
                    weighted_firing_strength=weighted, output_term=rule.output_term,
                    consequent_value=consequent_value,
                )
            )
        if denominator <= 1e-12:
            raise FISError("No rule produced a non-zero consequent; Sugeno output is undefined for this input.")
        output = numerator / denominator
        trace = FISTrace(
            fis_id=normalized.fis_id, semantic_hash=normalized.semantic_hash or semantic_hash(normalized),
            input_values={name: float(value) for name, value in inputs.items()}, memberships=memberships,
            rules=rule_traces, output_grid=[], aggregated_membership=[], final_output=output,
            reconstruction_output=output, reconstruction_error=0.0, inference_kind="sugeno",
        )
        return FISEvaluation(output_name=normalized.output.name, output=output, trace=trace)

    if grid_size is not None and grid_size != normalized.operators.centroid_resolution:
        raise FISError("Evaluation grid_size must match the persisted centroid resolution; change the canonical operator setting instead.")
    resolution = normalized.operators.centroid_resolution
    sampling = normalized.operators.centroid_sampling
    output_grid, dx = centroid_sample_coordinates(normalized.output.minimum, normalized.output.maximum, resolution, sampling)
    aggregated = np.zeros_like(output_grid)
    for rule in normalized.rules:
        clause_values = {
            f"{clause.variable}.{clause.term}": membership_lookup[(clause.variable, clause.term)]
            for clause in rule.clauses
        }
        firing = _aggregate_rule(rule, clause_values.values(), normalized.operators) if rule.enabled else 0.0
        weighted = firing * rule.weight
        consequent = _term(normalized.output, rule.output_term)
        consequent_curve = np.asarray(membership_degree(output_grid, consequent))
        implied = np.minimum(weighted, consequent_curve) if normalized.operators.implication == "min" else weighted * consequent_curve
        if normalized.operators.aggregation == "max":
            aggregated = np.maximum(aggregated, implied)
        elif normalized.operators.aggregation == "probabilistic_sum":
            aggregated = aggregated + implied - aggregated * implied
        elif normalized.operators.aggregation == "bounded_sum":
            aggregated = np.minimum(1.0, aggregated + implied)
        elif normalized.operators.aggregation == "hamacher":
            aggregated = (aggregated + implied - 2 * aggregated * implied) / np.maximum(1e-12, 1 - aggregated * implied)
        else:
            aggregated = (aggregated + implied) / np.maximum(1e-12, 1 + aggregated * implied)
        rule_traces.append(
            RuleTrace(
                rule_id=rule.rule_id,
                name=rule.name,
                enabled=rule.enabled,
                connector=rule.connector,
                clause_values=clause_values,
                firing_strength=firing,
                weight=rule.weight,
                weighted_firing_strength=weighted,
                output_term=rule.output_term,
            )
        )

    denominator = float(np.sum(aggregated))
    if denominator <= 1e-12:
        raise FISError("No rule produced a non-zero consequent; output is undefined for this input.")
    output = float(np.sum(output_grid * aggregated) / denominator)
    reconstructed = float(np.sum(output_grid * aggregated) / denominator)
    trace = FISTrace(
        fis_id=normalized.fis_id,
        semantic_hash=normalized.semantic_hash or semantic_hash(normalized),
        input_values={name: float(value) for name, value in inputs.items()},
        memberships=memberships,
        rules=rule_traces,
        output_grid=[float(value) for value in output_grid],
        aggregated_membership=[float(value) for value in aggregated],
        defuzzification=normalized.operators.defuzzification,
        output_domain=(normalized.output.minimum, normalized.output.maximum),
        centroid_resolution=resolution,
        centroid_sampling=sampling,
        centroid_dx=dx,
        centroid_sample_count=len(output_grid),
        final_output=output,
        reconstruction_output=reconstructed,
        reconstruction_error=abs(output - reconstructed),
        inference_kind="mamdani",
    )
    return FISEvaluation(output_name=normalized.output.name, output=output, trace=trace)



def load_latest_trace(project_root: Path) -> FISEvaluation:
    store = ArtifactStore(project_root)
    records = [
        record
        for record in store.list_records()
        if record.media_type == "application/vnd.ruflex.fis-trace+json"
    ]
    if not records:
        raise FileNotFoundError("No FIS trace artifact exists in this project.")
    record = max(records, key=lambda item: item.created_at)
    with store.open(ArtifactRef(sha256=record.sha256)) as handle:
        trace = FISTrace.model_validate_json(handle.read())
    spec = load_fis(project_root, str(trace.fis_id))
    if trace.semantic_hash != spec.semantic_hash:
        raise FISError("Latest trace is stale for the current saved FIS revision.")
    return FISEvaluation(output_name=spec.output.name, output=trace.final_output, trace=trace)

def save_trace_artifact(project_root: Path, evaluation: FISEvaluation) -> ArtifactRef:
    payload = evaluation.trace.model_dump_json(indent=2).encode("utf-8")
    return ArtifactStore(project_root).ingest_bytes(
        payload,
        metadata=ArtifactMetadata(
            media_type="application/vnd.ruflex.fis-trace+json",
            source_kind="generated",
            original_name=f"fis-trace-{evaluation.trace.fis_id}.json",
            producer={"component": "ruflex.application.fis", "trace_schema_version": str(evaluation.trace.trace_schema_version)},
        ),
    )
