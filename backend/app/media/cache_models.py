from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MediaCacheDiagnostics:
    providerId: str
    duplicate: bool
    sizeBytes: int
    sourceTransferSeconds: float
    sourceHashSeconds: float
    sourceFileWriteSeconds: float
    duplicateCheckSeconds: float
    fingerprintSeconds: float
    metadataSeconds: float
    manifestSeconds: float
    totalSeconds: float
    fingerprintDeferred: bool = False

    def toDictionary(self) -> dict[str, Any]:
        return {
            "providerId": self.providerId,
            "duplicate": self.duplicate,
            "sizeBytes": self.sizeBytes,
            "sourceTransferSeconds": self.sourceTransferSeconds,
            "sourceHashSeconds": self.sourceHashSeconds,
            "sourceFileWriteSeconds": self.sourceFileWriteSeconds,
            "duplicateCheckSeconds": self.duplicateCheckSeconds,
            "fingerprintSeconds": self.fingerprintSeconds,
            "metadataSeconds": self.metadataSeconds,
            "manifestSeconds": self.manifestSeconds,
            "totalSeconds": self.totalSeconds,
            "fingerprintDeferred": self.fingerprintDeferred,
        }


@dataclass(frozen=True)
class CachedMedia:
    mediaId: str
    providerId: str
    contentHash: str
    path: Path
    sizeBytes: int
    duplicate: bool
    diagnostics: MediaCacheDiagnostics | None = None

    def toDictionary(self) -> dict[str, Any]:
        return {
            "mediaId": self.mediaId,
            "providerId": self.providerId,
            "contentHash": self.contentHash,
            "path": str(self.path),
            "uri": self.path.as_uri(),
            "sizeBytes": self.sizeBytes,
            "duplicate": self.duplicate,
            "diagnostics": (
                self.diagnostics.toDictionary() if self.diagnostics else None
            ),
        }
