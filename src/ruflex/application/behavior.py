from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from ruflex.application.evidence import _atomic_write_text, predict_run_sample
from ruflex.application.training import load_training_run
from ruflex.application.fis import evaluate_fis, list_fis_revisions, load_fis
from ruflex.domain.behavior import BehaviorSpec, BehaviorSpecResult


class BehaviorSpecError(ValueError):
    pass


def _root(project_root: Path) -> Path:
    root = Path(project_root).resolve() / "evidence" / "behavior-specs"
    root.mkdir(parents=True, exist_ok=True)
    return root


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
    if spec.kind in {"monotonic_pair", "invariance_pair"} and spec.comparison_sample is None:
        raise BehaviorSpecError(f"{spec.kind} requires a comparison sample.")
    if spec.kind == "monotonic_pair" and spec.expected_direction is None:
        raise BehaviorSpecError("Monotonic-pair specs require an expected direction.")
    _atomic_write_text(_root(project_root) / f"{spec.spec_id}.json", spec.model_dump_json(indent=2))
    _atomic_write_text(_root(project_root) / "active-spec.json", json.dumps({"spec_id": str(spec.spec_id)}))
    return spec


def run_behavior_spec(project_root: Path, spec_id: UUID) -> BehaviorSpecResult:
    spec = BehaviorSpec.model_validate_json((_root(project_root) / f"{spec_id}.json").read_text())
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
    if spec.kind == "output_range":
        passed = (spec.minimum is None or value >= spec.minimum - spec.tolerance) and (spec.maximum is None or value <= spec.maximum + spec.tolerance)
        detail = f"Output {value:.8g} is {'within' if passed else 'outside'} declared range [{spec.minimum}, {spec.maximum}]."
    elif spec.kind == "invariance_pair":
        passed = abs(value - other) <= spec.tolerance
        detail = f"Pair difference {abs(value-other):.8g}; tolerance {spec.tolerance:.8g}."
    elif spec.kind == "monotonic_pair":
        passed = value <= other + spec.tolerance if spec.expected_direction == "nondecreasing" else value >= other - spec.tolerance
        detail = f"Outputs {value:.8g} → {other:.8g}; expected {spec.expected_direction}."
    else:
        passed = (spec.minimum is None or value >= spec.minimum - spec.tolerance) and (spec.maximum is None or value <= spec.maximum + spec.tolerance)
        detail = f"Regression case output {value:.8g}; accepted range [{spec.minimum}, {spec.maximum}]."
    result = BehaviorSpecResult(spec_id=spec.spec_id, run_id=spec.run_id, model_artifact_sha256=spec.model_artifact_sha256, fis_id=spec.fis_id, fis_semantic_hash=spec.fis_semantic_hash, status="PASS" if passed else "FAIL", observed_output=value, comparison_output=other, detail=detail)
    _atomic_write_text(_root(project_root) / f"result-{result.result_id}.json", result.model_dump_json(indent=2))
    _atomic_write_text(_root(project_root) / "active-result.json", json.dumps({"result_id": str(result.result_id)}))
    return result


def load_behavior_spec(project_root: Path, spec_id: UUID) -> BehaviorSpec:
    return BehaviorSpec.model_validate_json((_root(project_root) / f"{spec_id}.json").read_text())


def list_behavior_specs(project_root: Path) -> list[BehaviorSpec]:
    root = _root(project_root)
    return sorted(
        (BehaviorSpec.model_validate_json(path.read_text()) for path in root.glob("*.json") if path.name not in {"active-spec.json", "active-result.json"} and not path.name.startswith("result-")),
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


def load_latest_behavior_result(project_root: Path) -> BehaviorSpecResult:
    pointer = json.loads((_root(project_root) / "active-result.json").read_text())
    return BehaviorSpecResult.model_validate_json((_root(project_root) / f"result-{pointer['result_id']}.json").read_text())
