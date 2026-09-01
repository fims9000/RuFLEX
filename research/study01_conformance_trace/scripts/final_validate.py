"""Fail-closed result-freeze validator for Study 01."""
from __future__ import annotations

import json
from pathlib import Path

from research.study01_conformance_trace.scripts.freeze_protocol import build_manifest


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    manifest = json.loads((ROOT / "config" / "locked_suite_manifest.json").read_text())
    if manifest["manifest_hash"] != build_manifest()["manifest_hash"]:
        raise AssertionError("Frozen manifest no longer rebuilds identically.")
    result = json.loads((ROOT / "artifacts" / "locked" / "locked_study_results.json").read_text())
    if result["status"] != "RESULT_FREEZE" or result["locked_manifest_hash"] != manifest["manifest_hash"]:
        raise AssertionError("Results are not bound to the accepted frozen manifest.")
    if result["locked_system_count"] != 52 or result["locked_case_count"] != 764098:
        raise AssertionError("Unexpected locked matrix cardinality.")
    if sum(result["failure_taxonomy"].values()) != 4056:
        raise AssertionError("Failure taxonomy does not account for all observed failures.")
    thesis = json.loads((ROOT / "THESIS_NUMBERS.json").read_text())
    if thesis["locked_manifest_hash"] != manifest["manifest_hash"] or thesis["cases"] != result["locked_case_count"]:
        raise AssertionError("Thesis numbers are not bound to the frozen result.")
    if thesis["defined_output_cases"] != result["locked_case_count"] - sum(result["failure_taxonomy"].values()):
        raise AssertionError("Thesis defined-output count is inconsistent with failure taxonomy.")
    provenance = json.loads((ROOT / "artifacts" / "aggregated" / "locked_evidence_provenance.json").read_text())
    if provenance["manifest_hash"] != manifest["manifest_hash"]:
        raise AssertionError("Figure provenance is not manifest-bound.")
    for relative in [*result["tables"], *result["figures"]]:
        if not (ROOT / relative).is_file():
            raise AssertionError(f"Missing reported output: {relative}")
    print("STUDY01_RESULT_FREEZE_VALIDATOR_PASS")


if __name__ == "__main__":
    main()
