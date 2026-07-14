import logging
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.media.fingerprint_backfill_models import MediaFingerprintBackfillJob
from app.project.errors import ProjectError
from app.project.project_model import Project
from app.services.media_cache_service import MediaCacheService
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)
ACTIVE_STATUSES = ("queued", "running")


class MediaFingerprintBackfillService:
    def __init__(
        self, mediaCacheService: MediaCacheService, projectService: ProjectService
    ) -> None:
        self.mediaCacheService = mediaCacheService
        self.projectService = projectService
        self._lock = threading.RLock()
        self._jobs: dict[str, MediaFingerprintBackfillJob] = {}
        self._cancellations: dict[str, threading.Event] = {}

    def startForActiveProject(self) -> MediaFingerprintBackfillJob:
        project = self.projectService.getCurrentProject()
        if project is None:
            raise ProjectError("NO_ACTIVE_PROJECT", "No project is currently open.")
        return self.startForProject(project)

    def startForProject(self, project: Project) -> MediaFingerprintBackfillJob:
        with self._lock:
            current = self._jobs.get(project.id)
            if current and current.status in ACTIVE_STATUSES:
                return current
            job = MediaFingerprintBackfillJob(uuid4().hex, project.id, "queued")
            cancellation = threading.Event()
            self._jobs[project.id] = job
            self._cancellations[project.id] = cancellation
            threading.Thread(
                target=self._run,
                args=(project.id, project.path / "cache", cancellation),
                name=f"fingerprint-backfill-{project.id}",
                daemon=True,
            ).start()
            return job

    def getActiveProjectJob(self) -> MediaFingerprintBackfillJob | None:
        project = self.projectService.getCurrentProject()
        if project is None:
            raise ProjectError("NO_ACTIVE_PROJECT", "No project is currently open.")
        with self._lock:
            return self._jobs.get(project.id)

    def cancelActiveProjectJob(self) -> MediaFingerprintBackfillJob:
        job = self.getActiveProjectJob()
        if job is None:
            raise ProjectError(
                "FINGERPRINT_BACKFILL_NOT_FOUND",
                "No fingerprint backfill job exists.",
            )
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
            result = self.mediaCacheService.backfillMissingFingerprints(
                cacheRoot=cacheRoot,
                progress=lambda *values: self._progress(projectId, *values),
                isCancelled=cancellation.is_set,
            )
            status = "cancelled" if cancellation.is_set() else "completed"
            self._update(
                projectId,
                status=status,
                updatedMedia=result.updatedMedia,
                skippedMedia=result.skippedMedia,
                failedContentHashes=result.failedContentHashes,
            )
        except Exception as error:
            logger.exception("Media fingerprint backfill job failed for %s", projectId)
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
            totalMedia=total,
            processedMedia=processed,
            updatedMedia=updated,
            skippedMedia=skipped,
            failedContentHashes=failed,
        )

    def _update(self, projectId: str, **changes: Any) -> None:
        with self._lock:
            self._jobs[projectId] = replace(self._jobs[projectId], **changes)
