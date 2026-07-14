from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.config.dependencies import getProjectService, getTimelineMediaService
from app.main import createApp
from app.repositories.sqlite_project_repository import SQLiteProjectRepository
from app.services.project_service import ProjectService
from app.services.timeline_media_service import VisualMediaAssignment
from app.timeline.media_assets import TimelineMediaAsset, TimelineMediaAssetPage
from app.timeline.models import (
    Timeline,
    TimelineMediaType,
    TimelineScene,
    VisualClipRole,
)


class FakeTimelineMediaService:
    def listAssets(self) -> tuple[TimelineMediaAsset, ...]:
        return self.listAssetPage(0, None).assets

    def listAssetPage(
        self, offset: int = 0, limit: int | None = None
    ) -> TimelineMediaAssetPage:
        return TimelineMediaAssetPage(
            (
                TimelineMediaAsset(
                    "a" * 64,
                    TimelineMediaType.IMAGE,
                    "cached.jpg",
                    "file:///cache/cached.jpg",
                    100,
                    ("pexels",),
                ),
            ),
            offset,
            limit,
            1,
            False,
        )

    def assignVisualMedia(
        self, sceneId: str, role: VisualClipRole, contentHash: str | None
    ) -> Timeline:
        del role, contentHash
        timestamp = datetime.now(UTC)
        return Timeline(
            "timeline-1",
            (TimelineScene(sceneId, 1, 0, 2_000),),
            timestamp,
            timestamp,
        )

    def assignVisualMediaBatch(
        self, assignments: tuple[VisualMediaAssignment, ...]
    ) -> Timeline:
        timestamp = datetime.now(UTC)
        return Timeline(
            "timeline-1",
            tuple(
                TimelineScene(assignment.sceneId, index, index * 2_000, index * 2_000)
                for index, assignment in enumerate(assignments, start=1)
            ),
            timestamp,
            timestamp,
        )


def createClient(tmp_path: Path) -> tuple[TestClient, ProjectService]:
    app = createApp()
    projectService = ProjectService(SQLiteProjectRepository(tmp_path / "app-data"))
    app.dependency_overrides[getProjectService] = lambda: projectService
    return TestClient(app), projectService


def testGeneratesSavesAndLoadsTimeline(tmp_path: Path) -> None:
    client, projectService = createClient(tmp_path)
    projectsDirectory = tmp_path / "projects"
    projectsDirectory.mkdir()
    client.post(
        "/api/projects",
        json={"name": "Demo", "parentDirectory": str(projectsDirectory)},
    )
    scriptPath = tmp_path / "script.txt"
    scriptPath.write_text("First scene.\n\nSecond scene.", encoding="utf-8")
    client.post("/api/scripts/import", json={"path": str(scriptPath)})

    generated = client.post("/api/timeline/generate")
    payload = generated.json()["data"]
    payload["scenes"][0]["endMilliseconds"] = 3_000
    payload["scenes"][0]["subtitleClips"][0]["endMilliseconds"] = 3_000
    payload["scenes"][1]["startMilliseconds"] = 3_000
    payload["scenes"][1]["endMilliseconds"] = 5_000
    payload["scenes"][1]["subtitleClips"][0]["startMilliseconds"] = 3_000
    payload["scenes"][1]["subtitleClips"][0]["endMilliseconds"] = 5_000

    saved = client.put("/api/timeline", json=payload)
    loaded = client.get("/api/timeline")

    assert generated.status_code == 201
    assert saved.status_code == 200
    assert loaded.json()["data"]["durationMilliseconds"] == 5_000
    project = projectService.getCurrentProject()
    assert project is not None
    assert (project.path / "timeline" / "timeline.json").is_file()


def testTimelineApiRequiresScenes(tmp_path: Path) -> None:
    client, _projectService = createClient(tmp_path)
    projectsDirectory = tmp_path / "projects"
    projectsDirectory.mkdir()
    client.post(
        "/api/projects",
        json={"name": "Demo", "parentDirectory": str(projectsDirectory)},
    )

    response = client.post("/api/timeline/generate")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SCENES_NOT_FOUND"


def testTimelineApiListsCachedMediaAssets() -> None:
    app = createApp()
    app.dependency_overrides[getTimelineMediaService] = FakeTimelineMediaService
    client = TestClient(app)

    response = client.get("/api/timeline/media-assets")

    assert response.status_code == 200
    assert response.json()["data"]["assets"][0]["mediaType"] == "image"
    assert response.json()["data"]["assets"][0]["providerIds"] == ["pexels"]
    assert response.json()["data"]["totalEntries"] == 1
    assert response.json()["data"]["hasMore"] is False

    pageResponse = client.get("/api/timeline/media-assets", params={"limit": 1})

    assert pageResponse.status_code == 200
    assert pageResponse.json()["data"]["limit"] == 1

    assignmentResponse = client.put(
        "/api/timeline/scenes/scene-1/media",
        json={"contentHash": "a" * 64},
    )

    assert assignmentResponse.status_code == 200
    assert assignmentResponse.json()["data"]["scenes"][0]["sceneId"] == "scene-1"

    batchResponse = client.put(
        "/api/timeline/media-assignments",
        json={
            "assignments": [
                {"sceneId": "scene-1", "contentHash": "a" * 64},
                {"sceneId": "scene-2", "contentHash": "a" * 64},
            ]
        },
    )

    assert batchResponse.status_code == 200
    assert len(batchResponse.json()["data"]["scenes"]) == 2
