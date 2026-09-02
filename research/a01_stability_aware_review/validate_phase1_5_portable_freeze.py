"""Pure-Python validator for extracted A01 Phase 1.5 evidence/runtime bundles."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def _rows(path: Path) -> list[dict]: return [json.loads(line) for line in path.read_text().splitlines() if line]


def validate(bundle_root: Path, runtime_root: Path) -> list[str]:
    errors: list[str] = []
    manifest = json.loads((bundle_root / "BUNDLE_MANIFEST.json").read_text())
    runtime = json.loads((runtime_root / "RUNTIME_MANIFEST.json").read_text())
    if manifest.get("final_test_data_included") or runtime.get("final_test_data_included"): errors.append("final-test data included")
    artifacts = runtime.get("artifacts", [])
    if len(artifacts) != 300: errors.append("expected 300 artifacts")
    corrected = json.loads((bundle_root / "research/results/phase1_5_audit/H1_CORRECTED_INTERPRETATION.json").read_text())
    if len(corrected) != 15 or any(row.get("h1_confirmatory_status") != "NOT_ASSESSABLE" for row in corrected): errors.append("H1 amendment missing")
    h2 = json.loads((bundle_root / "research/results/phase1_5_audit/H2_INDEPENDENT_RECOMPUTATION.json").read_text())
    if len(h2) != 15: errors.append("H2 recomputation incomplete")
    for row in artifacts:
        if Path(row["logical_project_root"]).is_absolute() or "/home/" in row["logical_project_root"]: errors.append("absolute logical root")
        blob, metadata = runtime_root / row["logical_project_root"] / row["artifact_blob"], runtime_root / row["logical_project_root"] / row["artifact_metadata"]
        if not blob.is_file() or not metadata.is_file() or _sha(blob) != row["model_artifact_sha256"]: errors.append(f"artifact invalid {row['run_id']}")
    # A firewall *receipt* is required evidence that test access stayed closed;
    # an evaluation/result artifact is forbidden.  Do not reject the receipt
    # merely because it truthfully contains the words "final test".
    for path in bundle_root.rglob("*.json"):
        name = path.name.lower()
        if name == "final_test_firewall_receipt.json":
            payload = json.loads(path.read_text())
            if payload.get("status") != "PASS" or payload.get("final_test_artifacts") != []:
                errors.append("firewall receipt is not closed")
        elif "final-test" in name or "final_test" in name:
            errors.append(f"unexpected final-test artifact {path}")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--bundle-root", type=Path, required=True); parser.add_argument("--runtime-root", type=Path, required=True); args = parser.parse_args()
    errors = validate(args.bundle_root, args.runtime_root)
    if errors: raise SystemExit("FAIL: " + "; ".join(errors))
    print("PASS: portable evidence/runtime freeze verified; final test absent")
