import time
from datetime import UTC, datetime
from pathlib import Path

from app.media.cache_manifest import MediaCacheEntry, MediaCacheManifest
from app.media.media_metadata_service import MediaMetadataService
from app.media.metadata_backfill_models import MediaMetadataBackfillJob
from app.project.project_model import Project
from app.services.media_cache_service import MediaCacheService
from app.services.media_metadata_backfill_service import MediaMetadataBackfillService
from app.services.project_service import ProjectService


class FakeProjectRepository:
    def createProject(self, project: Project) -> Project:
        return project

    def saveProject(self, project: Project) -> Project:
        return project

    def openProject(self, projectPath: Path) -> Project:
        raise NotImplementedError

    def listRecentProjects(self, limit: int) -> list[Project]:
        return []


class SlowMetadataService(MediaMetadataService):
    def __init__(self) -> None:
        pass

    def probeDurationMilliseconds(self, path: Path) -> int:
        time.sleep(0.04)
        return 10_000


def testBackfillJobReportsProgressAndSupportsCancellation(tmp_path: Path) -> None:
    projectPath = tmp_path / "project"
    cacheRoot = projectPath / "cache"
    timestamp = datetime.now(UTC)
    entries = []
    for index in range(5):
        path = cacheRoot / "aa" / f"{index}.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"video")
        entries.append(
            MediaCacheEntry(
                str(index) * 64,
                f"aa/{index}.mp4",
                5,
                timestamp,
                timestamp,
                (),
            )
        )
    projectService = ProjectService(FakeProjectRepository())
    project = Project("project-id", "Project", projectPath, timestamp, timestamp)
    projectService.activeProject = project
    cacheService = MediaCacheService(
        projectService, (), 1_000, 5, metadataService=SlowMetadataService()
    )
    cacheService.repository.save(cacheRoot, MediaCacheManifest(tuple(entries)))
    service = MediaMetadataBackfillService(cacheService, projectService)

    first = service.startForActiveProject()
    assert service.startForActiveProject().jobId == first.jobId
    _waitForProgress(service)
    service.cancelActiveProjectJob()
    job = _waitForTerminal(service)

    assert job.status == "cancelled"
    assert 1 <= job.processedVideos < 5
    assert len(cacheService.getManifest().entries) == 5


def _waitForProgress(service: MediaMetadataBackfillService) -> None:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        job = service.getActiveProjectJob()
        if job and job.processedVideos:
            return
        time.sleep(0.01)
    raise AssertionError("Backfill did not report progress")


def _waitForTerminal(
    service: MediaMetadataBackfillService,
) -> MediaMetadataBackfillJob:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        job = service.getActiveProjectJob()
        if job and job.status not in ("queued", "running"):
            return job
        time.sleep(0.01)
    raise AssertionError("Backfill did not stop")
