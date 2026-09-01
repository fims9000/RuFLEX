"""Safe, declarative evidence export; never an executable project archive."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from ruflex.application.assurance import load_latest_assurance_case
from ruflex.application.evidence import _atomic_write_text
from ruflex.application.lineage import build_project_lineage
from ruflex.domain.verification import VerificationBundle

_EVIDENCE_DIRS = (
    "runs", "studies", "analyses/evaluations", "analyses/calibrations", "analyses/thresholds",
    "analyses/selective-policies", "analyses/stability-analyses", "analyses/stability-policies", "analyses/slices", "analyses/final-tests", "analyses/comparisons",
    "objects/protocols/generalization", "evidence/explanations", "evidence/explanation-checks",
    "evidence/explanation-reproducibility", "evidence/behavior-specs", "evidence/exhaustive-lab",
    "evidence/tree-paths", "evidence/assurance", "evidence/condition-monitoring-demo", "analyses/expert-corrections",
)
_DECLARATIVE_MODEL_DIRS = ("models/fis",)
_POINTERS = {"active-training-run.json", "active-study.json", "active-evaluation.json", "active-calibration.json", "active-threshold.json", "active-policy.json", "active-slice-analysis.json", "active-final-test.json", "active-comparison.json", "active-explanation.json", "active-check.json", "active-spec.json", "active-result.json", "active-case.json", "latest.json"}
_EXCLUDED = ["raw datasets", "pickle/joblib", "untrusted executable code", "credentials", "node_modules", "caches", "temporary build products"]


def _sha(data: bytes) -> str: return hashlib.sha256(data).hexdigest()


def _declarative_paths(base: Path) -> list[Path]:
    result: list[Path] = []
    project = base / "project.yaml"
    if project.is_file(): result.append(project)
    for relative in ("data/dataset-contract.json", "data/dataset-profile.json", "data/dataset-audit.json"):
        path = base / relative
        if path.is_file(): result.append(path)
    for directory in _EVIDENCE_DIRS:
        root = base / directory
        if not root.is_dir(): continue
        for path in sorted(root.glob("*.json")):
            if path.name not in _POINTERS and not path.name.startswith("result-") or path.name.startswith("result-"):
                result.append(path)
    for directory in _DECLARATIVE_MODEL_DIRS:
        root = base / directory
        if root.is_dir():
            result.extend(path for path in sorted(root.rglob("*.json")) if path.is_file())
    return result


def export_verification_bundle(root: Path) -> dict:
    base = Path(root).resolve(); assurance = load_latest_assurance_case(base)
    contents: dict[str, bytes] = {}
    for path in _declarative_paths(base):
        name = path.relative_to(base).as_posix()
        if name.endswith((".pkl", ".pickle", ".joblib", ".pyc")) or "node_modules" in name:
            continue
        contents[name] = path.read_bytes()
    contents["lineage.json"] = build_project_lineage(base).model_dump_json(indent=2).encode()
    contents["assurance-summary.json"] = assurance.model_dump_json(indent=2).encode()
    report = "# RuFLEX Verification Bundle\n\nInspection-first declarative evidence package. Independent AssuranceCase gates are not a trust score.\n\n"
    report += "## Assurance gates\n\n" + "\n".join(f"- {gate.key}: {gate.status}" + (f" — {gate.risk}" if gate.risk else "") for gate in assurance.gates) + "\n"
    contents["report.md"] = report.encode()
    checksums = {name: _sha(data) for name, data in sorted(contents.items())}
    manifest = {"schema_version": 2, "inspection_first": True, "assurance_id": str(assurance.assurance_id), "checksums": checksums, "excluded": _EXCLUDED, "manifest_checksum_file": "verification-manifest.sha256"}
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode()
    contents["verification-manifest.json"] = manifest_bytes
    contents["verification-manifest.sha256"] = f"{_sha(manifest_bytes)}  verification-manifest.json\n".encode()
    out = base / "exports"; out.mkdir(parents=True, exist_ok=True)
    bundle = out / f"verification-bundle-{assurance.assurance_id}.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(contents.items()): archive.writestr(name, data)
    object_ = VerificationBundle(assurance_id=assurance.assurance_id, sha256=_sha(bundle.read_bytes()), entry_count=len(contents), manifest_sha256=_sha(manifest_bytes), excluded=_EXCLUDED)
    evidence_root = base / "evidence" / "verification-bundles"; evidence_root.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(evidence_root / f"{object_.bundle_id}.json", object_.model_dump_json(indent=2))
    _atomic_write_text(evidence_root / "active-bundle.json", json.dumps({"bundle_id": str(object_.bundle_id), "path": str(bundle)}))
    return {**object_.model_dump(mode="json"), "path": str(bundle)}
