"""Bind the audit-only Phase 1.5 layer without modifying Phase 1 evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from research.a01_stability_aware_review.core import ROOT, canonical_json, sha256_file


def build() -> dict:
    config, phase1, audit = ROOT / "config", ROOT / "results" / "phase1_validation", ROOT / "results" / "phase1_5_audit"
    required = {
        "phase0_manifest_sha256": sha256_file(config / "locked_manifest.json"),
        "phase0_5_manifest_sha256": sha256_file(config / "phase0_5_manifest.json"),
        "phase1_manifest_sha256": sha256_file(phase1 / "phase1_validation_freeze_manifest.json"),
        "amendment_sha256": sha256_file(ROOT / "AMENDMENT_001_H1_UNDERSPECIFICATION.md"),
        "audit_receipt_sha256": sha256_file(audit / "PHASE1_5_AUDIT_RECEIPT.json"),
        "model_artifact_manifest_sha256": sha256_file(audit / "MODEL_ARTIFACT_FREEZE.jsonl"),
        "phase2_executor_sha256": sha256_file(ROOT / "scripts" / "execute_phase2_final_test.py"),
        "portable_validator_sha256": sha256_file(ROOT / "validate_phase1_5_portable_freeze.py"),
    }
    bundle = json.loads((audit / "BUNDLE_RECEIPT.json").read_text(encoding="utf-8"))
    required.update({"evidence_bundle_sha256": bundle["evidence_bundle_sha256"], "runtime_bundle_sha256": bundle["runtime_bundle_sha256"]})
    payload = {"schema_version": 1, "study": "A01 — Stability-Aware Selective Review", "phase": "1.5", "status": "SCIENTIFIC_FREEZE_AUDITED_FINAL_TEST_CLOSED", "h1_original_binary_labels": "WITHDRAWN_DESCRIPTIVE_EVIDENCE_RETAINED", "h2": "INDEPENDENTLY_RECOMPUTED", "h3": "NOT_ASSESSABLE_FINAL_TEST_NOT_OPENED", "model_artifact_count": 300, "final_test_access": "CLOSED", "bindings": required}
    payload["manifest_id"] = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
    target = config / "phase1_5_scientific_freeze_manifest.json"
    target.write_text(canonical_json(payload) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__": print(canonical_json(build()))
