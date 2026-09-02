"""Build deterministic A01 pre-freeze execution and manifest files."""
from __future__ import annotations

from pathlib import Path

from research.a01_stability_aware_review.core import CONFIG, PRODUCT_SNAPSHOT, build_execution_plan, canonical_json, config_hash, load_json, sha256_bytes, write_locked_plan


def build(config_root: Path = CONFIG) -> dict[str, str]:
    plan = load_json(config_root / "pre_freeze_plan.json")
    datasets = load_json(config_root / "dataset_specs.json")
    models = load_json(config_root / "model_specs.json")
    datasets["dataset_spec_sha256"] = config_hash(config_root / "dataset_specs.json")
    models["model_spec_sha256"] = config_hash(config_root / "model_specs.json")
    rows = build_execution_plan(datasets, models, plan)
    execution_hash = write_locked_plan(config_root / "locked_execution_plan.jsonl", rows)
    protocol_hash = sha256_bytes((config_root.parent / "PROTOCOL.md").read_bytes())
    locked_protocol = {
        "study": plan["study"], "status": plan["status"], "product_source_snapshot": PRODUCT_SNAPSHOT,
        "protocol_document_sha256": protocol_hash, "pre_freeze_plan_sha256": config_hash(config_root / "pre_freeze_plan.json"),
        "dataset_spec_sha256": datasets["dataset_spec_sha256"], "model_spec_sha256": models["model_spec_sha256"],
        "execution_plan_sha256": execution_hash, "primary_protocol": plan["primary_protocol"],
        "split_seed": plan["split_seed"], "training_seeds": plan["training_seeds"],
        "expected_dataset_ids": [item["canonical_dataset_id"] for item in datasets["datasets"]],
        "expected_model_families": [item["model_family"] for item in models["models"]],
        "expected_training_runs": len(rows), "gate_constants": plan["validation_only_policy"],
        "selection_rule": plan["selected_run_rule"], "decision_threshold": plan["decision_threshold"],
        "claim_boundaries": plan["claim_boundaries"], "final_test": plan["final_test"],
    }
    (config_root / "locked_protocol.json").write_text(canonical_json(locked_protocol) + "\n", encoding="utf-8")
    manifest = {"schema_version": 1, "study": plan["study"], "status": plan["status"], "immutable_style": True, "locked_protocol_sha256": sha256_bytes((config_root / "locked_protocol.json").read_bytes()), **locked_protocol}
    manifest["manifest_id"] = sha256_bytes(canonical_json(manifest).encode("utf-8"))
    (config_root / "locked_manifest.json").write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    return {"protocol_sha256": protocol_hash, "dataset_spec_sha256": datasets["dataset_spec_sha256"], "model_spec_sha256": models["model_spec_sha256"], "execution_plan_sha256": execution_hash, "manifest_id": manifest["manifest_id"]}


if __name__ == "__main__":
    print(canonical_json(build()))
