from __future__ import annotations

from fastapi.testclient import TestClient

from ruflex.api import main as api_main
from ruflex.api.main import app


def test_mutation_persistence_oserrors_are_not_reported_as_validation(tmp_path, monkeypatch) -> None:
    client = TestClient(app)
    project = client.post("/api/projects", json={"path": str(tmp_path / "project"), "name": "Persistence failure"}).json()
    session_id = project["session_id"]

    def persistence_error(*args, **kwargs):
        raise OSError("simulated storage failure")

    monkeypatch.setattr(api_main, "create_split_contract", persistence_error)
    split = client.post("/api/projects/dataset/splits", json={"session_id": session_id, "family": "RANDOM", "split_seed": 42})
    assert split.status_code == 500
    assert split.json()["code"] == "PRODUCT_ERROR"

    from ruflex.application import training

    monkeypatch.setattr(training, "train_model", persistence_error)
    run = client.post("/api/projects/training/run", json={"session_id": session_id, "model_kind": "flat_neuro_fuzzy"})
    assert run.status_code == 500
    assert run.json()["code"] == "PRODUCT_ERROR"

    monkeypatch.setattr(training, "start_study_job", persistence_error)
    study = client.post("/api/projects/training/study-jobs", json={
        "session_id": session_id,
        "model_kind": "flat_neuro_fuzzy",
        "seeds": [1, 2, 3],
    })
    assert study.status_code == 500
    assert study.json()["code"] == "PRODUCT_ERROR"
