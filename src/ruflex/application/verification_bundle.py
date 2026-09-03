"""Safe, declarative evidence export; never an executable project archive."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from ruflex.application.assurance import load_latest_assurance_case
from ruflex.application.evidence import _atomic_write_text
from ruflex.application.lineage import build_project_lineage
from ruflex.domain.verification import VerificationBundle, VerificationBundleValidation
from ruflex.application.datasets import DataAuditReport, DatasetContract, DatasetProfile
from ruflex.domain.assurance import AssuranceCase
from ruflex.domain.behavior import BehaviorSpec, BehaviorSpecResult
from ruflex.domain.evidence import ExplanationCheck, ExplanationContract, ExplanationReproducibilityAnalysis
from ruflex.application.generalization import GeneralizationContract
from ruflex.domain.selective import SelectivePredictionPolicy
from ruflex.domain.stability import StabilityGatePolicy, StudyStabilityAnalysis
from ruflex.domain.training import AnalysisComparison, AnalysisEvaluation, CalibrationTransform, DecisionThresholdPolicy, FinalTestEvaluation, TrainingRun, TrainingStudy

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


_FORBIDDEN_SUFFIXES = (".pkl", ".pickle", ".joblib", ".pyc", ".py", ".sh", ".exe")


def _safe_name(name: str) -> bool:
    path = Path(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and not name.startswith("/")


def _model_for_entry(name: str) -> type[BaseModel] | None:
    if name == "data/dataset-contract.json": return DatasetContract
    if name == "data/dataset-profile.json": return DatasetProfile
    if name == "data/dataset-audit.json": return DataAuditReport
    if name.startswith("runs/"): return TrainingRun
    if name.startswith("studies/"): return TrainingStudy
    if name.startswith("analyses/evaluations/"): return AnalysisEvaluation
    if name.startswith("analyses/calibrations/"): return CalibrationTransform
    if name.startswith("analyses/thresholds/"): return DecisionThresholdPolicy
    if name.startswith("analyses/selective-policies/"): return SelectivePredictionPolicy
    if name.startswith("analyses/stability-analyses/"): return StudyStabilityAnalysis
    if name.startswith("analyses/stability-policies/"): return StabilityGatePolicy
    if name.startswith("analyses/final-tests/"): return FinalTestEvaluation
    if name.startswith("analyses/comparisons/"): return AnalysisComparison
    if name.startswith("objects/protocols/generalization/"): return GeneralizationContract
    if name.startswith("evidence/explanations/"): return ExplanationContract
    if name.startswith("evidence/explanation-checks/"): return ExplanationCheck
    if name.startswith("evidence/explanation-reproducibility/"): return ExplanationReproducibilityAnalysis
    if name.startswith("evidence/behavior-specs/result-"): return BehaviorSpecResult
    if name.startswith("evidence/behavior-specs/"): return BehaviorSpec
    if name.startswith("evidence/assurance/"): return AssuranceCase
    return None


def _read_bundle_entries(source: Path) -> tuple[dict[str, bytes], str | None, list[str]]:
    """Read a ZIP or an extracted bundle without executing any contents."""
    errors: list[str] = []
    if source.is_file():
        raw = source.read_bytes()
        try:
            with zipfile.ZipFile(source) as archive:
                names = archive.namelist()
                if len(names) != len(set(names)): errors.append("Bundle contains duplicate entry names.")
                entries = {name: archive.read(name) for name in names if _safe_name(name)}
                if any(not _safe_name(name) for name in names): errors.append("Bundle contains an unsafe archive path.")
        except zipfile.BadZipFile:
            return {}, _sha(raw), ["Bundle is not a valid ZIP archive."]
        return entries, _sha(raw), errors
    if source.is_dir():
        entries = {path.relative_to(source).as_posix(): path.read_bytes() for path in source.rglob("*") if path.is_file()}
        return entries, None, errors
    return {}, None, ["Bundle path does not exist."]


def _validate_relationships(objects: list[BaseModel]) -> list[str]:
    by_type: dict[type[BaseModel], set[str]] = {}
    for object_ in objects:
        identifier = next((getattr(object_, field) for field in ("run_id", "study_id", "evaluation_id", "calibration_id", "threshold_id", "policy_id", "analysis_id", "final_test_id", "explanation_id", "check_id", "spec_id", "result_id", "assurance_id") if hasattr(object_, field)), None)
        if identifier is not None: by_type.setdefault(type(object_), set()).add(str(identifier))
    def exists(model: type[BaseModel], value: Any) -> bool: return value is None or str(value) in by_type.get(model, set())
    errors: list[str] = []
    for object_ in objects:
        if isinstance(object_, AnalysisEvaluation) and not exists(TrainingRun, object_.run_id): errors.append(f"Evaluation {object_.evaluation_id} references missing TrainingRun {object_.run_id}.")
        elif isinstance(object_, CalibrationTransform) and (not exists(AnalysisEvaluation, object_.evaluation_id) or not exists(TrainingRun, object_.run_id)): errors.append(f"Calibration {object_.calibration_id} has a broken evaluation/run reference.")
        elif isinstance(object_, DecisionThresholdPolicy) and (not exists(AnalysisEvaluation, object_.evaluation_id) or not exists(TrainingRun, object_.run_id)): errors.append(f"Threshold {object_.threshold_id} has a broken evaluation/run reference.")
        elif isinstance(object_, SelectivePredictionPolicy) and (not exists(AnalysisEvaluation, object_.evaluation_id) or not exists(TrainingRun, object_.run_id) or not exists(DecisionThresholdPolicy, object_.class_threshold_id)): errors.append(f"Selective policy {object_.policy_id} has broken frozen-policy provenance.")
        elif isinstance(object_, ExplanationContract) and not exists(TrainingRun, object_.run_id): errors.append(f"Explanation {object_.explanation_id} references missing TrainingRun {object_.run_id}.")
        elif isinstance(object_, ExplanationCheck) and (not exists(ExplanationContract, object_.explanation_id) or not exists(TrainingRun, object_.run_id)): errors.append(f"Explanation check {object_.check_id} has broken evidence provenance.")
        elif isinstance(object_, StabilityGatePolicy) and (not exists(StudyStabilityAnalysis, object_.stability_analysis_id) or not exists(TrainingRun, object_.selected_run_id) or not exists(AnalysisEvaluation, object_.evaluation_id) or not exists(DecisionThresholdPolicy, object_.class_threshold_id)): errors.append(f"Stability gate {object_.policy_id} has broken frozen-policy provenance.")
    return errors


def validate_verification_bundle(path: Path | str) -> VerificationBundleValidation:
    """Fail-closed validation for a ZIP or freshly extracted evidence bundle."""
    source = Path(path)
    entries, bundle_sha, errors = _read_bundle_entries(source)
    warnings: list[str] = []
    manifest_sha: str | None = None
    manifest_raw = entries.get("verification-manifest.json")
    if manifest_raw is None:
        errors.append("Missing verification-manifest.json.")
        return VerificationBundleValidation(bundle_path=str(source), status="FAIL", bundle_sha256=bundle_sha, errors=errors)
    try:
        manifest = json.loads(manifest_raw)
        manifest_sha = _sha(manifest_raw)
    except json.JSONDecodeError:
        return VerificationBundleValidation(bundle_path=str(source), status="FAIL", bundle_sha256=bundle_sha, errors=[*errors, "verification-manifest.json is malformed JSON."])
    if manifest.get("schema_version") != 2 or manifest.get("inspection_first") is not True:
        errors.append("Unsupported or non-inspection-first verification manifest.")
    checksum_file = entries.get("verification-manifest.sha256", b"").decode("utf-8", errors="replace").split()
    if not checksum_file or checksum_file[0] != manifest_sha:
        errors.append("verification-manifest.sha256 does not match the manifest.")
    checksums = manifest.get("checksums")
    if not isinstance(checksums, dict) or not checksums:
        errors.append("Manifest has no checksum inventory.")
        checksums = {}
    for name, expected in checksums.items():
        actual = entries.get(name)
        if actual is None: errors.append(f"Manifest entry is missing: {name}.")
        elif _sha(actual) != expected: errors.append(f"Checksum mismatch: {name}.")
    allowed_unmanifested = {"verification-manifest.json", "verification-manifest.sha256"}
    unlisted = set(entries) - set(checksums) - allowed_unmanifested
    if unlisted: errors.append("Bundle contains entries absent from the checksum inventory: " + ", ".join(sorted(unlisted)) + ".")
    for name in entries:
        if not _safe_name(name) or name.lower().endswith(_FORBIDDEN_SUFFIXES) or "node_modules" in Path(name).parts:
            errors.append(f"Bundle contains prohibited or unsafe entry: {name}.")
    objects: list[BaseModel] = []
    for name, raw in checksums.items():
        model = _model_for_entry(name)
        if model is None: continue
        try: objects.append(model.model_validate_json(entries[name]))
        except (ValidationError, ValueError, KeyError) as error: errors.append(f"Invalid {model.__name__} evidence at {name}: {error}.")
    errors.extend(_validate_relationships(objects))
    if not any(isinstance(item, AssuranceCase) for item in objects): warnings.append("No typed AssuranceCase object was found in the bundle.")
    return VerificationBundleValidation(bundle_path=str(source), status="FAIL" if errors else "PASS", bundle_sha256=bundle_sha, manifest_sha256=manifest_sha, checked_entries=len(checksums), errors=errors, warnings=warnings)


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
