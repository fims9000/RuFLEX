from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

from ruflex.application.evidence import _atomic_write_text, predict_run_sample
from ruflex.application.training import load_training_run
from ruflex.application.fis import evaluate_fis, list_fis_revisions, load_fis
from ruflex.domain.behavior import BehaviorObservation, BehaviorRevisionComparison, BehaviorSpec, BehaviorSpecResult


class BehaviorSpecError(ValueError):
    pass


def _root(project_root: Path) -> Path:
    root = Path(project_root).resolve() / "evidence" / "behavior-specs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _requirement_identity(spec: BehaviorSpec) -> str:
    payload = spec.model_dump(mode="json", exclude={"spec_id", "created_at", "run_id", "model_artifact_sha256", "fis_id", "fis_semantic_hash"})
    return "behavior-requirement:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def compare_behavior_results(project_root: Path, baseline_result_id: UUID, candidate_result_id: UUID) -> BehaviorRevisionComparison:
    results = {item.result_id: item for item in list_behavior_results(project_root)}
    try:
        baseline, candidate = results[baseline_result_id], results[candidate_result_id]
    except KeyError as error:
        raise BehaviorSpecError("Both persisted BehaviorSpec results are required for a revision comparison.") from error
    if baseline.result_id == candidate.result_id:
        raise BehaviorSpecError("BehaviorSpec revision comparison requires two distinct results.")
    baseline_spec, candidate_spec = load_behavior_spec(project_root, baseline.spec_id), load_behavior_spec(project_root, candidate.spec_id)
    baseline_requirement, candidate_requirement = _requirement_identity(baseline_spec), _requirement_identity(candidate_spec)
    if baseline_requirement != candidate_requirement:
        raise BehaviorSpecError("BehaviorSpec results do not represent the same frozen requirement.")
    transition = f"{baseline.status}_TO_{candidate.status}"
    comparison = BehaviorRevisionComparison(
        requirement_identity=baseline_requirement, baseline_result_id=baseline.result_id, candidate_result_id=candidate.result_id,
        baseline_status=baseline.status, candidate_status=candidate.status, transition=transition,
        regression_detected=transition == "PASS_TO_FAIL",
        baseline_binding=str(baseline.model_artifact_sha256 or baseline.fis_semantic_hash),
        candidate_binding=str(candidate.model_artifact_sha256 or candidate.fis_semantic_hash),
    )
    _atomic_write_text(_root(project_root) / f"comparison-{comparison.comparison_id}.json", comparison.model_dump_json(indent=2))
    return comparison


def create_behavior_spec(project_root: Path, payload: dict) -> BehaviorSpec:
    clean_payload = {key: value for key, value in payload.items() if key != "session_id"}
    if clean_payload.get("run_id"):
        run = load_training_run(project_root, UUID(str(clean_payload["run_id"])))
        spec = BehaviorSpec.model_validate({**clean_payload, "model_artifact_sha256": run.model_artifact_sha256})
    else:
        fis = load_fis(project_root, str(clean_payload["fis_id"]))
        requested = clean_payload.get("fis_semantic_hash")
        if requested and requested != fis.semantic_hash:
            revisions = {item.semantic_hash: item for item in list_fis_revisions(project_root, str(fis.fis_id))}
            fis = revisions.get(requested)
            if fis is None: raise BehaviorSpecError("Requested FIS semantic revision does not exist.")
        spec = BehaviorSpec.model_validate({**clean_payload, "fis_id": fis.fis_id, "fis_semantic_hash": fis.semantic_hash})
    if spec.kind == "output_range" and spec.minimum is None and spec.maximum is None:
        raise BehaviorSpecError("Output-range specs require a minimum or maximum.")
    pair_kinds = {"monotonic_pair", "invariance_pair", "symmetry_pair", "bounded_perturbation", "categorical_invariance", "required_order"}
    range_kinds = {"output_range", "regression_case", "domain_constraint"}
    if spec.kind in pair_kinds and spec.comparison_sample is None:
        raise BehaviorSpecError(f"{spec.kind} requires a comparison sample.")
    if spec.kind in {"monotonic_pair", "required_order"} and spec.expected_direction is None:
        raise BehaviorSpecError(f"{spec.kind} requires an expected direction.")
    if spec.kind == "bounded_perturbation" and spec.maximum_delta is None:
        raise BehaviorSpecError("Bounded-perturbation specs require maximum_delta.")
    if spec.kind == "forbidden_region" and (spec.minimum is None or spec.maximum is None):
        raise BehaviorSpecError("Forbidden-region specs require minimum and maximum bounds.")
    if spec.kind in range_kinds and spec.minimum is None and spec.maximum is None:
        raise BehaviorSpecError(f"{spec.kind} requires a minimum or maximum.")
    if spec.kind == "batch_regression_suite":
        if not spec.cases: raise BehaviorSpecError("Batch regression suites require one or more named cases.")
        if any(case.minimum is None and case.maximum is None for case in spec.cases): raise BehaviorSpecError("Every batch regression case requires a minimum or maximum.")
    _atomic_write_text(_root(project_root) / f"{spec.spec_id}.json", spec.model_dump_json(indent=2))
    _atomic_write_text(_root(project_root) / "active-spec.json", json.dumps({"spec_id": str(spec.spec_id)}))
    return spec


