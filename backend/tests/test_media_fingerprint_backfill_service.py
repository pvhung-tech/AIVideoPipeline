import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from app.media.cache_manifest import MediaFingerprintBackfillResult
from app.media.fingerprint_backfill_models import MediaFingerprintBackfillJob
from app.project.project_model import Project
from app.services.media_fingerprint_backfill_service import (
    MediaFingerprintBackfillService,
)
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


class SlowFingerprintCacheService:
    def backfillMissingFingerprints(
        self,
        cacheRoot: Path | None = None,
        progress: Callable[[int, int, int, int, tuple[str, ...]], None] | None = None,
        isCancelled: Callable[[], bool] | None = None,
    ) -> MediaFingerprintBackfillResult:
        del cacheRoot
        updated = 0
        skipped = 0
        failed: tuple[str, ...] = ()
        if progress:
            progress(0, 5, 0, 0, ())
        for index in range(5):
            if isCancelled and isCancelled():
                break
            time.sleep(0.04)
            updated += 1
            if progress:
                progress(index + 1, 5, updated, skipped, failed)
        return MediaFingerprintBackfillResult(5, updated, skipped, failed)


def testFingerprintBackfillJobReportsProgressAndSupportsCancellation(
    tmp_path: Path,
) -> None:
    timestamp = datetime.now(UTC)
    projectService = ProjectService(FakeProjectRepository())
    project = Project(
        "project-id", "Project", tmp_path / "project", timestamp, timestamp
    )
    projectService.activeProject = project
    service = MediaFingerprintBackfillService(
        cast(Any, SlowFingerprintCacheService()), projectService
    )

    first = service.startForActiveProject()
    assert service.startForActiveProject().jobId == first.jobId
    _waitForProgress(service)
    service.cancelActiveProjectJob()
    job = _waitForTerminal(service)

    assert job.status == "cancelled"
    assert 1 <= job.processedMedia < 5


def _waitForProgress(service: MediaFingerprintBackfillService) -> None:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        job = service.getActiveProjectJob()
        if job and job.processedMedia:
            return
        time.sleep(0.01)
    raise AssertionError("Fingerprint backfill did not report progress")


def _waitForTerminal(
    service: MediaFingerprintBackfillService,
) -> MediaFingerprintBackfillJob:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        job = service.getActiveProjectJob()
        if job and job.status not in ("queued", "running"):
            return job
        time.sleep(0.01)
    raise AssertionError("Fingerprint backfill did not stop")
