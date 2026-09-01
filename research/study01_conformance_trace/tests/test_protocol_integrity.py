from __future__ import annotations

import hashlib
import json
from pathlib import Path

from research.study01_conformance_trace.scripts.freeze_protocol import build_manifest
from research.study01_conformance_trace.scripts.validate_study import EXPECTED_SHA, ARCHIVE, validate_baseline, validate_protocol_preconditions


ROOT = Path(__file__).resolve().parents[1]


def test_product_baseline_hash() -> None:
    validate_baseline()
    assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == EXPECTED_SHA


def test_protocol_preconditions() -> None:
    validate_protocol_preconditions()


def test_locked_manifest_has_stable_content_before_unlock() -> None:
    manifest = build_manifest()
    assert manifest["test_unlock"] == "FORBIDDEN_PENDING_PROTOCOL_REVIEW"
    assert len(manifest["fixture_ids"]) == 52


def test_no_locked_fixture_removed() -> None:
    manifest = build_manifest()
    paths = list((ROOT / "fixtures" / "curated").glob("*.json")) + list((ROOT / "fixtures" / "generated").glob("*.json"))
    assert len(paths) == len(manifest["fixture_ids"])


def test_figures_generated_from_artifacts() -> None:
    provenance = ROOT / "artifacts" / "aggregated" / "dev_evidence_provenance.json"
    assert provenance.is_file()
    data = json.loads(provenance.read_text())
    assert (ROOT / data["source"]).is_file()
    assert (ROOT / data["figure"]).is_file()


def test_result_freeze_thesis_numbers_bind_the_locked_manifest() -> None:
    data = json.loads((ROOT / "THESIS_NUMBERS.json").read_text())
    assert data["status"] == "RESULT_FREEZE"
    assert data["locked_manifest_hash"] == build_manifest()["manifest_hash"]


def test_environment_records_matlab_unavailable_without_failure() -> None:
    data = json.loads((ROOT / "config" / "environments.json").read_text())
    assert data["matlab_engine"]["status"] == "NOT_AVAILABLE"
