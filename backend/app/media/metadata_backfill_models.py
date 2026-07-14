from dataclasses import dataclass
from typing import Any, Literal

BackfillStatus = Literal["queued", "running", "completed", "cancelled", "failed"]


@dataclass(frozen=True)
class MediaMetadataBackfillJob:
    jobId: str
    projectId: str
    status: BackfillStatus
    totalVideos: int = 0
    processedVideos: int = 0
    updatedVideos: int = 0
    skippedVideos: int = 0
    failedContentHashes: tuple[str, ...] = ()
    errorMessage: str | None = None

    def toDictionary(self) -> dict[str, Any]:
        percent = (
            round(self.processedVideos * 100 / self.totalVideos)
            if self.totalVideos
            else (100 if self.status == "completed" else 0)
        )
        return {
            "jobId": self.jobId,
            "projectId": self.projectId,
            "status": self.status,
            "totalVideos": self.totalVideos,
            "processedVideos": self.processedVideos,
            "progressPercent": percent,
            "updatedVideos": self.updatedVideos,
            "skippedVideos": self.skippedVideos,
            "failedCount": len(self.failedContentHashes),
            "failedContentHashes": list(self.failedContentHashes),
            "errorMessage": self.errorMessage,
        }
