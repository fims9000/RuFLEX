"""Future A01 Phase 2 entry point; deliberately fail-closed until unlocked.

This module has no training, selection, threshold-fitting, or calibration path.
It must load only the model/artifact identities frozen by Phase 1.5.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def authorization_gate(unlock_path: Path | None, expected: dict[str, str]) -> dict:
    if unlock_path is None or not unlock_path.is_file():
        raise PermissionError("A01 final test is closed: explicit external unlock artifact is required before any dataset read.")
    unlock = json.loads(unlock_path.read_text(encoding="utf-8"))
    if unlock.get("allow_single_final_test_opening") is not True:
        raise PermissionError("A01 unlock artifact does not authorize a single opening.")
    for key, value in expected.items():
        if unlock.get(key) != value: raise PermissionError(f"A01 unlock identity mismatch: {key}.")
    return unlock


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--unlock", type=Path); parser.add_argument("--phase1-5-manifest", required=True); parser.add_argument("--evidence-sha", required=True); parser.add_argument("--runtime-sha", required=True); args = parser.parse_args()
    authorization_gate(args.unlock, {"phase1_5_manifest_id": args.phase1_5_manifest, "evidence_bundle_sha256": args.evidence_sha, "runtime_bundle_sha256": args.runtime_sha})
    raise RuntimeError("Phase 2 execution is intentionally not invoked by Phase 1.5; authorization was checked without reading A01 data.")


if __name__ == "__main__": main()
