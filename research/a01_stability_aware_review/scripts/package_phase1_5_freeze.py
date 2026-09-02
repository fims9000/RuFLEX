"""Build the separate portable A01 evidence and frozen-model runtime bundles.

The evidence bundle contains no raw data or model blobs.  The runtime bundle
contains only verified frozen model/preprocessing artifacts and logical roots.
Neither package contains final-test rows or an authorization artifact.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from research.a01_stability_aware_review.core import ROOT, canonical_json, sha256_file

PHASE1 = ROOT / "results" / "phase1_validation"
AUDIT = ROOT / "results" / "phase1_5_audit"
PROJECTS = ROOT / "artifacts" / "phase1-projects"
RELEASE = ROOT.parents[1] / "release"


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _copy(source: Path, root: Path, target: str) -> None:
    destination = root / target
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _zip(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source))
    return sha256_file(destination)


def package() -> dict[str, Any]:
    artifacts = _rows(AUDIT / "MODEL_ARTIFACT_FREEZE.jsonl")
    bindings = json.loads((PHASE1 / "selected_runs.json").read_text(encoding="utf-8"))
    # `/tmp` is a quota-limited tmpfs on the research workstation; staging a
    # portable bundle there can fail despite abundant repository filesystem
    # capacity.  Keep the ephemeral staging directory under ignored release.
    staging_parent = RELEASE / ".staging"; staging_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ruflex-a01-phase1-5-", dir=staging_parent) as temp:
        staging = Path(temp); evidence = staging / "evidence"; runtime = staging / "runtime"
        # Frozen scientific configuration and compact/recomputed research data.
        for path in sorted((ROOT / "config").glob("*.json")):
            _copy(path, evidence, f"research/config/{path.name}")
        for name in ["PROTOCOL.md", "STATISTICAL_ANALYSIS_PLAN.md", "PHASE1_VALIDATION_RESULTS.md", "AMENDMENT_001_H1_UNDERSPECIFICATION.md"]:
            _copy(ROOT / name, evidence, f"research/{name}")
        _copy(ROOT / "validate_phase1_5_portable_freeze.py", evidence, "validator/validate_phase1_5_portable_freeze.py")
        for directory, prefix in [(PHASE1, "results/phase1_validation"), (AUDIT, "results/phase1_5_audit")]:
            for path in sorted(directory.glob("*")):
                if path.is_file(): _copy(path, evidence, f"research/{prefix}/{path.name}")
        # Persisted canonical metadata and all validation-only case evidence.
        # Include the exact frozen chain, not every superseded active-object
        # revision left by Phase 1 resume/enrichment.  This is both portable
        # and scientific: the IDs in the binding are the authoritative chain.
        seen_projects: set[tuple[str, str]] = set()
        for binding in bindings:
            key = (binding["dataset_id"], binding["model_family"])
            if key in seen_projects: continue
            seen_projects.add(key)
            source = PROJECTS / key[0] / key[1]
            logical = f"projects/{key[0]}/{key[1]}"
            _copy(source / "project.yaml", evidence, f"{logical}/project.yaml")
            study = json.loads((source / "studies" / f"{binding['study_id']}.json").read_text(encoding="utf-8"))
            exact = [
                ("studies", binding["study_id"]), ("analyses/evaluations", binding["evaluation_id"]),
                ("analyses/thresholds", binding["threshold_id"]), ("analyses/stability-analyses", binding["stability_analysis_id"]),
                ("analyses/stability-policies", binding["stability_gate_policy_id"]), ("analyses/selective-policies", binding["confidence_only_policy_id"]),
            ] + [("runs", run["run_id"]) for run in study["seed_runs"]]
            for directory, identifier in exact:
                _copy(source / directory / f"{identifier}.json", evidence, f"{logical}/{directory}/{identifier}.json")
            for name in ["dataset-contract.json", "dataset-profile.json", "data-audit.json"]:
                _copy(source / "data" / name, evidence, f"{logical}/data/{name}")
        # Runtime model blobs plus their metadata only; all paths are logical.
        for row in artifacts:
            source = PROJECTS / row["dataset_id"] / row["model_family"]
            logical = row["logical_project_root"]
            _copy(source / row["artifact_blob"], runtime, f"{logical}/{row['artifact_blob']}")
            _copy(source / row["artifact_metadata"], runtime, f"{logical}/{row['artifact_metadata']}")
        _write(evidence / "BUNDLE_MANIFEST.json", {"bundle_kind": "A01_PHASE1_5_VALIDATION_EVIDENCE", "logical_roots_only": True, "final_test_data_included": False, "binding_count": len(bindings), "model_artifact_manifest_sha256": sha256_file(AUDIT / "MODEL_ARTIFACT_FREEZE.jsonl")})
        _write(runtime / "RUNTIME_MANIFEST.json", {"bundle_kind": "A01_FROZEN_MODELS_RUNTIME", "logical_roots_only": True, "final_test_data_included": False, "artifact_count": len(artifacts), "artifacts": artifacts})
        evidence_zip = RELEASE / "RuFLEX_A01_PHASE1_5_VALIDATION_EVIDENCE_BUNDLE.zip"
        runtime_zip = RELEASE / "RuFLEX_A01_FROZEN_MODELS_RUNTIME_BUNDLE.zip"
        evidence_sha, runtime_sha = _zip(evidence, evidence_zip), _zip(runtime, runtime_zip)
    output = {"evidence_bundle": str(evidence_zip), "evidence_bundle_sha256": evidence_sha, "runtime_bundle": str(runtime_zip), "runtime_bundle_sha256": runtime_sha, "artifact_count": len(artifacts), "final_test_data_included": False}
    _write(AUDIT / "BUNDLE_RECEIPT.json", output)
    return output


if __name__ == "__main__":
    print(canonical_json(package()))
