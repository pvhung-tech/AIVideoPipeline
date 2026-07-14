import logging
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.media.metadata_backfill_models import MediaMetadataBackfillJob
from app.project.errors import ProjectError
from app.project.project_model import Project
from app.services.media_cache_service import MediaCacheService
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)
ACTIVE_STATUSES = ("queued", "running")


class MediaMetadataBackfillService:
    def __init__(
        self, mediaCacheService: MediaCacheService, projectService: ProjectService
    ) -> None:
        self.mediaCacheService = mediaCacheService
        self.projectService = projectService
        self._lock = threading.RLock()
        self._jobs: dict[str, MediaMetadataBackfillJob] = {}
        self._cancellations: dict[str, threading.Event] = {}

    def startForActiveProject(self) -> MediaMetadataBackfillJob:
        project = self.projectService.getCurrentProject()
        if project is None:
            raise ProjectError("NO_ACTIVE_PROJECT", "No project is currently open.")
        return self.startForProject(project)

    def startForProject(self, project: Project) -> MediaMetadataBackfillJob:
        with self._lock:
            current = self._jobs.get(project.id)
            if current and current.status in ACTIVE_STATUSES:
                return current
            job = MediaMetadataBackfillJob(uuid4().hex, project.id, "queued")
            cancellation = threading.Event()
            self._jobs[project.id] = job
            self._cancellations[project.id] = cancellation
            threading.Thread(
                target=self._run,
                args=(project.id, project.path / "cache", cancellation),
                name=f"metadata-backfill-{project.id}",
                daemon=True,
            ).start()
            return job

    def getActiveProjectJob(self) -> MediaMetadataBackfillJob | None:
        project = self.projectService.getCurrentProject()
        if project is None:
            raise ProjectError("NO_ACTIVE_PROJECT", "No project is currently open.")
        with self._lock:
            return self._jobs.get(project.id)

    def cancelActiveProjectJob(self) -> MediaMetadataBackfillJob:
        job = self.getActiveProjectJob()
        if job is None:
            raise ProjectError("BACKFILL_NOT_FOUND", "No metadata backfill job exists.")
        with self._lock:
            cancellation = self._cancellations.get(job.projectId)
            if cancellation and job.status in ACTIVE_STATUSES:
                cancellation.set()
            return self._jobs[job.projectId]

    def _run(
        self, projectId: str, cacheRoot: Path, cancellation: threading.Event
    ) -> None:
        self._update(projectId, status="running")
        try:
            result = self.mediaCacheService.backfillVideoMetadata(
                cacheRoot=cacheRoot,
                progress=lambda *values: self._progress(projectId, *values),
                isCancelled=cancellation.is_set,
            )
            status = "cancelled" if cancellation.is_set() else "completed"
            self._update(
                projectId,
                status=status,
                updatedVideos=result.updatedVideos,
                skippedVideos=result.skippedVideos,
                failedContentHashes=result.failedContentHashes,
            )
        except Exception as error:
            logger.exception("Video metadata backfill job failed for %s", projectId)
            self._update(projectId, status="failed", errorMessage=str(error))

    def _progress(
        self,
        projectId: str,
        processed: int,
        total: int,
        updated: int,
        skipped: int,
        failed: tuple[str, ...],
    ) -> None:
        self._update(
            projectId,
            totalVideos=total,
            processedVideos=processed,
            updatedVideos=updated,
            skippedVideos=skipped,
            failedContentHashes=failed,
        )

    def _update(self, projectId: str, **changes: Any) -> None:
        with self._lock:
            self._jobs[projectId] = replace(self._jobs[projectId], **changes)
