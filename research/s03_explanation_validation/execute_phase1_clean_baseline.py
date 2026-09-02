"""Execute the frozen S03 Phase 1 clean-control baseline only.

This is deliberately not the corrupt-artifact executor.  It materializes the
three locked benchmark tables, trains the 15 declared single fits, freezes the
120 validation sample identities, and persists 264 native CLEAN explanations
with their 792 validator-mode control rows.  No FinalTestEvaluation is ever
created or imported by this module.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from research.s03_explanation_validation.sample_selection import select_validation_samples
from research.s03_explanation_validation.validate_phase0_2_sample_position_amendment import validate as validate_sample_position_amendment
from ruflex.application.artifacts import ArtifactStore
from ruflex.application.datasets import (
    build_dataset_contract,
    inspect_dataset,
    persist_dataset_bytes,
    persist_dataset_contract,
    run_data_audit,
)
from ruflex.application.evidence import (
    check_explanation,
    create_gradient_shap_explanation,
    create_integrated_gradients_explanation,
    create_occlusion_explanation,
    create_permutation_shap_explanation,
    create_tree_shap_explanation,
)
from ruflex.application.training import load_training_run, train_model

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"
# R6 starts from new declared model fits after Amendments 002 and 003.  Each dataset gets one project root
# containing its five declared model runs, as frozen M1b requires an existing
# cross-family alternate run resolvable by the product.
RESULTS = ROOT / "results" / "phase1_clean_baseline_r6"
PROJECTS = ROOT / "artifacts" / "phase1_clean_projects_r6"
A01_DATA = ROOT.parent / "a01_stability_aware_review" / "artifacts" / "phase1-data" / "materialized"
A01_SPECS = ROOT.parent / "a01_stability_aware_review" / "config" / "dataset_specs.json"


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(canonical(value) + "\n", encoding="utf-8")
    temporary.replace(path)


def atomic_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def a01_dataset_specs() -> dict[str, dict]:
    return {row["canonical_dataset_id"]: row for row in read_json(A01_SPECS)["datasets"]}


def phase0_matrix() -> dict:
    return read_json(CONFIG / "matrix_phase0_2.json")


def frozen_clean_artifact_keys() -> dict[tuple[str, str, str, int], str]:
    rows = [json.loads(line) for line in (CONFIG / "locked_artifact_plan_phase0_2_treeshap_amendment.jsonl").read_text(encoding="utf-8").splitlines()]
    result = {
        (row["dataset_id"], row["model_family"], row["explainer"], int(row["sample_slot"])): row["artifact_key"]
        for row in rows if row["artifact_role"] == "CLEAN"
    }
    if len(result) != 264:
        raise RuntimeError(f"FROZEN_CLEAN_ARTIFACT_KEY_COUNT:{len(result)}")
    return result


def phase0_model_specs() -> dict:
    return read_json(CONFIG / "model_specs.json")


def project_root(dataset_id: str, model_kind: str) -> Path:
    del model_kind
    return PROJECTS / dataset_id


def record_path(name: str) -> Path:
    return RESULTS / name


def load_ledger() -> dict[str, dict]:
    path = record_path("run_ledger.json")
    if not path.exists():
        return {}
    return {row["cell_key"]: row for row in read_json(path)["rows"]}


def persist_ledger(ledger: dict[str, dict]) -> None:
    atomic_json(record_path("run_ledger.json"), {"schema_version": 1, "rows": [ledger[key] for key in sorted(ledger)]})


def load_clean_artifact_ledger() -> dict[str, dict]:
    path = record_path("clean_artifact_ledger.json")
    if not path.exists(): return {}
    return {row["artifact_key"]: row for row in read_json(path)["rows"]}


def persist_clean_artifact_ledger(ledger: dict[str, dict]) -> None:
    atomic_json(record_path("clean_artifact_ledger.json"), {"schema_version": 1, "rows": [ledger[key] for key in sorted(ledger)]})


def materialize_project(dataset_id: str) -> tuple[pd.DataFrame, dict, Path]:
    specs = a01_dataset_specs()
    spec = specs[dataset_id]
    source = A01_DATA / dataset_id / "canonical.csv"
    if not source.exists():
        raise RuntimeError(f"MISSING_FROZEN_MATERIALIZED_DATASET:{dataset_id}")
    source_bytes = source.read_bytes()
    if sha_bytes(source_bytes) != spec["materialized_table_sha256"]:
        raise RuntimeError(f"MATERIALIZED_TABLE_SHA256_MISMATCH:{dataset_id}")
    frame = pd.read_csv(source)
    expected_columns = list(spec["row_identity"]) + list(spec["feature_columns"]) + [spec["target"]]
    if list(frame.columns) != expected_columns:
        raise RuntimeError(f"FROZEN_FEATURE_ORDER_MISMATCH:{dataset_id}")
    if len(frame) < 8:
        raise RuntimeError(f"DATASET_LT_EIGHT_ROWS:{dataset_id}")
    return frame, spec, source


def initialize_project(dataset_id: str, model_kind: str, frame: pd.DataFrame, spec: dict, source: Path) -> Path:
    root = project_root(dataset_id, model_kind)
    marker = root / "data" / "dataset-contract.json"
    if marker.exists():
        return root
    root.mkdir(parents=True, exist_ok=True)
    artifact = persist_dataset_bytes(root, source.read_bytes(), original_name="canonical.csv")
    profile = inspect_dataset(frame, source_artifact_sha256=artifact.sha256)
    contract = build_dataset_contract(
        profile,
        target=spec["target"],
        task="binary_classification",
        id_columns=list(spec["row_identity"]),
        source_format="csv",
    )
    if contract.feature_columns != spec["feature_columns"]:
        raise RuntimeError(f"DATASET_CONTRACT_FEATURE_ORDER_MISMATCH:{dataset_id}")
    persist_dataset_contract(root, contract, run_data_audit(contract, frame), profile)
    return root


def frozen_training_kwargs(model_kind: str, model_specs: dict) -> dict:
    common = model_specs
    kwargs = {
        "seed": None,
        "split_seed": int(common["split_seed"]),
        "training_seed": int(common["training_seed"]),
        "validation_fraction": float(common["split_fractions"]["validation"]),
        "test_fraction": float(common["split_fractions"]["final_test"]),
    }
    model = common["models"][model_kind]
    if model_kind == "flat_neuro_fuzzy":
        kwargs.update({key: model[key] for key in ("max_epochs", "learning_rate", "batch_size", "patience", "max_rules")})
    elif model_kind == "gradient_boosting":
        # The product dispatcher currently exposes the frozen learning-rate
        # argument; the remaining values are source- and environment-locked
        # product defaults also materialized in model_specs.json.
        kwargs["learning_rate"] = model["learning_rate"]
    return kwargs


def train_or_verify(dataset_id: str, model_kind: str, frame: pd.DataFrame, spec: dict, source: Path, ledger: dict[str, dict]) -> dict:
    key = f"{dataset_id}/{model_kind}"
    root = initialize_project(dataset_id, model_kind, frame, spec, source)
    existing = ledger.get(key)
    if existing and existing["status"] == "SUCCEEDED":
        run = load_training_run(root, __import__("uuid").UUID(existing["run_id"]))
        if run.model_artifact_sha256 != existing["model_artifact_sha256"] or not ArtifactStore(root).verify(__import__("ruflex.application.artifacts", fromlist=["ArtifactRef"]).ArtifactRef(sha256=run.model_artifact_sha256)).valid:
            raise RuntimeError(f"SUCCEEDED_RUN_ARTIFACT_MISMATCH:{key}")
        return existing
    # A process interruption can leave only a RUNNING ledger marker.  It does
    # not authorize reuse of a partial fit; the declared cell is re-run with
    # the same frozen seed and provenance.
    if existing and existing["status"] == "RUNNING":
        existing["status"] = "PENDING_AFTER_INTERRUPTION"
        existing["interruption_reason"] = "PROCESS_INTERRUPTED_BEFORE_PERSISTED_SUCCESS"
        ledger[key] = existing
        persist_ledger(ledger)
    row = {"cell_key": key, "dataset_id": dataset_id, "model_family": model_kind, "project_root": str(root), "status": "RUNNING"}
    ledger[key] = row
    persist_ledger(ledger)
    try:
        run = train_model(root, model_kind=model_kind, **frozen_training_kwargs(model_kind, phase0_model_specs()))
        if run.split_seed != 3003 or run.training_seed != 3003 or run.split.test_status != "LOCKED_NOT_EVALUATED":
            raise RuntimeError(f"FROZEN_RUN_PROVENANCE_MISMATCH:{key}")
        if run.feature_columns != spec["feature_columns"]:
            raise RuntimeError(f"FROZEN_RUN_FEATURE_ORDER_MISMATCH:{key}")
        if not ArtifactStore(root).verify(__import__("ruflex.application.artifacts", fromlist=["ArtifactRef"]).ArtifactRef(sha256=run.model_artifact_sha256)).valid:
            raise RuntimeError(f"MODEL_ARTIFACT_VERIFY_FAILED:{key}")
        row.update({"status": "SUCCEEDED", "run_id": str(run.run_id), "model_artifact_sha256": run.model_artifact_sha256, "validation_metrics": run.validation_metrics, "split_identity": run.split.split_identity, "preprocessing_identity": hashlib.sha256(canonical(run.normalization).encode()).hexdigest(), "finished_at": datetime.now(timezone.utc).isoformat()})
    except Exception as error:
        row.update({"status": "FAILED", "error": f"{type(error).__name__}:{error}", "finished_at": datetime.now(timezone.utc).isoformat()})
        ledger[key] = row
        persist_ledger(ledger)
        raise
    ledger[key] = row
    persist_ledger(ledger)
    return row


def prediction_rows(run) -> list[dict]:
    rows = []
    for prediction in run.prediction_preview:
        if prediction.source_row is None or prediction.probability is None or prediction.predicted_label is None:
            raise RuntimeError("VALIDATION_PREDICTION_EVIDENCE_INCOMPLETE")
        rows.append({"source_row": int(prediction.source_row), "truth": int(prediction.target), "prediction": int(prediction.predicted_label), "raw_prediction": float(prediction.prediction), "probability": float(prediction.probability)})
    return rows


def frozen_samples(ledger: dict[str, dict]) -> list[dict]:
    frozen = record_path("FROZEN_SAMPLE_SELECTION.json")
    if frozen.exists():
        rows = read_json(frozen)["selection"]
        if len(rows) != 120: raise RuntimeError("FROZEN_SAMPLE_SELECTION_CORRUPT")
        return rows
    rows = []
    for key in sorted(ledger):
        entry = ledger[key]
        root = Path(entry["project_root"])
        run = load_training_run(root, __import__("uuid").UUID(entry["run_id"]))
        chosen = select_validation_samples(prediction_rows(run), required=8)
        for slot, prediction in enumerate(chosen):
            sample_identity = hashlib.sha256(canonical({"dataset_id": entry["dataset_id"], "model_family": entry["model_family"], "run_id": entry["run_id"], "source_row": prediction["source_row"]}).encode()).hexdigest()
            rows.append({**entry, "sample_slot": slot, "sample_identity": sample_identity, **prediction})
    if len(rows) != 120:
        raise RuntimeError(f"FROZEN_SAMPLE_SELECTION_COUNT:{len(rows)}")
    atomic_json(frozen, {"schema_version": 1, "selection": rows})
    return rows


def sample_from_source(frame: pd.DataFrame, source_row: int, feature_columns: list[str]) -> dict[str, float]:
    """Resolve the product-native persisted validation table position fail-closed."""
    if int(source_row) < 0 or int(source_row) >= len(frame):
        raise RuntimeError(f"SOURCE_ROW_POSITION_UNRESOLVABLE:{source_row}")
    record = frame.iloc[int(source_row)]
    return {name: float(record[name]) for name in feature_columns}


def create_clean_explanation(root: Path, run_id, explainer: str, sample: dict[str, float]):
    if explainer == "occlusion": return create_occlusion_explanation(root, run_id, sample)
    if explainer == "integrated_gradients": return create_integrated_gradients_explanation(root, run_id, sample, steps=64)
    if explainer == "gradient_shap": return create_gradient_shap_explanation(root, run_id, sample, background_count=24)
    if explainer == "permutation_shap": return create_permutation_shap_explanation(root, run_id, sample, background_count=24)
    if explainer == "tree_shap": return create_tree_shap_explanation(root, run_id, sample, background_count=32)
    raise RuntimeError(f"UNKNOWN_EXPLAINER:{explainer}")


def clean_controls(samples: list[dict]) -> tuple[list[dict], list[dict]]:
    matrix = phase0_matrix()
    specs = a01_dataset_specs()
    frames = {dataset: pd.read_csv(A01_DATA / dataset / "canonical.csv") for dataset in matrix["datasets"]}
    artifact_keys = frozen_clean_artifact_keys()
    artifact_ledger = load_clean_artifact_ledger()
    evaluations: list[dict] = []
    for sample_row in samples:
        dataset, model = sample_row["dataset_id"], sample_row["model_family"]
        root = Path(sample_row["project_root"])
        run = load_training_run(root, __import__("uuid").UUID(sample_row["run_id"]))
        sample = sample_from_source(frames[dataset], sample_row["source_row"], run.feature_columns)
        if int(frames[dataset].iloc[int(sample_row["source_row"])][specs[dataset]["target"]]) != int(sample_row["truth"]):
            raise RuntimeError(f"SOURCE_ROW_POSITION_TRUTH_MISMATCH:{dataset}:{sample_row['source_row']}")
        for explainer in matrix["models"][model]:
            artifact_key = artifact_keys[(dataset, model, explainer, int(sample_row["sample_slot"]))]
            existing = artifact_ledger.get(artifact_key)
            if existing is not None:
                explanation_path = root / "evidence" / "explanations" / f"{existing['explanation_id']}.json"
                if not explanation_path.exists() or sha_file(explanation_path) != existing["explanation_sha256"]:
                    raise RuntimeError(f"CLEAN_ARTIFACT_LEDGER_INTEGRITY_FAILURE:{artifact_key}")
                artifact = existing
            else:
                explanation = create_clean_explanation(root, run.run_id, explainer, sample)
                check = check_explanation(root, explanation.explanation_id)
                artifact = {"artifact_key": artifact_key, "artifact_role": "CLEAN", "dataset_id": dataset, "model_family": model, "explainer": explainer, "sample_slot": sample_row["sample_slot"], "sample_identity": sample_row["sample_identity"], "project_root": str(root), "run_id": sample_row["run_id"], "explanation_id": str(explanation.explanation_id), "explanation_sha256": sha_file(root / "evidence" / "explanations" / f"{explanation.explanation_id}.json"), "check_id": str(check.check_id), "check_status": check.status, "check_items": [item.model_dump(mode="json") for item in check.checks]}
                artifact_ledger[artifact_key] = artifact
                persist_clean_artifact_ledger(artifact_ledger)
            for mode in matrix["validator_modes"]:
                # Quantus has only a paired corrupt-vs-clean rule; it cannot
                # reject a clean control in isolation.  Numerical WARN is
                # descriptive-only by the frozen Phase 0.2 validator spec.
                rejected = any(item["status"] == "FAIL" for item in artifact["check_items"])
                evaluations.append({**artifact, "validator_mode": mode, "execution_id": hashlib.sha256(canonical({"artifact_key":artifact_key,"mode":mode}).encode()).hexdigest()[:24], "rejected_clean": rejected, "quantus_clean_decision": "NOT_APPLICABLE_UNPAIRED_CONTROL", "numerical_warn_is_detector": False})
    artifacts = [artifact_ledger[key] for key in sorted(artifact_ledger)]
    if len(artifacts) != 264 or len(evaluations) != 792:
        raise RuntimeError(f"CLEAN_BASELINE_COUNT_MISMATCH:{len(artifacts)}/{len(evaluations)}")
    return artifacts, evaluations


def require_no_final_tests() -> None:
    for root in PROJECTS.glob("*"):
        final_root = root / "analyses" / "final-tests"
        if final_root.exists() and list(final_root.glob("*.json")):
            raise RuntimeError(f"S03_FINAL_TEST_ARTIFACT_FORBIDDEN:{root}")


def freeze(ledger: dict[str, dict], samples: list[dict], artifacts: list[dict], evaluations: list[dict]) -> dict:
    atomic_jsonl(record_path("CLEAN_ARTIFACTS.jsonl"), artifacts)
    atomic_jsonl(record_path("CLEAN_EVALUATIONS.jsonl"), evaluations)
    atomic_json(record_path("T01_clean_run_completion.json"), {"declared_runs": 15, "succeeded_runs": sum(row["status"] == "SUCCEEDED" for row in ledger.values()), "failed_runs": sum(row["status"] == "FAILED" for row in ledger.values())})
    atomic_json(record_path("T02_clean_false_rejection.json"), {"clean_controls": len(evaluations), "rejected_clean": sum(row["rejected_clean"] for row in evaluations), "clean_false_rejection_rate": sum(row["rejected_clean"] for row in evaluations) / len(evaluations)})
    payload = {"schema_version": 1, "study": "S03", "status": "PHASE1_CLEAN_BASELINE_FROZEN_CORRUPT_EXECUTION_NOT_STARTED", "phase0_2_treeshap_amendment_manifest_id": read_json(CONFIG / "phase0_2_treeshap_amendment_manifest.json")["manifest_id"], "run_ledger_sha256": sha_file(record_path("run_ledger.json")), "sample_selection_sha256": sha_file(record_path("FROZEN_SAMPLE_SELECTION.json")), "clean_artifacts_sha256": sha_file(record_path("CLEAN_ARTIFACTS.jsonl")), "clean_evaluations_sha256": sha_file(record_path("CLEAN_EVALUATIONS.jsonl")), "declared_models": 15, "sample_slots": 120, "clean_artifacts": 264, "clean_evaluations": 792, "final_test_accessed": False, "corrupt_artifacts_executed": 0, "created_at": datetime.now(timezone.utc).isoformat()}
    payload["manifest_id"] = hashlib.sha256(canonical(payload).encode()).hexdigest()
    atomic_json(record_path("PHASE1_CLEAN_FREEZE_MANIFEST.json"), payload)
    return payload


def main() -> dict:
    validate_sample_position_amendment()
    if RESULTS.exists() and (record_path("PHASE1_CLEAN_FREEZE_MANIFEST.json")).exists():
        raise RuntimeError("PHASE1_CLEAN_BASELINE_ALREADY_FROZEN")
    matrix = phase0_matrix()
    ledger = load_ledger()
    for dataset in matrix["datasets"]:
        frame, spec, source = materialize_project(dataset)
        for model_kind in matrix["models"]:
            train_or_verify(dataset, model_kind, frame, spec, source, ledger)
    if len(ledger) != 15 or any(row["status"] != "SUCCEEDED" for row in ledger.values()):
        raise RuntimeError("S03_PHASE1_DECLARED_MODEL_SUPPORT_INCOMPLETE")
    samples = frozen_samples(ledger)
    artifacts, evaluations = clean_controls(samples)
    require_no_final_tests()
    return freeze(ledger, samples, artifacts, evaluations)


if __name__ == "__main__":
    print(canonical(main()))
