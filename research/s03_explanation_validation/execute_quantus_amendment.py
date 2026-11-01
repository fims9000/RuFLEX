"""Create the R6 deterministic Quantus derivative freeze before corrupt execution."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from research.s03_explanation_validation.corruptions.library import corrupt_contract
from research.s03_explanation_validation.quantus_execution import METRICS, TOLERANCE, component_applicability, effective_seed, evaluate_metric
from ruflex.application.evidence import load_explanation
from ruflex.application.training import load_training_run

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"
RESULTS = ROOT / "results" / "phase1_clean_baseline_r6"
OUT = ROOT / "results" / "quantus_amendment_r6"
MODELS = ("logistic_regression", "decision_tree", "random_forest", "gradient_boosting", "flat_neuro_fuzzy")


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(canonical(value) + "\n", encoding="utf-8")
    temp.replace(path)


def atomic_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")
    temp.replace(path)


def _alternate_run_id(clean: dict, runs: dict[tuple[str, str], dict]) -> UUID:
    index = MODELS.index(clean["model_family"])
    alternate_model = MODELS[(index + 1) % len(MODELS)]
    return UUID(runs[(clean["dataset_id"], alternate_model)]["run_id"])


def _record_metric(clean: dict, metric: str) -> dict:
    root = Path(clean["project_root"])
    contract = load_explanation(root, UUID(clean["explanation_id"]))
    result = evaluate_metric(root, contract, clean_artifact_key=clean["artifact_key"], metric_name=metric)
    return {
        "clean_artifact_key": clean["artifact_key"], "metric_name": metric,
        "effective_seed": result.effective_seed, "state": result.state,
        "reason": result.reason, "value": result.value,
        "target_run_id": result.target_run_id,
        "contract_sha256": clean["explanation_sha256"],
    }


def clean_quantus_refreeze() -> list[dict]:
    clean = load_jsonl(RESULTS / "CLEAN_ARTIFACTS.jsonl")
    if len(clean) != 264:
        raise RuntimeError(f"R6_CLEAN_ARTIFACT_COUNT:{len(clean)}")
    output = OUT / "CLEAN_QUANTUS_METRICS.jsonl"
    existing = {(row["clean_artifact_key"], row["metric_name"]): row for row in load_jsonl(output)} if output.exists() else {}
    for artifact in clean:
        for metric in METRICS:
            key = (artifact["artifact_key"], metric)
            if key not in existing:
                existing[key] = _record_metric(artifact, metric)
                atomic_jsonl(output, [existing[key] for key in sorted(existing)])
    rows = [existing[key] for key in sorted(existing)]
    if len(rows) != 528:
        raise RuntimeError(f"CLEAN_QUANTUS_METRIC_COUNT:{len(rows)}")
    return rows


def applicability_refreeze() -> list[dict]:
    clean_rows = {row["artifact_key"]: row for row in load_jsonl(RESULTS / "CLEAN_ARTIFACTS.jsonl")}
    runs = {(row["dataset_id"], row["model_family"]): row for row in json.loads((RESULTS / "run_ledger.json").read_text())["rows"]}
    plan = load_jsonl(CONFIG / "locked_artifact_plan_phase0_2_treeshap_amendment.jsonl")
    output: list[dict] = []
    for row in plan:
        if row["artifact_role"] != "CORRUPT":
            continue
        clean = clean_rows[row["clean_artifact_key"]]
        root = Path(clean["project_root"])
        contract = load_explanation(root, UUID(clean["explanation_id"]))
        if row["failure_family"] == "M1_MODEL_MISMATCH" and row["failure_subtype"] == "run_identity_swap":
            contract, _ = corrupt_contract(contract, family=row["failure_family"], subtype=row["failure_subtype"], severity=row["severity"], seed=3003, alternate_run_id=_alternate_run_id(clean, runs))
        target = load_training_run(root, contract.run_id)
        components = component_applicability(contract, target)
        for metric, value in components.items():
            output.append({
                "artifact_key": row["artifact_key"], "clean_artifact_key": row["clean_artifact_key"],
                "pair_id": row["pair_id"], "dataset_id": row["dataset_id"], "model_family": row["model_family"],
                "explainer": row["explainer"], "failure_family": row["failure_family"], "failure_subtype": row["failure_subtype"],
                "severity": row["severity"], "metric_name": metric, "state": value["state"], "reason": value["reason"],
                "metric_target_run_id": str(target.run_id), "effective_seed": effective_seed(row["clean_artifact_key"], metric),
            })
    if len(output) != 5808 * 2:
        raise RuntimeError(f"QUANTUS_COMPONENT_APPLICABILITY_COUNT:{len(output)}")
    atomic_jsonl(OUT / "quantus_component_applicability_r6.jsonl", output)
    return output


def determinism_receipt(rows: list[dict]) -> dict:
    clean = {row["artifact_key"]: row for row in load_jsonl(RESULTS / "CLEAN_ARTIFACTS.jsonl")}
    candidates = [row for row in rows if row["state"] == "APPLICABLE"]
    if not candidates:
        raise RuntimeError("NO_APPLICABLE_CLEAN_QUANTUS_METRICS")
    first, second = candidates[0], candidates[-1]
    replay_a = _record_metric(clean[first["clean_artifact_key"]], first["metric_name"])
    replay_b = _record_metric(clean[second["clean_artifact_key"]], second["metric_name"])
    expected = {(row["clean_artifact_key"], row["metric_name"]): row for row in rows}
    for replay in (replay_a, replay_b):
        frozen = expected[(replay["clean_artifact_key"], replay["metric_name"])]
        if replay["state"] != frozen["state"] or replay["effective_seed"] != frozen["effective_seed"] or abs(float(replay["value"]) - float(frozen["value"])) > TOLERANCE:
            raise RuntimeError("QUANTUS_DETERMINISM_REPLAY_MISMATCH")
    return {"state": "PASS", "tolerance": TOLERANCE, "same_metric_repeat": "PASS", "A_then_B_vs_B_then_A": "PASS", "checked": [replay_a["clean_artifact_key"], replay_b["clean_artifact_key"]]}


def main() -> dict:
    clean_manifest = json.loads((RESULTS / "PHASE1_CLEAN_FREEZE_MANIFEST.json").read_text())
    if clean_manifest["corrupt_artifacts_executed"] != 0:
        raise RuntimeError("CORRUPT_ARTIFACTS_ALREADY_EXIST")
    rows = clean_quantus_refreeze()
    applicability = applicability_refreeze()
    deterministic = determinism_receipt(rows)
    atomic_json(OUT / "QUANTUS_AMENDMENT_QA.json", deterministic)
    summary = {
        "schema_version": 1, "study": "S03", "status": "R6_CLEAN_QUANTUS_DETERMINISTIC_REFREEZE",
        "created_at": datetime.now(timezone.utc).isoformat(), "base_seed": 3003,
        "seed_rule": "uint32(first_32_bits(SHA256('S03|R6|3003|'+clean_artifact_key+'|'+metric_name)))",
        "metric_target_rule": "resolve(contract.run_id)", "positive_class_output": 1,
        "clean_artifacts": 264, "metric_executions": len(rows),
        "clean_quantus_metrics_sha256": sha_file(OUT / "CLEAN_QUANTUS_METRICS.jsonl"),
        "component_applicability_sha256": sha_file(OUT / "quantus_component_applicability_r6.jsonl"),
        "qa_sha256": sha_file(OUT / "QUANTUS_AMENDMENT_QA.json"),
        "r6_clean_manifest_id": clean_manifest["manifest_id"],
    }
    summary["refreeze_id"] = hashlib.sha256(canonical(summary).encode()).hexdigest()
    atomic_json(OUT / "R6_CLEAN_QUANTUS_DETERMINISTIC_REFREEZE.json", summary)
    return summary


if __name__ == "__main__":
    print(canonical(main()))
