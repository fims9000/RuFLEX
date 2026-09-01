from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from ruflex.api.main import app


def _frame(rows: int = 60) -> pd.DataFrame:
    records = []
    for index in range(rows):
        temperature = 10.0 + index * 0.5
        pressure = 2.0 + ((index * 7) % 30) / 10.0
        wear = ((index * 11) % 20) / 20.0
        target = int(temperature + 5.0 * pressure + 8.0 * wear > 40.0)
        records.append({"temperature": temperature, "pressure": pressure, "wear": wear, "target": target})
    return pd.DataFrame(records)


def test_expert_correction_refits_only_unlocked_sugeno_consequents_on_train(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "expert-correction"
    session_id = client.post("/api/projects", json={"path": str(root), "name": "Expert correction"}).json()["session_id"]
    confirmed = client.post(
        "/api/projects/dataset/confirm",
        json={
            "session_id": session_id,
            "csv_text": _frame().to_csv(index=False),
            "target": "target",
            "task": "binary_classification",
            "id_columns": [],
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    created = client.post("/api/projects/fis/default", json={"session_id": session_id, "name": "Expert Sugeno"})
    assert created.status_code == 201, created.text
    spec = created.json()
    spec["system_type"] = "sugeno"
    constants = [0.1, 0.5, 0.9]
    for rule, value in zip(spec["rules"], constants, strict=True):
        rule["sugeno_consequent"] = {"kind": "constant", "constant": value, "coefficients": {}, "intercept": 0.0}
    saved = client.post("/api/projects/fis/save", json={"session_id": session_id, "spec": spec})
    assert saved.status_code == 200, saved.text
    source = saved.json()
    locked_rule_id = source["rules"][0]["rule_id"]
    locked_constant = source["rules"][0]["sugeno_consequent"]["constant"]

    corrected = client.post(
        "/api/projects/fis/expert-correction",
        json={"session_id": session_id, "locked_rule_ids": [locked_rule_id], "seed": 17},
    )
    assert corrected.status_code == 201, corrected.text
    result = corrected.json()
    correction = result["correction"]
    fitted = result["fis"]
    assert correction["source_semantic_hash"] == source["semantic_hash"]
    assert correction["result_semantic_hash"] == fitted["semantic_hash"]
    assert correction["result_semantic_hash"] != correction["source_semantic_hash"]
    assert correction["locked_rule_ids"] == [locked_rule_id]
    assert locked_rule_id not in correction["fitted_rule_ids"]
    assert correction["test_status"] == "LOCKED_NOT_EVALUATED"
    assert correction["train_row_count"] < len(_frame())
    assert correction["train_rmse_after"] <= correction["train_rmse_before"] + 1e-10
    assert correction["validation_row_count"] > 0
    assert correction["validation_rmse_before"] is not None
    assert correction["validation_rmse_after"] is not None
    assert correction["test_status"] == "LOCKED_NOT_EVALUATED"
    assert fitted["rules"][0]["sugeno_consequent"]["constant"] == locked_constant
    assert any(
        fitted["rules"][index]["sugeno_consequent"]["constant"] != source["rules"][index]["sugeno_consequent"]["constant"]
        for index in (1, 2)
    )

    assert client.post("/api/projects/close", json={"session_id": session_id}).status_code == 204
    reopened = client.post("/api/projects/open", json={"path": str(root), "read_only": False})
    assert reopened.status_code == 200, reopened.text
    latest = client.get(f"/api/projects/{reopened.json()['session_id']}/fis/expert-correction/latest")
    assert latest.status_code == 200, latest.text
    assert latest.json()["correction_id"] == correction["correction_id"]
    specific = client.get(
        f"/api/projects/{reopened.json()['session_id']}/fis/expert-correction/{correction['correction_id']}"
    )
    assert specific.status_code == 200, specific.text
    assert specific.json()["source_semantic_hash"] == correction["source_semantic_hash"]
