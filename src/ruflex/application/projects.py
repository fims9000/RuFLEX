from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import ValidationError

from ruflex.domain.project import PROJECT_DIRECTORY_NAMES, PROJECT_SCHEMA_VERSION, Project, ProjectManifest


class ProjectError(RuntimeError):
    """Base error for canonical project lifecycle operations."""


class ProjectAlreadyExistsError(ProjectError):
    pass


class ProjectReadOnlyError(ProjectError):
    pass


class ProjectValidationError(ProjectError):
    pass


class UnsupportedProjectSchemaError(ProjectValidationError):
    pass


class ProjectService:
    """Safe create/open/save operations for declarative Studio workspaces."""

    manifest_filename = "project.yaml"

    def __init__(self, *, workspace_root: Path | None = None) -> None:
        self.workspace_root = None if workspace_root is None else Path(workspace_root).expanduser().resolve()

    def create(self, path: Path, *, name: str, description: str | None = None) -> Project:
        root = self._create_root(path)
        manifest = ProjectManifest(name=name, description=description)
        for directory in PROJECT_DIRECTORY_NAMES:
            (root / directory).mkdir()
        project = Project(root=root, manifest=manifest)
        self._write_manifest(project)
        return project

    def open(self, path: Path, *, read_only: bool = False) -> Project:
        root = self._resolve_existing_root(path)
        manifest_path = root / self.manifest_filename
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise ProjectValidationError(f"Project manifest must be a regular file: {manifest_path}")
        try:
            payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            raise ProjectValidationError(f"Project manifest is invalid YAML: {error}") from error
        if not isinstance(payload, dict):
            raise ProjectValidationError("Project manifest must contain a YAML mapping.")
        schema_version = payload.get("schema_version")
        if not isinstance(schema_version, int):
            raise ProjectValidationError("Project manifest has no integer schema_version.")
        if schema_version > PROJECT_SCHEMA_VERSION:
            raise UnsupportedProjectSchemaError(
                f"Project schema version {schema_version} is newer than supported version {PROJECT_SCHEMA_VERSION}."
            )
        if schema_version != PROJECT_SCHEMA_VERSION:
            raise ProjectValidationError(
                f"Project schema version {schema_version} requires an explicit migration before opening."
            )
        try:
            manifest = ProjectManifest.model_validate(payload)
        except ValidationError as error:
            raise ProjectValidationError(f"Project manifest failed validation: {error}") from error
        return Project(root=root, manifest=manifest, read_only=read_only)

    def save(self, project: Project) -> Project:
        if project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot be saved.")
        project.manifest.modified_at = datetime.now(timezone.utc)
        self._write_manifest(project)
        return project

    def update_metadata(self, project: Project, *, description: str | None) -> Project:
        if project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot be changed.")
        project.manifest.description = description
        return self.save(project)

    def validate(self, path: Path) -> Project:
        return self.open(path, read_only=True)

    def _create_root(self, path: Path) -> Path:
        root = self._normalize_root(path)
        if root.exists():
            raise ProjectAlreadyExistsError(f"Refusing to create a project over an existing path: {root}")
        root.mkdir(parents=True)
        return root.resolve()

    def _resolve_existing_root(self, path: Path) -> Path:
        root = self._normalize_root(path)
        if not root.is_dir() or root.is_symlink():
            raise ProjectValidationError(f"Project root must be an existing non-symlink directory: {root}")
        return root.resolve()

    def _normalize_root(self, path: Path) -> Path:
        supplied = Path(path).expanduser()
        if ".." in supplied.parts:
            raise ProjectValidationError("Project paths must not contain '..' traversal segments.")
        root = supplied if supplied.is_absolute() else (self.workspace_root / supplied if self.workspace_root else supplied)
        absolute_root = root.absolute()
        for parent in (absolute_root, *absolute_root.parents):
            if parent.is_symlink():
                raise ProjectValidationError(f"Project path contains a symlink component: {parent}")
        resolved = absolute_root.resolve(strict=False)
        if self.workspace_root is not None:
            try:
                resolved.relative_to(self.workspace_root)
            except ValueError as error:
                raise ProjectValidationError("Project path escapes the configured workspace root.") from error
        return resolved

    def _write_manifest(self, project: Project) -> None:
        root = project.root.resolve()
        manifest_path = root / self.manifest_filename
        if manifest_path.parent != root:
            raise ProjectValidationError("Project manifest path escapes the project root.")
        serialized = yaml.safe_dump(project.manifest.model_dump(mode="json"), allow_unicode=True, sort_keys=False)
        fd, temporary_name = tempfile.mkstemp(prefix=".project-", suffix=".yaml", dir=root)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, manifest_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
