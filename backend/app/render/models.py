from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.render.errors import RenderError

ENCODER_PRESETS = (
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
)
RENDER_PROFILE_IDS = ("fast_preview", "draft", "standard", "high_quality", "archive")
RENDER_REVIEW_STATUSES = ("accepted", "rejected")


@dataclass(frozen=True)
class RenderExportSettings:
    width: int = 1920
    height: int = 1080
    frameRate: int = 30
    crf: int = 18
    encoderPreset: str = "medium"
    audioBitrateKbps: int = 192
    profileId: str = "standard"

    def __post_init__(self) -> None:
        if not 320 <= self.width <= 7680:
            raise RenderError("INVALID_RENDER_SETTINGS", "Render width is invalid.")
        if not 180 <= self.height <= 4320:
            raise RenderError("INVALID_RENDER_SETTINGS", "Render height is invalid.")
        if not 1 <= self.frameRate <= 120:
            raise RenderError(
                "INVALID_RENDER_SETTINGS", "Render frame rate is invalid."
            )
        if not 0 <= self.crf <= 51:
            raise RenderError("INVALID_RENDER_SETTINGS", "Render CRF is invalid.")
        if self.encoderPreset not in ENCODER_PRESETS:
            raise RenderError(
                "INVALID_RENDER_SETTINGS", "Render encoder preset is invalid."
            )
        if not 64 <= self.audioBitrateKbps <= 512:
            raise RenderError(
                "INVALID_RENDER_SETTINGS", "Render audio bitrate is invalid."
            )
        if self.profileId not in (*RENDER_PROFILE_IDS, "custom"):
            raise RenderError("INVALID_RENDER_SETTINGS", "Render profile is invalid.")

    def toDictionary(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "frameRate": self.frameRate,
            "crf": self.crf,
            "encoderPreset": self.encoderPreset,
            "audioBitrateKbps": self.audioBitrateKbps,
            "profileId": self.profileId,
        }

    @classmethod
    def fromDictionary(cls, data: Any) -> "RenderExportSettings":
        if not isinstance(data, dict):
            return cls()
        return cls(
            int(data.get("width", 1920)),
            int(data.get("height", 1080)),
            int(data.get("frameRate", 30)),
            int(data.get("crf", 18)),
            str(data.get("encoderPreset", "medium")),
            int(data.get("audioBitrateKbps", 192)),
            str(data.get("profileId", "standard")),
        )


@dataclass(frozen=True)
class RenderProfile:
    profileId: str
    name: str
    settings: RenderExportSettings

    def toDictionary(self) -> dict[str, Any]:
        return {
            "profileId": self.profileId,
            "name": self.name,
            "settings": self.settings.toDictionary(),
        }


RENDER_PROFILES = {
    "fast_preview": RenderProfile(
        "fast_preview",
        "Fast Preview",
        RenderExportSettings(640, 360, 15, 32, "veryfast", 96, "fast_preview"),
    ),
    "draft": RenderProfile(
        "draft",
        "Draft",
        RenderExportSettings(854, 480, 24, 28, "veryfast", 128, "draft"),
    ),
    "standard": RenderProfile(
        "standard",
        "Standard",
        RenderExportSettings(1920, 1080, 30, 18, "medium", 192, "standard"),
    ),
    "high_quality": RenderProfile(
        "high_quality",
        "High Quality",
        RenderExportSettings(1920, 1080, 30, 16, "slow", 256, "high_quality"),
    ),
    "archive": RenderProfile(
        "archive",
        "Archive",
        RenderExportSettings(3840, 2160, 30, 14, "slower", 320, "archive"),
    ),
}


def renderProfileSettings(profileId: str) -> RenderExportSettings:
    profile = RENDER_PROFILES.get(profileId)
    if profile is None:
        raise RenderError("INVALID_RENDER_SETTINGS", "Render profile is invalid.")
    return profile.settings


@dataclass(frozen=True)
class FFmpegCommand:
    arguments: tuple[str, ...]
    outputPath: Path


@dataclass(frozen=True)
class RenderResult:
    outputPath: Path
    durationMilliseconds: int
    sizeBytes: int

    def toDictionary(self) -> dict[str, Any]:
        return {
            "outputPath": str(self.outputPath),
            "durationMilliseconds": self.durationMilliseconds,
            "sizeBytes": self.sizeBytes,
        }


@dataclass(frozen=True)
class RenderPreflightCheck:
    code: str
    message: str
    status: str

    def toDictionary(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "status": self.status,
        }


@dataclass(frozen=True)
class RenderPreflightGroup:
    group: str
    status: str
    checks: tuple[RenderPreflightCheck, ...]

    def toDictionary(self) -> dict[str, Any]:
        return {
            "group": self.group,
            "status": self.status,
            "checks": [check.toDictionary() for check in self.checks],
        }


@dataclass(frozen=True)
class RenderPreflightReport:
    ready: bool
    groups: tuple[RenderPreflightGroup, ...]
    outputFileName: str | None = None
    durationMilliseconds: int | None = None

    def toDictionary(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "groups": [group.toDictionary() for group in self.groups],
            "outputFileName": self.outputFileName,
            "durationMilliseconds": self.durationMilliseconds,
        }


