from dataclasses import dataclass
from typing import Any, Literal

BackfillStatus = Literal["queued", "running", "completed", "cancelled", "failed"]


@dataclass(frozen=True)
class MediaFingerprintBackfillJob:
    jobId: str
    projectId: str
    status: BackfillStatus
    totalMedia: int = 0
    processedMedia: int = 0
    updatedMedia: int = 0
    skippedMedia: int = 0
    failedContentHashes: tuple[str, ...] = ()
    errorMessage: str | None = None

    def toDictionary(self) -> dict[str, Any]:
        percent = (
            round(self.processedMedia * 100 / self.totalMedia)
            if self.totalMedia
            else (100 if self.status == "completed" else 0)
        )
        return {
            "jobId": self.jobId,
            "projectId": self.projectId,
            "status": self.status,
            "totalMedia": self.totalMedia,
            "processedMedia": self.processedMedia,
            "progressPercent": percent,
            "updatedMedia": self.updatedMedia,
            "skippedMedia": self.skippedMedia,
            "failedCount": len(self.failedContentHashes),
            "failedContentHashes": list(self.failedContentHashes),
            "errorMessage": self.errorMessage,
        }
