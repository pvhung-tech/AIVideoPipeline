import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.project.errors import ProjectError
from app.project.project_model import Project
from app.repositories.sqlite_project_repository import (
    PROJECT_DIRECTORIES,
    SQLiteProjectRepository,
)


def createProject(projectPath: Path, name: str = "Demo") -> Project:
    timestamp = datetime.now(UTC)
    return Project(
        id="project-id",
        name=name,
        path=projectPath,
        createdAt=timestamp,
        updatedAt=timestamp,
    )


def testRepositoryCreatesProjectStructureAndManifest(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "app-data")
    project = createProject(tmp_path / "projects" / "Demo")
    project.path.parent.mkdir()

    repository.createProject(project)

    manifest = json.loads((project.path / "project.json").read_text("utf-8"))
    assert manifest["id"] == project.id
    assert "path" not in manifest
    for directoryName in PROJECT_DIRECTORIES:
        assert (project.path / directoryName).is_dir()


def testRepositorySavesOpensAndListsRecentProject(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "app-data")
    project = createProject(tmp_path / "projects" / "Demo")
    project.path.parent.mkdir()
    repository.createProject(project)
    updated = replace(project, name="Updated", updatedAt=datetime.now(UTC))

    repository.saveProject(updated)
    opened = repository.openProject(project.path)
    recent = repository.listRecentProjects(10)

    assert opened.name == "Updated"
    assert recent == [updated]


def testRepositoryRejectsInvalidProjectFile(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "app-data")
    projectPath = tmp_path / "Broken"
    projectPath.mkdir()
    (projectPath / "project.json").write_text("not-json", encoding="utf-8")

    with pytest.raises(ProjectError) as error:
        repository.openProject(projectPath)

    assert error.value.code == "INVALID_PROJECT_FILE"
