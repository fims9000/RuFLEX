from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from ruflex.api.main import app


@pytest.mark.parametrize("invalid_seed", [-1, 4_294_967_296, 1.5, ""])
@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/projects/dataset/splits", {"family": "RANDOM", "split_seed": None}),
        ("/api/projects/training/run", {"model_kind": "decision_tree", "seed": None}),
        ("/api/projects/training/run", {"model_kind": "decision_tree", "split_seed": None}),
        ("/api/projects/training/run", {"model_kind": "decision_tree", "training_seed": None}),
        ("/api/projects/training/study-jobs", {"model_kind": "decision_tree", "seeds": [3, None, 7]}),
    ],
)
def test_invalid_seed_is_rejected_before_project_execution(path: str, payload: dict, invalid_seed: object) -> None:
    body = {"session_id": str(uuid4()), **payload}
    for key, value in body.items():
        if value is None:
            body[key] = invalid_seed
        elif isinstance(value, list):
            body[key] = [invalid_seed if item is None else item for item in value]
    response = TestClient(app).post(path, json=body)
    assert response.status_code == 422, response.text
