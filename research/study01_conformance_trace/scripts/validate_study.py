from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
_STUDY_CONFIG = yaml.safe_load((ROOT / "config" / "study01.yaml").read_text())
ARCHIVE = ROOT.parents[1] / _STUDY_CONFIG["subject_archive"]
EXPECTED_SHA = _STUDY_CONFIG["subject_sha256"]


def validate_baseline() -> None:
    digest = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA:
        raise AssertionError(f"Frozen baseline mismatch: {digest}")


def validate_protocol_preconditions() -> None:
    required = ["MASTER_SPEC.md", "PROTOCOL.md", "config/semantic_intersection.json", "config/tolerances.json", "config/environments.json"]
    missing = [name for name in required if not (ROOT / name).is_file()]
    if missing:
        raise AssertionError(f"Study protocol is incomplete: {missing}")
    data = json.loads((ROOT / "config" / "semantic_intersection.json").read_text())
    if not data["elements"]:
        raise AssertionError("Semantic intersection is empty.")


def main() -> None:
    validate_baseline()
    validate_protocol_preconditions()
    print("STUDY01_PRE_FREEZE_VALIDATOR_PASS")


if __name__ == "__main__":
    main()
