from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from ruflex.api.main import app


def _slice_frame(rows: int = 60) -> pd.DataFrame:
    records = []
    for index in range(rows):
        temperature = 5.0 + index * 0.75
        torque = 18.0 + (index * 7) % 65
        records.append({
            "site": "A" if index % 2 == 0 else "B",
            "event_time": f"2026-01-{1 + index % 28:02d}",
            "temperature": temperature,
            "torque": torque,
            "target": int(temperature + torque > 58),
        })
    return pd.DataFrame(records)


def test_slice_lab_uses_original_validation_source_rows_and_persists_all_slice_kinds(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "slice-lab"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Slice Lab"}).json()["session_id"]
    frame = _slice_frame()
    confirmed = client.post(
        "/api/projects/dataset/confirm",
        json={
            "session_id": session_id,
            "csv_text": frame.to_csv(index=False),
            "target": "target",
            "task": "binary_classification",
            "id_columns": ["site", "event_time"],
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    generalization = client.post(
        "/api/projects/generalization/contracts",
        json={
            "session_id": session_id,
            "intended_use": "Validate deployment across declared sites",
            "novelty_axes": [
                {
                    "axis": "site",
                    "expected_future_relation": "unseen deployment site",
                    "evaluation_requirement": "hold out complete sites",
                }
            ],
            "supported_scope": [
                {"field": "site", "operator": "in", "value": ["A"], "rationale": "Validated deployment site"}
            ],
            "forbidden_scope": [
                {"field": "site", "operator": "in", "value": ["B"], "rationale": "External site is out of scope"}
            ],
            "unsupported_action": "REVIEW",
        },
    )
    assert generalization.status_code == 201, generalization.text
    generalization_id = generalization.json()["contract"]["contract_id"]
    trained = client.post(
        "/api/projects/training/run",
        json={
            "session_id": session_id,
            "model_kind": "logistic_regression",
            "seed": 17,
            "max_epochs": 1,
            "learning_rate": 0.01,
            "batch_size": 16,
            "patience": 1,
            "validation_fraction": 0.2,
            "test_fraction": 0.2,
            "max_rules": 3,
        },
    )
    assert trained.status_code == 201, trained.text
    evaluation = client.post(
        "/api/projects/analyses/evaluations",
        json={"session_id": session_id, "run_id": trained.json()["run_id"]},
    )
    assert evaluation.status_code == 201, evaluation.text
    evidence = evaluation.json()["prediction_preview"]
    assert evidence and all(row["source_row"] is not None for row in evidence)
    manual_row = evidence[0]["source_row"]

    created = client.post(
        "/api/projects/analyses/slices",
        json={
            "session_id": session_id,
            "evaluation_id": evaluation.json()["evaluation_id"],
            "metric": "f1",
            "definitions": [
                {"name": "warm", "kind": "numeric_range", "field": "temperature", "minimum": 20.0, "maximum": 55.0},
                {"name": "both sites", "kind": "group", "field": "site", "values": ["A", "B"]},
                {"name": "january", "kind": "temporal", "field": "event_time", "start": "2026-01-01", "end": "2026-01-31"},
                {"name": "one inspected case", "kind": "manual", "source_rows": [manual_row]},
            ],
        },
    )
    assert created.status_code == 201, created.text
    analysis = created.json()
    assert analysis["source_split"] == "validation"
    assert analysis["test_status"] == "LOCKED_NOT_EVALUATED"
    assert analysis["generalization_contract_id"] == generalization_id
    assert {row["kind"] for row in analysis["results"]} == {"numeric_range", "group", "temporal", "manual"}
    group_result = next(row for row in analysis["results"] if row["kind"] == "group")
    assert group_result["n"] == len(evidence)
    assert group_result["scope_disposition"] == "BLOCK"
    assert any("Forbidden scope rule matched" in reason for reason in group_result["scope_reasons"])
    assert next(row for row in analysis["results"] if row["kind"] == "temporal")["n"] == len(evidence)
    assert next(row for row in analysis["results"] if row["kind"] == "manual")["n"] == 1

    latest = client.get(f"/api/projects/{session_id}/analyses/slices/latest")
    assert latest.status_code == 200
    assert latest.json()["analysis_id"] == analysis["analysis_id"]

    lineage = client.get(f"/api/projects/{session_id}/lineage")
    assert lineage.status_code == 200, lineage.text
    assert any(
        edge["relation"] == "scopes_slice_analysis"
        and edge["source"] == f"generalization:{generalization_id}"
        and edge["target"] == f"slice:{analysis['analysis_id']}"
        for edge in lineage.json()["edges"]
    )
