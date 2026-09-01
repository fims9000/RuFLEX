from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import pickle
import os
import subprocess
import sys

import pytest
import yaml
from fastapi.testclient import TestClient

from ruflex.api.main import app
from ruflex.application.projects import ProjectReadOnlyError, ProjectService, ProjectValidationError, UnsupportedProjectSchemaError
from ruflex.domain.project import PROJECT_DIRECTORY_NAMES


def test_create_save_reopen_preserves_identity_and_skeleton(tmp_path: Path) -> None:
    service = ProjectService()
    root = tmp_path / "pump-01"

    created = service.create(root, name="Pump-01", description="Studio fixture")
    reopened = service.open(root)

    assert created.id == reopened.id
    assert reopened.summary().name == "Pump-01"
    assert (root / "project.yaml").is_file()
    assert {path.name for path in root.iterdir()} == {"project.yaml", *PROJECT_DIRECTORY_NAMES}


def test_read_only_project_rejects_save(tmp_path: Path) -> None:
    service = ProjectService()
    root = tmp_path / "read-only"
    service.create(root, name="Read only")

    with pytest.raises(ProjectReadOnlyError):
        service.save(service.open(root, read_only=True))


def test_future_schema_fails_closed_without_modifying_manifest(tmp_path: Path) -> None:
    service = ProjectService()
    root = tmp_path / "future"
    service.create(root, name="Future")
    manifest_path = root / "project.yaml"
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    payload["schema_version"] = 999
    manifest_path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    before = manifest_path.read_bytes()

    with pytest.raises(UnsupportedProjectSchemaError):
        service.open(root)

    assert manifest_path.read_bytes() == before


def test_api_create_and_open_lifecycle(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "api-project"
    create_response = client.post("/api/projects", json={"path": str(root), "name": "API project"})
    save_response = client.post("/api/projects/save", json={"session_id": create_response.json()["session_id"]})
    open_response = client.post("/api/projects/open", json={"path": str(root)})

    assert create_response.status_code == 201
    assert save_response.status_code == 200
    assert open_response.status_code == 200
    assert create_response.json()["project_id"] == open_response.json()["project_id"]
    assert client.get("/api/health").json()["status"] == "ok"


def test_api_read_only_session_rejects_all_mutations(tmp_path: Path) -> None:
    client = TestClient(app)
    root = tmp_path / "api-read-only"
    created = client.post("/api/projects", json={"path": str(root), "name": "Read only"})
    assert created.status_code == 201
    opened = client.post("/api/projects/open", json={"path": str(root), "read_only": True})
    assert opened.status_code == 200
    session_id = opened.json()["session_id"]

    save = client.post("/api/projects/save", json={"session_id": session_id})
    metadata = client.post("/api/projects/metadata", json={"session_id": session_id, "description": "must fail"})

    assert save.status_code == 403
    assert metadata.status_code == 403
    assert client.post("/api/projects/save", json={"path": str(root)}).status_code == 422


def test_workspace_root_rejects_relative_and_absolute_escapes(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    service = ProjectService(workspace_root=workspace_root)

    with pytest.raises(ProjectValidationError, match="traversal"):
        service.create(Path("../escape"), name="Escape")
    with pytest.raises(ProjectValidationError, match="escapes"):
        service.create(tmp_path / "outside", name="Outside")


def test_symlink_component_is_rejected(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = workspace_root / "linked"
    link.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ProjectValidationError, match="symlink"):
        ProjectService(workspace_root=workspace_root).create(link / "project", name="Linked")


def test_corrupt_yaml_and_malformed_uuid_fail_closed(tmp_path: Path) -> None:
    service = ProjectService()
    root = tmp_path / "invalid"
    service.create(root, name="Invalid")
    manifest_path = root / "project.yaml"
    manifest_path.write_text("project_id: [not valid yaml", encoding="utf-8")
    with pytest.raises(ProjectValidationError, match="invalid YAML"):
        service.open(root)

    service.create(tmp_path / "bad-id", name="Bad ID")
    bad_path = tmp_path / "bad-id" / "project.yaml"
    payload = yaml.safe_load(bad_path.read_text(encoding="utf-8"))
    payload["project_id"] = "not-a-uuid"
    bad_path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(ProjectValidationError, match="failed validation"):
        service.open(tmp_path / "bad-id")


def test_failed_atomic_save_preserves_previous_manifest(tmp_path: Path) -> None:
    service = ProjectService()
    root = tmp_path / "atomic"
    project = service.create(root, name="Atomic")
    manifest_path = root / "project.yaml"
    before = manifest_path.read_bytes()

    with patch("ruflex.application.projects.os.replace", side_effect=OSError("disk failure")):
        with pytest.raises(OSError, match="disk failure"):
            service.update_metadata(project, description="must not persist")

    assert manifest_path.read_bytes() == before
    assert not list(root.glob(".project-*.yaml"))


def test_safe_open_does_not_invoke_executable_or_legacy_loaders(tmp_path: Path) -> None:
    service = ProjectService()
    root = tmp_path / "safe-open"
    service.create(root, name="Safe open")

    import torch
    from ruflex.sdk.project import Project as LegacyProject

    with (
        patch.object(torch, "load", side_effect=AssertionError("torch.load must not run")),
        patch.object(pickle, "load", side_effect=AssertionError("pickle.load must not run")),
        patch.object(LegacyProject, "load", side_effect=AssertionError("legacy loader must not run")),
    ):
        project = service.open(root)

    assert project.id


def test_canonical_api_startup_does_not_import_legacy_or_streamlit() -> None:
    script = """
import builtins
original_import = builtins.__import__
blocked = ('streamlit', 'torch', 'ruflex.sdk', 'ruflex.toolbox', 'ruflex.ui')
def guarded(name, *args, **kwargs):
    if name.startswith(blocked):
        raise AssertionError(f'canonical startup imported blocked module: {name}')
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded
import ruflex.api.main
"""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path("src").resolve())
    result = subprocess.run([sys.executable, "-c", script], text=True, capture_output=True, env=environment)
    assert result.returncode == 0, result.stderr or result.stdout
