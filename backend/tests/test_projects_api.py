from pathlib import Path

from fastapi.testclient import TestClient

from app.config.dependencies import (
    getMediaFingerprintBackfillService,
    getMediaMetadataBackfillService,
    getProjectService,
)
from app.main import createApp
from app.project.project_model import Project
from app.repositories.sqlite_project_repository import SQLiteProjectRepository
from app.services.project_service import ProjectService


class FakeMetadataBackfillService:
    def __init__(self) -> None:
        self.startedProjectId: str | None = None

    def startForProject(self, project: Project) -> None:
        self.startedProjectId = project.id


class FakeFingerprintBackfillService:
    def __init__(self) -> None:
        self.startedProjectId: str | None = None

    def startForProject(self, project: Project) -> None:
        self.startedProjectId = project.id


def testProjectApiSupportsCompletePhaseOneWorkflow(tmp_path: Path) -> None:
    app = createApp()
    service = ProjectService(SQLiteProjectRepository(tmp_path / "app-data"))
    backfillService = FakeMetadataBackfillService()
    fingerprintBackfillService = FakeFingerprintBackfillService()
    app.dependency_overrides[getProjectService] = lambda: service
    app.dependency_overrides[getMediaMetadataBackfillService] = lambda: backfillService
    app.dependency_overrides[getMediaFingerprintBackfillService] = (
        lambda: fingerprintBackfillService
    )
    client = TestClient(app)
    projectsDirectory = tmp_path / "projects"
    projectsDirectory.mkdir()

    createResponse = client.post(
        "/api/projects",
        json={"name": "Demo Project", "parentDirectory": str(projectsDirectory)},
    )
    assert createResponse.status_code == 201
    projectPath = Path(createResponse.json()["data"]["path"])

    saveResponse = client.put("/api/projects/current", json={"name": "Updated Project"})
    assert saveResponse.status_code == 200
    assert saveResponse.json()["data"]["name"] == "Updated Project"

    closeResponse = client.post("/api/projects/close")
    assert closeResponse.status_code == 200
    assert client.get("/api/projects/current").json()["data"] is None

    openResponse = client.post("/api/projects/open", json={"path": str(projectPath)})
    assert openResponse.status_code == 200
    assert openResponse.json()["data"]["name"] == "Updated Project"
    assert backfillService.startedProjectId == openResponse.json()["data"]["id"]
    assert (
        fingerprintBackfillService.startedProjectId
        == openResponse.json()["data"]["id"]
    )

    recentResponse = client.get("/api/projects/recent")
    assert recentResponse.status_code == 200
    assert recentResponse.json()["data"]["projects"][0]["path"] == str(projectPath)


def testProjectApiReturnsStandardErrorResponse(tmp_path: Path) -> None:
    app = createApp()
    service = ProjectService(SQLiteProjectRepository(tmp_path / "app-data"))
    app.dependency_overrides[getProjectService] = lambda: service
    client = TestClient(app)

    response = client.put("/api/projects/current", json={})

    assert response.status_code == 409
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "NO_ACTIVE_PROJECT"