@dataclass(frozen=True)
class RenderDiagnostics:
    commandSummary: dict[str, Any]
    settingsSnapshot: dict[str, Any]
    metrics: dict[str, Any]
    stderrTail: str | None = None

    def toDictionary(self) -> dict[str, Any]:
        return {
            "commandSummary": self.commandSummary,
            "settingsSnapshot": self.settingsSnapshot,
            "metrics": self.metrics,
            "stderrTail": self.stderrTail,
        }

    @classmethod
    def fromDictionary(cls, data: Any) -> "RenderDiagnostics | None":
        if not isinstance(data, dict):
            return None
        commandSummary = data.get("commandSummary")
        settingsSnapshot = data.get("settingsSnapshot")
        metrics = data.get("metrics")
        stderrTail = data.get("stderrTail")
        if not isinstance(commandSummary, dict):
            commandSummary = {}
        if not isinstance(settingsSnapshot, dict):
            settingsSnapshot = {}
        if not isinstance(metrics, dict):
            metrics = {}
        return cls(
            dict(commandSummary),
            dict(settingsSnapshot),
            dict(metrics),
            stderrTail if isinstance(stderrTail, str) and stderrTail else None,
        )


@dataclass(frozen=True)
class RenderOutputPreview:
    thumbnailPath: Path | None
    thumbnailUri: str | None
    durationMilliseconds: int
    sizeBytes: int
    width: int
    height: int
    frameRate: int
    generatedAt: str
    status: str = "available"
    errorMessage: str | None = None

    def toDictionary(self) -> dict[str, Any]:
        return {
            "thumbnailPath": str(self.thumbnailPath) if self.thumbnailPath else None,
            "thumbnailUri": self.thumbnailUri,
            "durationMilliseconds": self.durationMilliseconds,
            "sizeBytes": self.sizeBytes,
            "width": self.width,
            "height": self.height,
            "frameRate": self.frameRate,
            "generatedAt": self.generatedAt,
            "status": self.status,
            "errorMessage": self.errorMessage,
        }

    @classmethod
    def fromDictionary(cls, data: Any) -> "RenderOutputPreview | None":
        if not isinstance(data, dict):
            return None
        thumbnailPath = data.get("thumbnailPath")
        thumbnailUri = data.get("thumbnailUri")
        errorMessage = data.get("errorMessage")
        try:
            return cls(
                (
                    Path(thumbnailPath)
                    if isinstance(thumbnailPath, str) and thumbnailPath
                    else None
                ),
                (
                    thumbnailUri
                    if isinstance(thumbnailUri, str) and thumbnailUri
                    else None
                ),
                int(data["durationMilliseconds"]),
                int(data["sizeBytes"]),
                int(data["width"]),
                int(data["height"]),
                int(data["frameRate"]),
                str(data["generatedAt"]),
                str(data.get("status", "available")),
                (
                    errorMessage
                    if isinstance(errorMessage, str) and errorMessage
                    else None
                ),
            )
        except (KeyError, TypeError, ValueError):
            return None


@dataclass(frozen=True)
class RenderReview:
    status: str
    note: str | None
    reviewedAt: str

    def __post_init__(self) -> None:
        if self.status not in RENDER_REVIEW_STATUSES:
            raise RenderError(
                "INVALID_RENDER_REVIEW", "Render review status is invalid."
            )

    def toDictionary(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "note": self.note,
            "reviewedAt": self.reviewedAt,
        }

    @classmethod
    def fromDictionary(cls, data: Any) -> "RenderReview | None":
        if not isinstance(data, dict):
            return None
        status = data.get("status")
        reviewedAt = data.get("reviewedAt")
        note = data.get("note")
        if not isinstance(status, str) or not isinstance(reviewedAt, str):
            return None
        try:
            return cls(
                status,
                note if isinstance(note, str) and note.strip() else None,
                reviewedAt,
            )
        except RenderError:
            return None


@dataclass(frozen=True)
class ProcessResult:
    returnCode: int
    standardError: str


@dataclass(frozen=True)
class RenderDraft:
    projectId: str
    projectPath: Path
    outputPath: Path
    durationMilliseconds: int
    exportSettings: RenderExportSettings


@dataclass(frozen=True)
class RenderPlan:
    projectId: str
    projectPath: Path
    command: FFmpegCommand
    outputPath: Path
    temporaryPath: Path
    durationMilliseconds: int
    exportSettings: RenderExportSettings
    temporaryFiles: tuple[Path, ...] = ()


@dataclass(frozen=True)
class RenderJobSnapshot:
    jobId: str
    projectId: str
    fileName: str
    status: str
    progressPercent: float
    processedMilliseconds: int
    durationMilliseconds: int
    outputPath: Path | None
    sizeBytes: int | None
    errorCode: str | None
    errorMessage: str | None
    createdAt: str | None = None
    updatedAt: str | None = None
    exportSettings: RenderExportSettings | None = None
    outputNameTemplate: str | None = None
    diagnostics: RenderDiagnostics | None = None
    preview: RenderOutputPreview | None = None
    review: RenderReview | None = None

    def toDictionary(self) -> dict[str, Any]:
        return {
            "jobId": self.jobId,
            "projectId": self.projectId,
            "fileName": self.fileName,
            "status": self.status,
            "progressPercent": self.progressPercent,
            "processedMilliseconds": self.processedMilliseconds,
            "durationMilliseconds": self.durationMilliseconds,
            "outputPath": str(self.outputPath) if self.outputPath else None,
            "sizeBytes": self.sizeBytes,
            "errorCode": self.errorCode,
            "errorMessage": self.errorMessage,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
            "exportSettings": (
                self.exportSettings.toDictionary() if self.exportSettings else None
            ),
            "outputNameTemplate": self.outputNameTemplate,
            "diagnostics": (
                self.diagnostics.toDictionary() if self.diagnostics else None
            ),
            "preview": self.preview.toDictionary() if self.preview else None,
            "review": self.review.toDictionary() if self.review else None,
        }


@dataclass(frozen=True)
class RenderJobQueueSnapshot:
    jobs: tuple[RenderJobSnapshot, ...]

    def toDictionary(self) -> dict[str, Any]:
        return {"jobs": [job.toDictionary() for job in self.jobs]}
