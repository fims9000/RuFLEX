from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from ruflex.api.main import app


def _frame(rows: int = 36) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "site": ["north" if index % 2 == 0 else "south" for index in range(rows)],
            "temperature": [10.0 + index * 0.5 for index in range(rows)],
            "target": [0 if index < rows // 2 else 1 for index in range(rows)],
        }
    )


def test_active_generalization_contract_reopens_and_is_lineage_addressable(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "generalization-reopen"
    session_id = client.post(
        "/api/projects",
        json={"path": str(root), "name": "Generalization reopen"},
    ).json()["session_id"]

    confirmed = client.post(
        "/api/projects/dataset/confirm",
        json={
            "session_id": session_id,
            "csv_text": _frame().to_csv(index=False),
            "target": "target",
            "task": "binary_classification",
            "id_columns": ["site"],
        },
    )
    assert confirmed.status_code == 200, confirmed.text

    created = client.post(
        "/api/projects/generalization/contracts",
        json={
            "session_id": session_id,
            "intended_use": "Evaluate deployment to unseen sites",
            "novelty_axes": [
                {
                    "axis": "site",
                    "expected_future_relation": "unseen deployment site",
                    "evaluation_requirement": "hold out complete sites",
                }
            ],
            "supported_scope": [
                {
                    "field": "site",
                    "operator": "in",
                    "value": ["north"],
                    "rationale": "Product V1 deployment is declared only for north-site metadata.",
                }
            ],
            "forbidden_scope": [
                {
                    "field": "site",
                    "operator": "in",
                    "value": ["south"],
                    "rationale": "South-site deployment is outside the declared scope.",
                }
            ],
            "unsupported_action": "REVIEW",
        },
    )
    assert created.status_code == 201, created.text
    contract_id = created.json()["contract"]["contract_id"]
    assert created.json()["lint"]["can_freeze"] is True

    allowed = client.post(
        f"/api/projects/generalization/contracts/{contract_id}/classify",
        json={"session_id": session_id, "sample_metadata": {"site": "north"}},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["disposition"] == "ALLOW"

    blocked = client.post(
        f"/api/projects/generalization/contracts/{contract_id}/classify",
        json={"session_id": session_id, "sample_metadata": {"site": "south"}},
    )
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["disposition"] == "BLOCK"

    review = client.post(
        f"/api/projects/generalization/contracts/{contract_id}/classify",
        json={"session_id": session_id, "sample_metadata": {"site": "west"}},
    )
    assert review.status_code == 200, review.text
    assert review.json()["disposition"] == "REVIEW"

    active = client.get(f"/api/projects/{session_id}/generalization/contracts/active")
    assert active.status_code == 200, active.text
    assert active.json()["contract"]["contract_id"] == contract_id

    frozen = client.post(
        f"/api/projects/generalization/contracts/{contract_id}/freeze",
        json={"session_id": session_id},
    )
    assert frozen.status_code == 200, frozen.text
    assert frozen.json()["contract"]["frozen_at"] is not None

    specific = client.get(f"/api/projects/{session_id}/generalization/contracts/{contract_id}")
    assert specific.status_code == 200, specific.text
    assert specific.json()["contract"]["frozen_at"] is not None

    lineage = client.get(f"/api/projects/{session_id}/lineage")
    assert lineage.status_code == 200, lineage.text
    generalization_node = next(
        node for node in lineage.json()["nodes"] if node["kind"] == "generalization_contract"
    )
    assert generalization_node["object_id"] == contract_id
    assert generalization_node["status"] == "FROZEN"

    assert client.post("/api/projects/close", json={"session_id": session_id}).status_code == 204
    reopened = client.post(
        "/api/projects/open",
        json={"path": str(root), "read_only": False},
    )
    assert reopened.status_code == 200, reopened.text
    reopened_session = reopened.json()["session_id"]

    restored = client.get(f"/api/projects/{reopened_session}/generalization/contracts/active")
    assert restored.status_code == 200, restored.text
    assert restored.json()["contract"]["contract_id"] == contract_id
    assert restored.json()["contract"]["frozen_at"] is not None
