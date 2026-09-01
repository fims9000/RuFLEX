from __future__ import annotations

import pytest

from ruflex.application.fis import evaluate_fis
from ruflex.application.fis_interop import export_matlab_fis, import_matlab_fis


MAMDANI = """[System]
Name='tipper'
Type='mamdani'
AndMethod='min'
OrMethod='max'
ImpMethod='min'
AggMethod='max'
DefuzzMethod='centroid'

[Input1]
Name='service'
Range=[0 10]
NumMFs=2
MF1='poor':'trimf',[0 0 5]
MF2='good':'trimf',[5 10 10]

[Input2]
Name='food'
Range=[0 10]
NumMFs=2
MF1='rancid':'trimf',[0 0 5]
MF2='delicious':'trimf',[5 10 10]

[Output1]
Name='tip'
Range=[0 30]
NumMFs=2
MF1='cheap':'trimf',[0 0 15]
MF2='generous':'trimf',[15 30 30]

[Rules]
1 1, 1 (1) : 1
2 2, 2 (0.8) : 1
"""


def test_imports_supported_matlab_mamdani_into_executable_canonical_fis() -> None:
    result = import_matlab_fis(MAMDANI)
    assert result.spec is not None
    assert result.spec.operators.centroid_sampling.value == "midpoint_cells"
    assert any(issue.status == "APPROXIMATED" and "sampling" in issue.semantic_consequence for issue in result.issues)
    evaluation = evaluate_fis(result.spec, {"service": 8, "food": 8})
    assert evaluation.output > 15
    assert evaluation.trace.inference_kind == "mamdani"


def test_rejects_unsupported_semantics_without_silent_substitution() -> None:
    result = import_matlab_fis(MAMDANI.replace("DefuzzMethod='centroid'", "DefuzzMethod='bisector'"))
    assert result.spec is None
    assert any(issue.status == "UNSUPPORTED" for issue in result.issues)


def test_rejects_negated_matlab_rule_index_without_claiming_import() -> None:
    result = import_matlab_fis(MAMDANI.replace("1 1, 1 (1) : 1", "-1 1, 1 (1) : 1"))
    assert result.spec is None
    assert any(issue.status == "UNSUPPORTED" for issue in result.issues)


def test_supported_mamdani_export_round_trips_without_semantic_substitution() -> None:
    imported = import_matlab_fis(MAMDANI).spec
    assert imported is not None
    restored = import_matlab_fis(export_matlab_fis(imported)).spec
    assert restored is not None
    for inputs in ({"service": 2, "food": 3}, {"service": 8, "food": 8}):
        assert evaluate_fis(restored, inputs).output == pytest.approx(
            evaluate_fis(imported, inputs).output, abs=1e-10
        )


def test_api_persists_supported_import_and_returns_explicit_report(tmp_path) -> None:
    from fastapi.testclient import TestClient
    from ruflex.api.main import app

    client = TestClient(app)
    created = client.post("/api/projects", json={"path": str(tmp_path / "project"), "name": "interop"})
    session_id = created.json()["session_id"]
    imported = client.post(
        "/api/projects/fis/import/matlab",
        json={"session_id": session_id, "source": MAMDANI},
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["spec"]["name"] == "tipper"
    assert any(issue["status"] == "APPROXIMATED" for issue in imported.json()["issues"])
    active = client.get(f"/api/projects/{session_id}/fis/active")
    assert active.status_code == 200
