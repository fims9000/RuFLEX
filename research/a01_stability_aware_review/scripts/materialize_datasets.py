"""Materialize declared A01 tables without starting any model training."""
from __future__ import annotations

import argparse
from pathlib import Path

from research.a01_stability_aware_review.core import CONFIG, canonical_json, load_json, materialize_dataset, obtain_source


def materialize(*, source_dir: Path | None, download: bool, output_root: Path) -> list[dict]:
    specs = load_json(CONFIG / "dataset_specs.json")["datasets"]
    raw_root = output_root / "raw"
    manifests = []
    for spec in specs:
        source = obtain_source(spec, source_dir=source_dir, download=download, destination=raw_root)
        manifests.append(materialize_dataset(spec, source_path=source, output_root=output_root / "materialized"))
    return manifests


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source-dir", type=Path, help="Directory containing the three declared source filenames.")
    group.add_argument("--download", action="store_true", help="Explicitly download only the declared immutable source URLs.")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(canonical_json({"status": "PRE_FREEZE_DATA_MATERIALIZATION_ONLY", "final_test_accessed": False, "datasets": materialize(source_dir=args.source_dir, download=args.download, output_root=args.output_root)}))
