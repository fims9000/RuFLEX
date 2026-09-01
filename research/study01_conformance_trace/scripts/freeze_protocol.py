from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from research.study01_conformance_trace.core.grids import grid_hash, uniform_grid


ROOT = Path(__file__).resolve().parents[1]
STUDY_CONFIG = yaml.safe_load((ROOT / "config" / "study01.yaml").read_text())


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest() -> dict[str, object]:
    fixtures = sorted((ROOT / "fixtures" / "curated").glob("*.json")) + sorted((ROOT / "fixtures" / "generated").glob("*.json"))
    if len(fixtures) != 52:
        raise AssertionError(f"Expected 52 frozen fixture definitions, found {len(fixtures)}.")
    manifest = {
        "schema_version": 1,
        "status": "PROTOCOL_FROZEN_TEST_NOT_UNLOCKED",
        "fixture_ids": [json.loads(path.read_text())["fixture_id"] for path in fixtures],
        "fixture_hashes": {path.name: _sha(path) for path in fixtures},
        "grid_specifications": {
            "one_dimensional": {"points": 10001, "minimum": 0.0, "maximum": 1.0, "hash": grid_hash(uniform_grid(0.0, 1.0, 10001))},
            "two_dimensional": {"points_per_axis": 201, "minimum": 0.0, "maximum": 1.0, "axis_hash": grid_hash(uniform_grid(0.0, 1.0, 201))},
        },
        "generator_seeds": {"mamdani": 20260831, "sugeno": 20260901},
        "tolerance_hash": _sha(ROOT / "config" / "tolerances.json"),
        "semantic_intersection_hash": _sha(ROOT / "config" / "semantic_intersection.json"),
        "environment_hash": _sha(ROOT / "config" / "environments.json"),
        "protocol_hash": _sha(ROOT / "PROTOCOL.md"),
        "reference_versions": {"pyfuzzylite": "8.0.6", "matlab_engine": "NOT_AVAILABLE"},
        "product_baseline": {"archive": STUDY_CONFIG["subject_archive"], "sha256": STUDY_CONFIG["subject_sha256"]},
        "supersedes": STUDY_CONFIG.get("supersedes"),
        "test_unlock": "FORBIDDEN_PENDING_PROTOCOL_REVIEW",
    }
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    manifest["manifest_hash"] = hashlib.sha256(encoded).hexdigest()
    return manifest


def main() -> None:
    manifest = build_manifest()
    path = ROOT / "config" / "locked_suite_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"manifest": str(path.relative_to(ROOT)), "manifest_hash": manifest["manifest_hash"], "test_unlock": manifest["test_unlock"]}))


if __name__ == "__main__":
    main()
