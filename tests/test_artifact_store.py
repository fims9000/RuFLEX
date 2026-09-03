import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ruflex.api.main import app
from ruflex.application.artifacts import ArtifactIntegrityError, ArtifactMetadata, ArtifactStore


def test_content_addressed_ingest_deduplicates_and_rebuilds_index(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    first = store.ingest_bytes(b"canonical evidence", metadata=ArtifactMetadata(media_type="text/plain", original_name="evidence.txt", source_kind="generated"))
    second = store.ingest_bytes(b"canonical evidence", metadata=ArtifactMetadata(media_type="text/plain", original_name="copy.txt", source_kind="generated"))

    assert first.sha256 == second.sha256
    assert store.verify(first).valid
    assert store.rebuild_index().artifact_count == 1
    assert (tmp_path / "artifacts" / "sha256" / first.sha256[:2] / first.sha256).read_bytes() == b"canonical evidence"


def test_tamper_and_materialization_escape_are_rejected(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    reference = store.ingest_bytes(b"safe bytes", metadata=ArtifactMetadata(media_type="application/octet-stream", source_kind="imported"))
    blob = tmp_path / "artifacts" / "sha256" / reference.sha256[:2] / reference.sha256
    blob.write_bytes(b"tampered")

    assert not store.verify(reference).valid
    with pytest.raises(ArtifactIntegrityError, match="mismatch"):
        store.open(reference)
    with pytest.raises(ArtifactIntegrityError, match="escapes"):
        store.materialize(reference, Path("../escape.bin"))


def test_verify_rejects_metadata_that_does_not_describe_the_canonical_blob(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    reference = store.ingest_bytes(b"canonical bytes", metadata=ArtifactMetadata(media_type="text/plain", source_kind="generated"))
    receipt_path = tmp_path / "objects" / "artifacts" / f"{reference.sha256}.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["size_bytes"] += 1
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    verification = store.verify(reference)
    assert not verification.valid
    assert "metadata" in verification.message.lower()


def test_failed_atomic_ingest_leaves_no_metadata_or_blob(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = ArtifactStore(tmp_path)
    monkeypatch.setattr("ruflex.application.artifacts.os.replace", lambda *_: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        store.ingest_bytes(b"interrupted", metadata=ArtifactMetadata(media_type="text/plain", source_kind="generated"))
    assert not list((tmp_path / "objects" / "artifacts").glob("*.json"))


def test_artifact_inventory_is_available_through_an_open_studio_session(tmp_path: Path) -> None:
    client = TestClient(app)
    created = client.post("/api/projects", json={"path": str(tmp_path / "studio"), "name": "Studio"})
    assert created.status_code == 201
    session_id = created.json()["session_id"]
    ingested = client.post("/api/projects/artifacts/text", json={"session_id": session_id, "text": "studio evidence", "original_name": "evidence.txt"})
    response = client.get(f"/api/projects/{session_id}/artifacts")
    assert ingested.status_code == 201
    assert response.status_code == 200
    assert response.json()[0]["original_name"] == "evidence.txt"