def evaluate_behavior_spec(project_root: Path, spec: BehaviorSpec) -> BehaviorSpecResult:
    """Recompute a frozen behavior requirement without persisting a result."""
    if spec.run_id is not None:
        run = load_training_run(project_root, spec.run_id)
        if run.model_artifact_sha256 != spec.model_artifact_sha256: raise BehaviorSpecError("BehaviorSpec model artifact identity no longer matches its TrainingRun.")
        value = predict_run_sample(project_root, spec.run_id, spec.sample)
        other = predict_run_sample(project_root, spec.run_id, spec.comparison_sample) if spec.comparison_sample else None
    else:
        fis = next((item for item in list_fis_revisions(project_root, str(spec.fis_id)) if item.semantic_hash == spec.fis_semantic_hash), None)
        if fis is None: raise BehaviorSpecError("Bound FIS semantic revision no longer exists.")
        value = evaluate_fis(fis, spec.sample).output
        other = evaluate_fis(fis, spec.comparison_sample).output if spec.comparison_sample else None
    observations: list[BehaviorObservation] = []
    if spec.kind in {"output_range", "domain_constraint"}:
        passed = (spec.minimum is None or value >= spec.minimum - spec.tolerance) and (spec.maximum is None or value <= spec.maximum + spec.tolerance)
        detail = f"Output {value:.8g} is {'within' if passed else 'outside'} declared range [{spec.minimum}, {spec.maximum}]."
    elif spec.kind in {"invariance_pair", "symmetry_pair", "categorical_invariance"}:
        passed = abs(value - other) <= spec.tolerance
        detail = f"Pair difference {abs(value-other):.8g}; tolerance {spec.tolerance:.8g}."
    elif spec.kind in {"monotonic_pair", "required_order"}:
        passed = value <= other + spec.tolerance if spec.expected_direction == "nondecreasing" else value >= other - spec.tolerance
        detail = f"Outputs {value:.8g} → {other:.8g}; expected {spec.expected_direction}."
    elif spec.kind == "bounded_perturbation":
        passed = abs(value - other) <= (spec.maximum_delta or 0.0) + spec.tolerance
        detail = f"Perturbation difference {abs(value-other):.8g}; maximum {spec.maximum_delta:.8g}."
    elif spec.kind == "forbidden_region":
        passed = value < spec.minimum - spec.tolerance or value > spec.maximum + spec.tolerance
        detail = f"Output {value:.8g} is {'outside' if passed else 'inside'} forbidden region [{spec.minimum}, {spec.maximum}]."
    elif spec.kind == "batch_regression_suite":
        observations = []
        for case in spec.cases:
            output = predict_run_sample(project_root, spec.run_id, case.sample) if spec.run_id is not None else evaluate_fis(fis, case.sample).output
            case_passed = (case.minimum is None or output >= case.minimum - spec.tolerance) and (case.maximum is None or output <= case.maximum + spec.tolerance)
            observations.append(BehaviorObservation(name=case.name, output=output, status="PASS" if case_passed else "FAIL", detail=f"Output {output:.8g}; accepted range [{case.minimum}, {case.maximum}]."))
        passed = all(item.status == "PASS" for item in observations)
        value = observations[0].output
        detail = f"Batch regression suite: {sum(item.status == 'PASS' for item in observations)}/{len(observations)} cases passed."
    else:
        passed = (spec.minimum is None or value >= spec.minimum - spec.tolerance) and (spec.maximum is None or value <= spec.maximum + spec.tolerance)
        detail = f"Regression case output {value:.8g}; accepted range [{spec.minimum}, {spec.maximum}]."
    return BehaviorSpecResult(spec_id=spec.spec_id, run_id=spec.run_id, model_artifact_sha256=spec.model_artifact_sha256, fis_id=spec.fis_id, fis_semantic_hash=spec.fis_semantic_hash, status="PASS" if passed else "FAIL", observed_output=value, comparison_output=other, detail=detail, observations=observations)


def run_behavior_spec(project_root: Path, spec_id: UUID) -> BehaviorSpecResult:
    spec = BehaviorSpec.model_validate_json((_root(project_root) / f"{spec_id}.json").read_text())
    result = evaluate_behavior_spec(project_root, spec)
    _atomic_write_text(_root(project_root) / f"result-{result.result_id}.json", result.model_dump_json(indent=2))
    _atomic_write_text(_root(project_root) / "active-result.json", json.dumps({"result_id": str(result.result_id)}))
    return result


def load_behavior_spec(project_root: Path, spec_id: UUID) -> BehaviorSpec:
    return BehaviorSpec.model_validate_json((_root(project_root) / f"{spec_id}.json").read_text())


def list_behavior_specs(project_root: Path) -> list[BehaviorSpec]:
    root = _root(project_root)
    return sorted(
        (
            BehaviorSpec.model_validate_json(path.read_text())
            for path in root.glob("*.json")
            if path.name not in {"active-spec.json", "active-result.json"}
            and not path.name.startswith(("result-", "comparison-"))
        ),
        key=lambda spec: spec.created_at,
        reverse=True,
    )


def list_behavior_results(project_root: Path) -> list[BehaviorSpecResult]:
    root = _root(project_root)
    return sorted(
        (BehaviorSpecResult.model_validate_json(path.read_text()) for path in root.glob("result-*.json")),
        key=lambda result: result.created_at,
        reverse=True,
    )


def list_behavior_revision_comparisons(project_root: Path) -> list[BehaviorRevisionComparison]:
    root = _root(project_root)
    return sorted(
        (BehaviorRevisionComparison.model_validate_json(path.read_text()) for path in root.glob("comparison-*.json")),
        key=lambda comparison: comparison.created_at,
        reverse=True,
    )


def load_latest_behavior_result(project_root: Path) -> BehaviorSpecResult:
    pointer = json.loads((_root(project_root) / "active-result.json").read_text())
    return BehaviorSpecResult.model_validate_json((_root(project_root) / f"result-{pointer['result_id']}.json").read_text())
