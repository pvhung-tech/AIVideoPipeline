import re
import threading
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.project.errors import ProjectError
from app.project.project_model import Project
from app.repositories.project_repository import ProjectRepository


class ProjectService:
    def __init__(self, repository: ProjectRepository) -> None:
        self.repository = repository
        self.activeProject: Project | None = None
        self.lock = threading.RLock()

    def createProject(self, name: str, parentDirectory: Path) -> Project:
        normalizedName = self._normalizeName(name)
        projectPath = parentDirectory.expanduser().resolve() / self._slugify(
            normalizedName
        )
        timestamp = datetime.now(UTC)
        project = Project(
            id=str(uuid4()),
            name=normalizedName,
            path=projectPath,
            createdAt=timestamp,
            updatedAt=timestamp,
        )

        with self.lock:
            self.activeProject = self.repository.createProject(project)
            return self.activeProject

    def openProject(self, projectPath: Path) -> Project:
        with self.lock:
            self.activeProject = self.repository.openProject(projectPath)
            return self.activeProject

    def saveCurrentProject(self, name: str | None = None) -> Project:
        with self.lock:
            project = self._requireActiveProject()
            updatedName = (
                self._normalizeName(name) if name is not None else project.name
            )
            updatedProject = replace(
                project,
                name=updatedName,
                updatedAt=datetime.now(UTC),
            )
            self.activeProject = self.repository.saveProject(updatedProject)
            return self.activeProject

    def closeProject(self) -> Project:
        with self.lock:
            project = self._requireActiveProject()
            self.activeProject = None
            return project

    def getCurrentProject(self) -> Project | None:
        with self.lock:
            return self.activeProject

    def listRecentProjects(self, limit: int = 10) -> list[Project]:
        if limit < 1 or limit > 50:
            raise ProjectError(
                "INVALID_RECENT_PROJECT_LIMIT",
                "Recent project limit must be between 1 and 50.",
            )
        return self.repository.listRecentProjects(limit)

    def _requireActiveProject(self) -> Project:
        if self.activeProject is None:
            raise ProjectError("NO_ACTIVE_PROJECT", "No project is currently open.")
        return self.activeProject

    def _normalizeName(self, name: str) -> str:
        normalizedName = name.strip()
        if not normalizedName:
            raise ProjectError("INVALID_PROJECT_NAME", "Project name cannot be empty.")
        if len(normalizedName) > 120:
            raise ProjectError(
                "INVALID_PROJECT_NAME",
                "Project name cannot exceed 120 characters.",
            )
        return normalizedName

    def _slugify(self, name: str) -> str:
        slug = re.sub(r"[^\w\s-]", "", name, flags=re.UNICODE)
        slug = re.sub(r"[-\s]+", "-", slug).strip("-_")
        return slug or f"project-{uuid4().hex[:8]}"
