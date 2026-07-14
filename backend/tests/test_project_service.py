from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.project.errors import ProjectError
from app.project.project_model import Project
from app.services.project_service import ProjectService


class FakeProjectRepository:
    def __init__(self) -> None:
        self.projects: dict[Path, Project] = {}

    def createProject(self, project: Project) -> Project:
        self.projects[project.path] = project
        return project

    def saveProject(self, project: Project) -> Project:
        self.projects[project.path] = project
        return project

    def openProject(self, projectPath: Path) -> Project:
        return self.projects[projectPath]

    def listRecentProjects(self, limit: int) -> list[Project]:
        return list(self.projects.values())[:limit]


def testProjectServiceCreatesAndAutoSavesProject(tmp_path: Path) -> None:
    repository = FakeProjectRepository()
    service = ProjectService(repository)

    created = service.createProject("  Demo Project  ", tmp_path)
    saved = service.saveCurrentProject("Renamed Project")

    assert created.name == "Demo Project"
    assert created.path == tmp_path / "Demo-Project"
    assert saved.name == "Renamed Project"
    assert saved.updatedAt >= created.updatedAt
    assert repository.projects[created.path] == saved


def testProjectServiceOpensClosesAndListsRecentProjects(tmp_path: Path) -> None:
    repository = FakeProjectRepository()
    service = ProjectService(repository)
    project = Project(
        id="project-id",
        name="Demo",
        path=tmp_path / "Demo",
        createdAt=datetime.now(UTC),
        updatedAt=datetime.now(UTC),
    )
    repository.projects[project.path] = project

    assert service.openProject(project.path) == project
    assert service.closeProject() == project
    assert service.getCurrentProject() is None
    assert service.listRecentProjects() == [project]


def testProjectServiceRejectsSaveWithoutActiveProject() -> None:
    service = ProjectService(FakeProjectRepository())

    with pytest.raises(ProjectError, match="No project is currently open") as error:
        service.saveCurrentProject()

    assert error.value.code == "NO_ACTIVE_PROJECT"
