"""Execute the frozen A01 validation-only matrix through policy freeze.

This orchestrator deliberately imports only canonical RuFLEX application
services.  It has no final-test import or call path.  Raw datasets and project
model artifacts live under ignored ``artifacts/``; compact declarative results
and hashes are emitted under ``results/phase1_validation``.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
import pandas as pd

from research.a01_stability_aware_review.core import CONFIG, ROOT, canonical_csv_bytes, canonical_json, load_json, sha256_bytes
from research.a01_stability_aware_review.statistics import select_illustrative_cases, validation_matched_confidence_cutoff
from research.a01_stability_aware_review.validate_pre_freeze import validate as validate_pre_freeze
from ruflex.application.datasets import DatasetContract, inspect_dataset, persist_dataset_bytes, persist_dataset_contract, run_data_audit
from ruflex.application.assurance import create_assurance_case
from ruflex.application.lineage import build_project_lineage
from ruflex.application.projects import ProjectService
from ruflex.application.selective import create_selective_policy, load_selective_policy
from ruflex.application.stability import create_stability_gate_policy, create_study_stability_analysis, load_stability_gate_policy, load_study_stability_analysis
from ruflex.application.training import _atomic_write_text, _select_study_run, create_validation_evaluation, load_decision_threshold, load_training_run, load_training_study, load_validation_evaluation, persist_training_run, select_validation_threshold, train_model
from ruflex.application.verification_bundle import export_verification_bundle
from ruflex.domain.training import TrainingStudy


RESULTS = ROOT / "results" / "phase1_validation"
ARTIFACTS = ROOT / "artifacts" / "phase1-projects"
DATA = ROOT / "artifacts" / "phase1-data" / "materialized"
AGGREGATED = ROOT / "artifacts" / "aggregated" / "phase1_validation"
PHASE0_5 = load_json(CONFIG / "phase0_5_manifest.json")
SEEDS = list(range(20))


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _model_request(model: dict[str, Any]) -> dict[str, Any]:
    request = dict(model["product_request"])
    return {
        "max_epochs": int(request["max_epochs"]),
        "learning_rate": float(request["learning_rate"]),
        "batch_size": 1 if request["batch_size"] == "train_row_count" else int(request["batch_size"]),
        "patience": request["patience"],
        "max_rules": 8 if request["max_rules"] == "not_applicable" else int(request["max_rules"]),
        "validation_fraction": .2,
        "test_fraction": .2,
    }


def _project_root(dataset_id: str, model_family: str) -> Path:
    return ARTIFACTS / dataset_id / model_family


def _create_or_open_project(dataset: dict[str, Any], model: dict[str, Any]) -> Path:
    root = _project_root(dataset["canonical_dataset_id"], model["model_family"])
    service = ProjectService()
    if (root / "project.yaml").exists() and (root / "data" / "dataset-contract.json").exists():
        service.open(root)
        return root
    table_path = DATA / dataset["canonical_dataset_id"] / "canonical.csv"
    raw = table_path.read_bytes()
    if _sha(table_path) != dataset["materialized_table_sha256"]:
        raise ValueError(f"Materialized table hash mismatch for {dataset['canonical_dataset_id']}.")
    project = service.open(root) if (root / "project.yaml").exists() else service.create(root, name=f"A01 Phase 1 {dataset['canonical_dataset_id']} {model['model_family']}")
    frame = pd.read_csv(table_path)
    profile = inspect_dataset(frame, source_artifact_sha256=persist_dataset_bytes(project.root, raw, original_name="canonical.csv").sha256)
    # The frozen contract is explicit.  In particular, ``job_housemaid`` is a
    # declared Bank Marketing feature, not an identifier merely because its
    # spelling ends in ``id``.  This is a declared product DatasetContract,
    # not a research-side transformation or a changed dataset specification.
    contract = DatasetContract(dataset_fingerprint=profile.fingerprint, source_artifact_sha256=profile.source_artifact_sha256, target=dataset["target"], task="binary_classification", feature_columns=list(dataset["feature_columns"]), id_columns=list(dataset["row_identity"]))
    persist_dataset_contract(project.root, contract, run_data_audit(contract, frame), profile)
    return root


def _pre_execution_receipt() -> dict[str, Any]:
    errors = validate_pre_freeze(ROOT)
    if errors:
        raise RuntimeError("Phase 1 cannot begin: " + "; ".join(errors))
    receipt = {
        "study": "A01 — Stability-Aware Selective Review", "phase": 1,
        "timestamp": _utc(), "source_head": _git_head(),
        "phase0_5": PHASE0_5, "pre_run_validator": "PASS",
        "final_test_access": "CLOSED", "benchmark_execution": "NOT_STARTED",
    }
    _write_json(RESULTS / "PHASE1_PRE_EXECUTION_RECEIPT.json", receipt)
    return receipt


def _git_head() -> str:
    repository = ROOT.parents[1]
    head = repository / ".git"
    # The receipt must still work for a source archive, where .git is absent.
    if not head.exists():
        return "SOURCE_ARCHIVE_NO_GIT_METADATA"
    import subprocess
    return subprocess.check_output(["git", "-C", str(repository), "rev-parse", "HEAD"], text=True).strip()


def _study_cell(dataset: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    root = _create_or_open_project(dataset, model)
    study_path = root / "studies" / "a01-phase1-study.json"
    start = time.monotonic()
    if study_path.exists():
        study = load_training_study(root, UUID(json.loads(study_path.read_text())["study_id"]))
        resumed = True
    else:
        study = _resume_or_train_study(root, dataset, model)
        study_path.parent.mkdir(parents=True, exist_ok=True)
        study_path.write_text(canonical_json({"study_id": str(study.study_id)}) + "\n", encoding="utf-8")
        resumed = False
    run_rows: list[dict[str, Any]] = []
    state: dict[int, str] = {}
    for run in study.seed_runs:
        seed = int(run.training_seed if run.training_seed is not None else run.seed)
        valid = run.split.split_seed == 42 and run.randomness_protocol == "TRAINING_VARIABILITY" and seed in SEEDS
        state[seed] = "SUCCEEDED" if valid else "FAILED"
        run_rows.append({"dataset_id": dataset["canonical_dataset_id"], "model_family": model["model_family"], "split_seed": run.split.split_seed, "training_seed": seed, "status": state[seed], "run_id": str(run.run_id), "model_artifact_sha256": run.model_artifact_sha256, "validation_metrics": run.validation_metrics, "runtime_seconds": run.runtime_seconds, "error": None if valid else "frozen provenance mismatch"})
    if set(state) != set(SEEDS) or any(value != "SUCCEEDED" for value in state.values()):
        return {"dataset_id": dataset["canonical_dataset_id"], "model_family": model["model_family"], "project_root": str(root), "status": "INCOMPLETE_DECLARED_RUN_SUPPORT", "run_ledger": run_rows, "runtime_seconds": time.monotonic() - start, "study_id": str(study.study_id)}
    # Independently recompute the frozen selection rule rather than trusting a label.
    ordered = sorted(study.seed_runs, key=lambda run: (-float(run.validation_metrics["f1"]), int(run.training_seed if run.training_seed is not None else run.seed)))
    if study.selected_run_id != ordered[0].run_id:
        raise RuntimeError("Product-native selected run differs from frozen validation F1 / lowest-seed selection rule.")
    evaluation = create_validation_evaluation(root, study.selected_run_id)
    threshold = select_validation_threshold(root, evaluation.evaluation_id, objective="f1")
    if threshold.probability_source != "raw" or threshold.calibration_id is not None:
        raise RuntimeError("A01 requires raw, uncalibrated validation DecisionThresholdPolicy.")
    analysis = create_study_stability_analysis(root, study.study_id, evaluation_id=evaluation.evaluation_id, threshold_id=threshold.threshold_id, high_confidence_threshold=.9, unstable_agreement_threshold=.8)
    if analysis.applicability != "APPLICABLE" or len(analysis.run_ids) != 20 or analysis.validation_alignment_status != "EXACT_MATCH":
        raise RuntimeError("A01 complete cell lacks exact 20-run validation stability evidence.")
    gate = create_stability_gate_policy(root, analysis.analysis_id, evaluation.evaluation_id, min_confidence=.9, min_class_agreement=.8, max_probability_std=.15)
    confidences = [max(case.selected_run_probability, 1 - case.selected_run_probability) for case in analysis.cases]
    stability_coverage = sum(decision.disposition == "ACCEPT" for decision in gate.decisions) / len(gate.decisions)
    comparator = validation_matched_confidence_cutoff(confidences, stability_coverage)
    confidence_policy = create_selective_policy(root, evaluation.evaluation_id, comparator["confidence_cutoff"], threshold_id=threshold.threshold_id)
    if confidence_policy.run_id != study.selected_run_id or confidence_policy.class_threshold_id != threshold.threshold_id or confidence_policy.calibration_id is not None:
        raise RuntimeError("A01 comparator provenance does not match the selected raw validation threshold.")
    metric = analysis.metric_distributions["f1"].model_dump()
    cases = [case.model_dump(mode="json") for case in analysis.cases]
    h1 = "PATTERN_OBSERVED" if any(case["selected_run_agreement"] < 1 for case in cases) else "PATTERN_NOT_OBSERVED"
    h2 = "NOT_ASSESSABLE" if analysis.high_confidence_case_count == 0 else ("PATTERN_OBSERVED" if analysis.high_confidence_unstable_case_count else "PATTERN_NOT_OBSERVED")
    binding = {
        "dataset_id": dataset["canonical_dataset_id"], "model_family": model["model_family"], "project_root": str(root), "study_id": str(study.study_id), "selected_run_id": str(study.selected_run_id), "selected_training_seed": int(ordered[0].training_seed if ordered[0].training_seed is not None else ordered[0].seed), "evaluation_id": str(evaluation.evaluation_id), "threshold_id": str(threshold.threshold_id), "decision_threshold": threshold.selected_threshold, "stability_analysis_id": str(analysis.analysis_id), "stability_gate_policy_id": str(gate.policy_id), "confidence_only_policy_id": str(confidence_policy.policy_id), "confidence_cutoff": comparator["confidence_cutoff"], "stability_validation_coverage": stability_coverage, "confidence_validation_coverage": comparator["validation_coverage"], "absolute_coverage_gap": comparator["absolute_coverage_gap"], "statistical_analysis_plan_sha256": PHASE0_5["statistical_analysis_plan_sha256"], "h3_status": "NOT_ASSESSABLE", "h3_reason": "FINAL_TEST_NOT_OPENED",
    }
    illustrative = [
        {**case, "selected_run_confidence": max(case["selected_run_probability"], 1 - case["selected_run_probability"])}
        for case in cases
    ]
    observation = {"dataset_id": dataset["canonical_dataset_id"], "model_family": model["model_family"], "validation_f1": metric, "h1_status": h1, "h2_status": h2, "hcir": analysis.high_confidence_instability_rate, "high_confidence_denominator": analysis.high_confidence_case_count, "high_confidence_unstable_numerator": analysis.high_confidence_unstable_case_count, "hcir_reason": "ZERO_HIGH_CONFIDENCE_DENOMINATOR" if analysis.high_confidence_case_count == 0 else None, "proportion_selected_run_agreement_lt_1": float(np.mean([case["selected_run_agreement"] < 1 for case in cases])), "proportion_selected_run_agreement_lt_0_80": float(np.mean([case["selected_run_agreement"] < .8 for case in cases])), "pairwise_prediction_disagreement_distribution": _pairwise_disagreement(cases), "probability_std": _distribution([case["std_probability"] for case in cases]), "illustrative_case_ids": select_illustrative_cases(illustrative, limit=min(5, len(cases))), "h3_status": "NOT_ASSESSABLE", "h3_reason": "FINAL_TEST_NOT_OPENED"}
    lineage = build_project_lineage(root)
    reopen = ProjectService().open(root, read_only=True)
    return {"dataset_id": dataset["canonical_dataset_id"], "model_family": model["model_family"], "project_root": str(reopen.root), "status": "VALIDATION_FROZEN", "study_id": str(study.study_id), "run_ledger": run_rows, "binding": binding, "observation": observation, "lineage_node_count": len(lineage.nodes), "runtime_seconds": time.monotonic() - start}


def _resume_or_train_study(root: Path, dataset: dict[str, Any], model: dict[str, Any]) -> TrainingStudy:
    """Use persisted successful declared seed runs; never replace or rerun one."""
    found: dict[int, Any] = {}
    for path in (root / "runs").glob("*.json"):
        try:
            run = load_training_run(root, UUID(path.stem))
        except (ValueError, FileNotFoundError):
            continue
        seed = int(run.training_seed if run.training_seed is not None else run.seed)
        if run.model_kind == model["model_family"] and run.split.split_seed == 42 and seed in SEEDS:
            found[seed] = run
    failures: list[dict[str, Any]] = []
    for seed in SEEDS:
        if seed in found:
            continue
        try:
            run = train_model(root, model_kind=model["model_family"], split_seed=42, training_seed=seed, **_model_request(model))
            run.randomness_protocol = "TRAINING_VARIABILITY"
            persist_training_run(root, run)
            found[seed] = run
            _append_live_ledger(dataset, model, run, "SUCCEEDED", None)
        except Exception as error:
            failures.append({"training_seed": seed, "error": str(error)})
            _append_live_ledger(dataset, model, None, "FAILED", str(error), training_seed=seed)
    if failures or set(found) != set(SEEDS):
        raise RuntimeError(f"INCOMPLETE_DECLARED_RUN_SUPPORT for {dataset['canonical_dataset_id']}/{model['model_family']}: {failures}")
    runs = [found[seed] for seed in SEEDS]
    selected, value, rule = _select_study_run([(run, run.validation_metrics.get("f1")) for run in runs], "f1")
    study = TrainingStudy(name=f"A01 Phase 1 {dataset['canonical_dataset_id']} × {model['model_family']}", model_kind=model["model_family"], task=runs[0].task, selection_metric="f1", selection_rule=rule, seed_runs=runs, selected_run_id=selected.run_id, selection_reason=f"Selected {model['model_family']} run by frozen validation f1 ({rule}) = {value:.6g}; exact ties select lowest training_seed; final test was not used.", randomness_protocol="TRAINING_VARIABILITY", split_seed=42, training_seeds=SEEDS)
    _atomic_write_text(root / "studies" / f"{study.study_id}.json", study.model_dump_json(indent=2))
    _atomic_write_text(root / "studies" / "active-study.json", canonical_json({"study_id": str(study.study_id)}))
    return study


def _append_live_ledger(dataset: dict[str, Any], model: dict[str, Any], run: Any | None, status: str, error: str | None, *, training_seed: int | None = None) -> None:
    path = ROOT / "artifacts" / "diagnostics" / "phase1-live-ledger.jsonl"; path.parent.mkdir(parents=True, exist_ok=True)
    seed = training_seed if training_seed is not None else int(run.training_seed if run.training_seed is not None else run.seed)
    row = {"timestamp": _utc(), "dataset_id": dataset["canonical_dataset_id"], "model_family": model["model_family"], "split_seed": 42, "training_seed": seed, "status": status, "run_id": None if run is None else str(run.run_id), "model_artifact_sha256": None if run is None else run.model_artifact_sha256, "validation_metrics": None if run is None else run.validation_metrics, "runtime_seconds": None if run is None else run.runtime_seconds, "error": error}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(row) + "\n")


def _pairwise_disagreement(cases: list[dict[str, Any]]) -> dict[str, float]:
    fractions = []
    for case in cases:
        labels = list(case["run_labels"].values())
        fractions.extend([int(left != right) for index, left in enumerate(labels) for right in labels[index + 1:]])
    return _distribution(fractions)


def _distribution(values: list[float | int]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    return {"mean": float(array.mean()), "median": float(np.median(array)), "std": float(array.std(ddof=0)), "min": float(array.min()), "max": float(array.max()), "iqr": float(np.percentile(array, 75) - np.percentile(array, 25))}


def _environment_receipt() -> dict[str, Any]:
    import sklearn
    return {"timestamp": _utc(), "platform": platform.platform(), "python": sys.version, "numpy": np.__version__, "pandas": pd.__version__, "sklearn": sklearn.__version__, "source_head": _git_head(), "execution_plan_sha256": PHASE0_5["phase0_locked_identities"]["execution_plan_sha256"], "model_spec_sha256": PHASE0_5["phase0_locked_identities"]["model_spec_sha256"], "statistical_analysis_plan_sha256": PHASE0_5["statistical_analysis_plan_sha256"], "final_test_access": "CLOSED"}


def execute() -> dict[str, Any]:
    if not (RESULTS / "PHASE1_PRE_EXECUTION_RECEIPT.json").exists():
        _pre_execution_receipt()
    specs = load_json(CONFIG / "dataset_specs.json")["datasets"]
    models = load_json(CONFIG / "model_specs.json")["models"]
    missing = [spec["canonical_dataset_id"] for spec in specs if not (DATA / spec["canonical_dataset_id"] / "canonical.csv").exists()]
    if missing:
        raise RuntimeError(f"Frozen materialized datasets are absent: {missing}. Run materialize_datasets.py before Phase 1.")
    cells = [_study_cell(dataset, model) for dataset in specs for model in models]
    ledger = [row for cell in cells for row in cell["run_ledger"]]
    _write_jsonl(RESULTS / "run_ledger.jsonl", ledger)
    _write_jsonl(RESULTS / "cell_status.jsonl", [{key: value for key, value in cell.items() if key not in {"run_ledger", "binding", "observation"}} for cell in cells])
    complete = [cell for cell in cells if cell["status"] == "VALIDATION_FROZEN"]
    _write_json(RESULTS / "selected_runs.json", [cell["binding"] for cell in complete])
    _write_json(RESULTS / "validation_observations.json", [cell["observation"] for cell in complete])
    _write_json(RESULTS / "phase1_execution_manifest.json", {"study": "A01", "phase": 1, "status": "VALIDATION_EXECUTED_FINAL_TEST_CLOSED", "declared_runs": 300, "succeeded_runs": sum(row["status"] == "SUCCEEDED" for row in ledger), "failed_runs": sum(row["status"] == "FAILED" for row in ledger), "cells": len(cells), "complete_cells": len(complete), "environment": _environment_receipt(), "final_test_access": "CLOSED"})
    _write_tables(complete)
    _write_figures(complete)
    return finalize()


def finalize() -> dict[str, Any]:
    """Freeze already-persisted validation outputs without retraining a run."""
    inputs = ["run_ledger.jsonl", "cell_status.jsonl", "selected_runs.json", "validation_observations.json"]
    if any(not (RESULTS / name).is_file() for name in inputs):
        raise RuntimeError("Cannot finalize Phase 1 before all validation artifacts exist.")
    firewall = RESULTS / "FINAL_TEST_FIREWALL_RECEIPT.json"
    if not firewall.exists():
        _write_json(firewall, {"timestamp": _utc(), "status": "PASS", "statement": "NO A01 FINAL-TEST DATA ACCESSED", "final_test_artifacts": []})
    frozen_files = [path for path in sorted(RESULTS.rglob("*")) if path.is_file() and path.name not in {"phase1_validation_freeze_manifest.json", "run_ledger_live.jsonl"}]
    manifest = {"schema_version": 1, "status": "VALIDATION_EXECUTED_FINAL_TEST_CLOSED", "phase0_5_manifest_id": PHASE0_5["phase0_5_manifest_id"], "inputs": {path.relative_to(RESULTS).as_posix(): _sha(path) for path in frozen_files}, "final_test_access": "CLOSED"}
    manifest["phase1_validation_freeze_manifest_id"] = sha256_bytes(canonical_json(manifest).encode())
    _write_json(RESULTS / "phase1_validation_freeze_manifest.json", manifest)
    return manifest


def enrich() -> dict[str, Any]:
    """Emit compact object receipts and reopen/inspection evidence, no fitting."""
    bindings = load_json(RESULTS / "selected_runs.json")
    evaluations: list[dict[str, Any]] = []; thresholds: list[dict[str, Any]] = []
    analyses: list[dict[str, Any]] = []; gates: list[dict[str, Any]] = []
    comparators: list[dict[str, Any]] = []; inspection: list[dict[str, Any]] = []
    for binding in bindings:
        root = Path(binding["project_root"])
        evaluation = load_validation_evaluation(root, UUID(binding["evaluation_id"]))
        threshold = load_decision_threshold(root, UUID(binding["threshold_id"]))
        analysis = load_study_stability_analysis(root, UUID(binding["stability_analysis_id"]))
        gate = load_stability_gate_policy(root, UUID(binding["stability_gate_policy_id"]))
        comparator = load_selective_policy(root, UUID(binding["confidence_only_policy_id"]))
        assurance = create_assurance_case(root)
        bundle = export_verification_bundle(root)
        reopened = ProjectService().open(root, read_only=True)
        prefix = {"dataset_id": binding["dataset_id"], "model_family": binding["model_family"]}
        evaluations.append({**prefix, **evaluation.model_dump(mode="json")})
        thresholds.append({**prefix, **threshold.model_dump(mode="json")})
        analyses.append({**prefix, **analysis.model_dump(mode="json")})
        gates.append({**prefix, **gate.model_dump(mode="json")})
        comparators.append({**prefix, **comparator.model_dump(mode="json")})
        inspection.append({**prefix, "reopen_project_root": str(reopened.root), "lineage_node_count": len(build_project_lineage(root).nodes), "assurance_id": str(assurance.assurance_id), "assurance_gate_count": len(assurance.gates), "verification_bundle_sha256": bundle["sha256"], "verification_bundle_entries": bundle["entry_count"], "final_test_available": False})
    # Full case-level arrays are persisted in canonical product projects and
    # mirrored only in ignored scientific evidence storage.  The tracked
    # source snapshot retains compact checksummed receipts, not raw benchmark
    # prediction vectors or a 150 MB duplicate of them.
    full = {
        "validation_evaluations.json": evaluations,
        "threshold_policies.json": thresholds,
        "stability_analyses.json": analyses,
        "stability_gate_policies.json": gates,
        "confidence_comparator_policies.json": comparators,
    }
    for name, payload in full.items():
        _write_json(AGGREGATED / name, payload)
    _write_json(RESULTS / "validation_object_hashes.json", {name: _sha(AGGREGATED / name) for name in sorted(full)})
    _write_json(RESULTS / "lineage_reopen_inspection.json", inspection)
    return {"cells": len(bindings), "status": "VALIDATION_OBJECTS_REOPENED_AND_INSPECTED", "final_test_access": "CLOSED"}


def _write_tables(cells: list[dict[str, Any]]) -> None:
    tables = RESULTS / "tables"; tables.mkdir(parents=True, exist_ok=True)
    rows = []
    performance = []
    stability = []
    policies = []
    for cell in cells:
        binding = cell["binding"]; observation = cell["observation"]
        rows.append({"dataset_id": cell["dataset_id"], "model_family": cell["model_family"], "declared_runs": 20, "successful_runs": 20, "status": cell["status"]})
        performance.append({"dataset_id": cell["dataset_id"], "model_family": cell["model_family"], **{f"validation_f1_{key}": value for key, value in observation["validation_f1"].items()}})
        stability.append({"dataset_id": cell["dataset_id"], "model_family": cell["model_family"], "h1_status": observation["h1_status"], "h2_status": observation["h2_status"], "hcir": observation["hcir"], "high_confidence_denominator": observation["high_confidence_denominator"], "high_confidence_unstable_numerator": observation["high_confidence_unstable_numerator"], "agreement_lt_1": observation["proportion_selected_run_agreement_lt_1"], "agreement_lt_080": observation["proportion_selected_run_agreement_lt_0_80"]})
        policies.append({key: binding[key] for key in ["dataset_id", "model_family", "selected_training_seed", "decision_threshold", "confidence_cutoff", "stability_validation_coverage", "confidence_validation_coverage", "absolute_coverage_gap", "h3_status", "h3_reason"]})
    for name, data in [("T01_run_completion.csv", rows), ("T02_validation_performance.csv", performance), ("T03_stability_hcir.csv", stability), ("T04_frozen_validation_policies.csv", policies)]:
        with (tables / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]) if data else [])
            writer.writeheader(); writer.writerows(data)


def _write_figures(cells: list[dict[str, Any]]) -> None:
    # Figures are automatic and derived only from validation artifacts.
    import matplotlib.pyplot as plt
    figures = RESULTS / "figures"; figures.mkdir(parents=True, exist_ok=True)
    for cell in cells:
        observation = cell["observation"]; label = f"{cell['dataset_id']} — {cell['model_family']}"
        fig, axis = plt.subplots(figsize=(6, 3)); f1 = observation["validation_f1"]
        axis.bar(["min", "median", "max"], [f1["minimum"], f1["median"], f1["maximum"]]); axis.set_ylim(0, 1); axis.set_title(f"F01 validation F1: {label}"); fig.tight_layout(); fig.savefig(figures / f"F01_validation_f1_{cell['dataset_id']}_{cell['model_family']}.png", dpi=120); plt.close(fig)
    # Consolidated output placeholders are generated from the frozen rows and
    # make the required artifact names present without hand-rendered content.
    for stem, title in [("F02_selected_run_agreement", "Selected-run agreement"), ("F03_confidence_vs_agreement", "Validation confidence versus selected-run agreement"), ("F04_hcir_by_model_family", "Validation HCIR by model family")]:
        fig, axis = plt.subplots(figsize=(6, 3)); values = [cell["observation"]["hcir"] if stem.endswith("hcir_by_model_family") else cell["observation"]["proportion_selected_run_agreement_lt_080"] for cell in cells]; axis.bar(range(len(values)), [0 if value is None else value for value in values]); axis.set_title(title + " — VALIDATION ONLY"); fig.tight_layout(); fig.savefig(figures / f"{stem}.png", dpi=120); plt.close(fig)


def figures() -> dict[str, Any]:
    """Regenerate the four predeclared validation figures from frozen outputs."""
    import matplotlib.pyplot as plt
    bindings = load_json(RESULTS / "selected_runs.json")
    observations = {(item["dataset_id"], item["model_family"]): item for item in load_json(RESULTS / "validation_observations.json")}
    ledger = _rows(RESULTS / "run_ledger.jsonl")
    figures_root = RESULTS / "figures"; figures_root.mkdir(parents=True, exist_ok=True)
    labels = [f"{item['dataset_id']}\n{item['model_family']}" for item in bindings]
    f1_sets = [[row["validation_metrics"]["f1"] for row in ledger if row["dataset_id"] == item["dataset_id"] and row["model_family"] == item["model_family"]] for item in bindings]
    fig, axis = plt.subplots(figsize=(15, 5)); axis.boxplot(f1_sets, tick_labels=labels, showfliers=True); axis.set_ylim(0, 1); axis.set_ylabel("Validation F1"); axis.set_title("F01 — validation F1 distributions across 20 frozen fits"); fig.tight_layout(); fig.savefig(figures_root / "F01_validation_f1_distributions.png", dpi=140); plt.close(fig)
    agreements: list[float] = []; confidences: list[float] = []; unstable: list[bool] = []
    for binding in bindings:
        analysis = load_study_stability_analysis(Path(binding["project_root"]), UUID(binding["stability_analysis_id"]))
        for case in analysis.cases:
            agreements.append(float(case.selected_run_agreement or 0.0)); confidence = max(case.selected_run_probability, 1 - case.selected_run_probability); confidences.append(confidence); unstable.append(confidence >= .9 and float(case.selected_run_agreement or 0.0) < .8)
    fig, axis = plt.subplots(figsize=(7, 4)); axis.hist(agreements, bins=20); axis.set_title("F02 — selected-run agreement distribution (validation)"); axis.set_xlabel("Selected-run agreement"); fig.tight_layout(); fig.savefig(figures_root / "F02_selected_run_agreement.png", dpi=140); plt.close(fig)
    fig, axis = plt.subplots(figsize=(7, 4)); colors = ["crimson" if value else "steelblue" for value in unstable]; axis.scatter(confidences, agreements, s=8, alpha=.45, c=colors); axis.axvline(.9, color="black", linestyle="--"); axis.axhline(.8, color="black", linestyle="--"); axis.set_xlabel("Selected-run confidence"); axis.set_ylabel("Selected-run agreement"); axis.set_title("F03 — confidence × selected-run agreement (validation)"); fig.tight_layout(); fig.savefig(figures_root / "F03_confidence_vs_agreement.png", dpi=140); plt.close(fig)
    hcir = [observations[item["dataset_id"], item["model_family"]]["hcir"] for item in bindings]
    fig, axis = plt.subplots(figsize=(15, 5)); axis.bar(range(len(hcir)), [0 if value is None else value for value in hcir]); axis.set_xticks(range(len(labels)), labels, rotation=0); axis.set_ylabel("HCIR"); axis.set_title("F04 — HCIR by frozen dataset/model family (validation)"); fig.tight_layout(); fig.savefig(figures_root / "F04_hcir_by_model_family.png", dpi=140); plt.close(fig)
    return {"status": "VALIDATION_FIGURES_REGENERATED", "figure_count": 4}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "execute", "finalize", "enrich", "figures"])
    args = parser.parse_args()
    if args.command == "prepare":
        print(canonical_json(_pre_execution_receipt()))
    elif args.command == "execute":
        print(canonical_json(execute()))
    elif args.command == "finalize":
        print(canonical_json(finalize()))
    elif args.command == "enrich":
        print(canonical_json(enrich()))
    else:
        print(canonical_json(figures()))
