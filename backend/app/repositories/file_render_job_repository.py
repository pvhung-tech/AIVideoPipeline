import json
import logging
import os
from pathlib import Path
from typing import Any

from app.render.errors import RenderError
from app.render.models import (
    RenderDiagnostics,
    RenderExportSettings,
    RenderJobSnapshot,
    RenderOutputPreview,
    RenderReview,
)

logger = logging.getLogger(__name__)
RENDER_JOB_SCHEMA_VERSION = 1


class FileRenderJobRepository:
    def saveJobs(self, projectPath: Path, jobs: tuple[RenderJobSnapshot, ...]) -> None:
        queuePath = self._queuePath(projectPath)
        temporaryPath = queuePath.with_name(f".{queuePath.name}.tmp")
        document = {
            "schemaVersion": RENDER_JOB_SCHEMA_VERSION,
            "jobs": [job.toDictionary() for job in jobs],
        }
        try:
            queuePath.parent.mkdir(parents=True, exist_ok=True)
            temporaryPath.write_text(
                json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            os.replace(temporaryPath, queuePath)
        except OSError as error:
            logger.exception("Failed to save render jobs in project %s", projectPath)
            raise RenderError(
                "RENDER_QUEUE_SAVE_FAILED", "Render queue could not be saved."
            ) from error

    def loadJobs(self, projectPath: Path) -> tuple[RenderJobSnapshot, ...]:
        queuePath = self._queuePath(projectPath)
        if not queuePath.is_file():
            return ()
        try:
            data: Any = json.loads(queuePath.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Render queue document must be an object.")
            if data.get("schemaVersion") != RENDER_JOB_SCHEMA_VERSION:
                raise ValueError("Unsupported render queue schema version.")
            jobs = data.get("jobs")
            if not isinstance(jobs, list):
                raise ValueError("Render queue jobs must be a list.")
            return tuple(self._jobFromDictionary(item) for item in jobs)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RenderError(
                "INVALID_RENDER_QUEUE_FILE", "The saved render queue is invalid."
            ) from error
        except OSError as error:
            logger.exception("Failed to load render jobs from project %s", projectPath)
            raise RenderError(
                "RENDER_QUEUE_READ_FAILED", "Render queue could not be read."
            ) from error

    def _jobFromDictionary(self, data: Any) -> RenderJobSnapshot:
        if not isinstance(data, dict):
            raise ValueError("Render job must be an object.")
        output = data.get("outputPath")
        return RenderJobSnapshot(
            self._requiredString(data, "jobId"),
            self._requiredString(data, "projectId"),
            self._requiredString(data, "fileName"),
            self._requiredString(data, "status"),
            float(data.get("progressPercent", 0.0)),
            int(data.get("processedMilliseconds", 0)),
            int(data.get("durationMilliseconds", 0)),
            Path(output) if isinstance(output, str) and output else None,
            self._optionalInt(data.get("sizeBytes")),
            self._optionalString(data.get("errorCode")),
            self._optionalString(data.get("errorMessage")),
            self._optionalString(data.get("createdAt")),
            self._optionalString(data.get("updatedAt")),
            self._exportSettings(data),
            self._optionalString(data.get("outputNameTemplate")),
            RenderDiagnostics.fromDictionary(data.get("diagnostics")),
            RenderOutputPreview.fromDictionary(data.get("preview")),
            RenderReview.fromDictionary(data.get("review")),
        )

    def _exportSettings(self, data: dict[str, Any]) -> RenderExportSettings | None:
        if "exportSettings" not in data:
            return RenderExportSettings()
        value = data.get("exportSettings")
        return RenderExportSettings.fromDictionary(value) if value is not None else None

    def _requiredString(self, data: dict[str, Any], key: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Render job {key} must be a non-empty string.")
        return value

    def _optionalString(self, value: Any) -> str | None:
        return value if isinstance(value, str) and value.strip() else None

    def _optionalInt(self, value: Any) -> int | None:
        return int(value) if isinstance(value, int) else None

    def _queuePath(self, projectPath: Path) -> Path:
        return projectPath / "render" / "jobs.json"
