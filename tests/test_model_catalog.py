from fastapi.testclient import TestClient

from ruflex.api.main import app


def test_model_catalog_exposes_capabilities_without_claiming_unavailable_adapters() -> None:
    response = TestClient(app).get("/api/model-catalog")
    assert response.status_code == 200
    entries = {entry["key"]: entry for entry in response.json()}
    assert entries["mamdani"]["available"] is True
    assert entries["mamdani"]["capabilities"]["exact_semantic_trace"] is True
    assert entries["decision_tree"]["available"] is True
    assert entries["decision_tree"]["capabilities"]["exact_tree_path"] is True
    assert entries["decision_tree"]["capabilities"]["exact_semantic_trace"] is False
    assert entries["linear"]["available"] is True
    assert entries["linear"]["capabilities"]["fit"] is True
