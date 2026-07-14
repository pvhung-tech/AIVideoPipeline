from pathlib import Path

from fastapi.testclient import TestClient

from app.config.dependencies import getProjectService
from app.main import createApp
from app.repositories.sqlite_project_repository import SQLiteProjectRepository
from app.services.project_service import ProjectService


def testScriptsApiImportsTxtAndSrtIntoActiveProject(tmp_path: Path) -> None:
    app = createApp()
    projectService = ProjectService(SQLiteProjectRepository(tmp_path / "app-data"))
    app.dependency_overrides[getProjectService] = lambda: projectService
    client = TestClient(app)
    projectsDirectory = tmp_path / "projects"
    projectsDirectory.mkdir()
    client.post(
        "/api/projects",
        json={"name": "Demo", "parentDirectory": str(projectsDirectory)},
    )
    txtPath = tmp_path / "script.txt"
    txtPath.write_text("A valid text script.", encoding="utf-8")
    srtPath = tmp_path / "subtitle.srt"
    srtPath.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nHello world\n",
        encoding="utf-8",
    )

    txtResponse = client.post("/api/scripts/import", json={"path": str(txtPath)})
    srtResponse = client.post("/api/scripts/import", json={"path": str(srtPath)})

    assert txtResponse.status_code == 200
    assert txtResponse.json()["data"]["format"] == "txt"
    assert txtResponse.json()["data"]["sceneCount"] == 1
    assert srtResponse.status_code == 200
    assert srtResponse.json()["data"]["cueCount"] == 1
    assert srtResponse.json()["data"]["scenes"][0]["startMilliseconds"] == 0

    scenesResponse = client.get("/api/scripts/scenes")
    updateResponse = client.put(
        "/api/scripts/scenes/scene-0001",
        json={"text": "Edited scene"},
    )
    reloadedResponse = client.get("/api/scripts/scenes")

    assert scenesResponse.status_code == 200
    assert scenesResponse.json()["data"]["sceneCount"] == 1
    assert updateResponse.status_code == 200
    assert reloadedResponse.json()["data"]["scenes"][0]["text"] == "Edited scene"
    activeProject = projectService.getCurrentProject()
    assert activeProject is not None
    assert (activeProject.path / "script" / "source.srt").is_file()
    assert (activeProject.path / "script" / "scenes.json").is_file()
    assert not (activeProject.path / "script" / "source.txt").exists()


def testScriptsApiReturnsValidationErrorForEmptyTxt(tmp_path: Path) -> None:
    app = createApp()
    projectService = ProjectService(SQLiteProjectRepository(tmp_path / "app-data"))
    app.dependency_overrides[getProjectService] = lambda: projectService
    client = TestClient(app)
    projectsDirectory = tmp_path / "projects"
    projectsDirectory.mkdir()
    client.post(
        "/api/projects",
        json={"name": "Demo", "parentDirectory": str(projectsDirectory)},
    )
    emptyPath = tmp_path / "empty.txt"
    emptyPath.write_text("   ", encoding="utf-8")

    response = client.post("/api/scripts/import", json={"path": str(emptyPath)})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EMPTY_SCRIPT"
