from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from ruflex.application.projects import ProjectError, ProjectService
from ruflex.domain.project import Project


class WorkspaceSessionError(ProjectError):
    """A request does not refer to a live Studio workspace session."""


@dataclass(slots=True)
class WorkspaceSession:
    """Ephemeral permission-bearing handle for one open Studio workspace.

    Project science and provenance remain canonical files on disk.  This object
    deliberately stores only process-local open-handle state, including the
    read-only invariant that HTTP mutations must preserve.
    """

    session_id: UUID
    project: Project


class WorkspaceSessionService:
    def __init__(self, project_service: ProjectService) -> None:
        self._project_service = project_service
        self._sessions: dict[UUID, WorkspaceSession] = {}

    def create(self, path, *, name: str, description: str | None = None) -> WorkspaceSession:
        return self._register(self._project_service.create(path, name=name, description=description))

    def open(self, path, *, read_only: bool = False) -> WorkspaceSession:
        return self._register(self._project_service.open(path, read_only=read_only))

    def get(self, session_id: UUID) -> WorkspaceSession:
        try:
            return self._sessions[session_id]
        except KeyError as error:
            raise WorkspaceSessionError("Workspace session is not open or has expired.") from error

    def save(self, session_id: UUID) -> WorkspaceSession:
        session = self.get(session_id)
        self._project_service.save(session.project)
        return session

    def update_metadata(self, session_id: UUID, *, description: str | None) -> WorkspaceSession:
        session = self.get(session_id)
        self._project_service.update_metadata(session.project, description=description)
        return session

    def close(self, session_id: UUID) -> None:
        if self._sessions.pop(session_id, None) is None:
            raise WorkspaceSessionError("Workspace session is not open or has expired.")

    def _register(self, project: Project) -> WorkspaceSession:
        session = WorkspaceSession(session_id=uuid4(), project=project)
        self._sessions[session.session_id] = session
        return session
