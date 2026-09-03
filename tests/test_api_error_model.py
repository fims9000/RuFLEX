from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from ruflex.api.main import app


def test_product_http_errors_keep_legacy_detail_and_add_stable_code() -> None:
    response = TestClient(app).post("/api/projects/close", json={"session_id": str(uuid4())})

    assert response.status_code == 404
    assert response.json()["code"] == "RESOURCE_NOT_FOUND"
    assert "expired" in response.json()["detail"]


def test_invalid_requests_have_a_typed_code() -> None:
    response = TestClient(app).post("/api/projects/save", json={"session_id": "not-a-uuid"})

    assert response.status_code == 422
    assert response.json()["code"] == "REQUEST_INVALID"
    assert isinstance(response.json()["detail"], list)
