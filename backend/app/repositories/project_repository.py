from pathlib import Path
from typing import Protocol

from app.project.project_model import Project


class ProjectRepository(Protocol):
    def createProject(self, project: Project) -> Project: ...

    def saveProject(self, project: Project) -> Project: ...

    def openProject(self, projectPath: Path) -> Project: ...

    def listRecentProjects(self, limit: int) -> list[Project]: ...
