from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

from research.a01_stability_aware_review.core import CONFIG, build_execution_plan, declared_run_support_status, load_json
from research.a01_stability_aware_review.scripts.build_locked_protocol import build
from research.a01_stability_aware_review.scripts.run_smoke import run_smoke
from research.a01_stability_aware_review.validate_pre_freeze import validate
from ruflex.application.training import _select_study_run
from ruflex.domain.training import TrainingRun


SOURCE = Path(__file__).resolve().parents[1] / "research" / "a01_stability_aware_review"


def _copy_protocol(tmp_path: Path) -> Path:
    target = tmp_path / "a01"
    # Phase 0 validators are historical: Phase 1 evidence intentionally makes
    # them fail in the live research tree.  Reconstruct the pre-execution
    # source state when testing that historical validator.
    shutil.copytree(SOURCE, target, ignore=shutil.ignore_patterns("artifacts", "results", "__pycache__"))
    return target


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def test_complete_a01_locked_protocol_passes(tmp_path: Path) -> None:
    assert validate(_copy_protocol(tmp_path)) == []


def test_missing_dataset_and_changed_hash_fail_closed(tmp_path: Path) -> None:
    root = _copy_protocol(tmp_path)
    specs = _json(root / "config" / "dataset_specs.json")
    specs["datasets"] = specs["datasets"][:-1]
    _write(root / "config" / "dataset_specs.json", specs)
    assert validate(root)
    root = _copy_protocol(tmp_path / "other")
    specs = _json(root / "config" / "dataset_specs.json")
    specs["datasets"][0]["raw_file_sha256"] = "0" * 64
    _write(root / "config" / "dataset_specs.json", specs)
    assert validate(root)


def test_seed_split_gate_and_operational_source_mutations_fail(tmp_path: Path) -> None:
    for name, mutate in {
        "missing-seed": lambda plan: plan.__setitem__("training_seeds", plan["training_seeds"][:-1]),
        "duplicate-seed": lambda plan: plan.__setitem__("training_seeds", [*plan["training_seeds"][:-1], 18]),
        "split": lambda plan: plan.__setitem__("split_seed", 7),
        "fraction": lambda plan: plan.__setitem__("split_fractions", {"train": .7, "validation": .1, "final_test": .2}),
        "confidence": lambda plan: plan["validation_only_policy"].__setitem__("min_confidence", .85),
        "agreement": lambda plan: plan["validation_only_policy"].__setitem__("min_class_agreement", .75),
        "dispersion": lambda plan: plan["validation_only_policy"].__setitem__("max_probability_std", .12),
        "calibrated": lambda plan: plan["decision_threshold"].__setitem__("probability_source", "calibrated"),
        "majority": lambda plan: plan["hcir"].__setitem__("agreement_source", "majority_class_agreement"),
        "partial": lambda plan: plan.__setitem__("declared_run_support", {"required_runs_per_dataset_model": 19, "failure_status": "PARTIAL", "replacement_seed": "ALLOWED"}),
    }.items():
        root = _copy_protocol(tmp_path / name)
        path = root / "config" / "pre_freeze_plan.json"
        plan = _json(path); mutate(plan); _write(path, plan)
        assert validate(root), name


def test_model_and_preprocessing_mutation_invalidates_lock(tmp_path: Path) -> None:
    root = _copy_protocol(tmp_path)
    model_path = root / "config" / "model_specs.json"; models = _json(model_path)
    models["models"][2]["estimator_parameters"]["n_estimators"] = 99
    _write(model_path, models)
    assert validate(root)
    root = _copy_protocol(tmp_path / "pre")
    dataset_path = root / "config" / "dataset_specs.json"; datasets = _json(dataset_path)
    datasets["datasets"][0]["preprocessing"]["fit_scope"] = "FULL_DATA"
    _write(dataset_path, datasets)
    assert validate(root)


def test_final_artifact_is_pre_freeze_failure(tmp_path: Path) -> None:
    root = _copy_protocol(tmp_path)
    final = root / "artifacts" / "final-test"; final.mkdir(parents=True)
    (final / "forbidden.json").write_text("{}", encoding="utf-8")
    assert any("final-test artifact" in issue for issue in validate(root))


def test_locked_plan_is_deterministic_and_complete() -> None:
    plan = load_json(CONFIG / "pre_freeze_plan.json")
    datasets = load_json(CONFIG / "dataset_specs.json")
    models = load_json(CONFIG / "model_specs.json")
    datasets["dataset_spec_sha256"] = "dataset"; models["model_spec_sha256"] = "model"
    assert build_execution_plan(datasets, models, plan) == build_execution_plan(datasets, models, plan)
    assert len(build_execution_plan(datasets, models, plan)) == 300


def test_locked_plan_rebuild_is_byte_stable(tmp_path: Path) -> None:
    root = _copy_protocol(tmp_path)
    first = (root / "config" / "locked_execution_plan.jsonl").read_bytes()
    build(root / "config")
    second = (root / "config" / "locked_execution_plan.jsonl").read_bytes()
    build(root / "config")
    assert first == second == (root / "config" / "locked_execution_plan.jsonl").read_bytes()


def test_a01_partial_declared_run_support_fails_closed() -> None:
    states = {seed: "SUCCEEDED" for seed in range(20)}
    states[7] = "FAILED"
    result = declared_run_support_status(list(range(20)), states)
    assert result["status"] == "INCOMPLETE_DECLARED_RUN_SUPPORT"
    assert result["missing_or_failed_training_seeds"] == [7]
    assert result["replacement_seed_permitted"] is False


def test_selected_run_tie_breaks_to_lowest_training_seed() -> None:
    low = TrainingRun.model_construct(run_id=uuid4(), seed=2, training_seed=2)
    high = TrainingRun.model_construct(run_id=uuid4(), seed=9, training_seed=9)
    selected, value, rule = _select_study_run([(high, .8), (low, .8)], "f1")
    assert selected.run_id == low.run_id and value == .8 and rule == "max"


def test_product_native_smoke_never_accesses_final_test() -> None:
    outcome = run_smoke()
    assert outcome["status"] == "SMOKE_PASS_NOT_A01_EVIDENCE"
    assert outcome["final_test_accessed"] is False
    assert outcome["reopened_analysis_count"] == 1
