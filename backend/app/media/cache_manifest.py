from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.media.errors import MediaError

CACHE_MANIFEST_VERSION = 1


@dataclass(frozen=True)
class MediaCacheSource:
    providerId: str
    mediaId: str
    sourceUri: str

    def toDictionary(self) -> dict[str, str]:
        return {
            "providerId": self.providerId,
            "mediaId": self.mediaId,
            "sourceUri": self.sourceUri,
        }

    @classmethod
    def fromDictionary(cls, data: Any) -> "MediaCacheSource":
        if not isinstance(data, dict):
            raise _invalidManifest()
        try:
            return cls(
                providerId=str(data["providerId"]),
                mediaId=str(data["mediaId"]),
                sourceUri=str(data["sourceUri"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise _invalidManifest() from error


@dataclass(frozen=True)
class MediaCacheEntry:
    contentHash: str
    relativePath: str
    sizeBytes: int
    createdAt: datetime
    lastAccessedAt: datetime
    sources: tuple[MediaCacheSource, ...]
    perceptualHash: str | None = None
    videoFingerprint: str | None = None
    durationMilliseconds: int | None = None

    def toDictionary(self) -> dict[str, Any]:
        return {
            "contentHash": self.contentHash,
            "relativePath": self.relativePath,
            "sizeBytes": self.sizeBytes,
            "createdAt": self.createdAt.isoformat(),
            "lastAccessedAt": self.lastAccessedAt.isoformat(),
            "sources": [source.toDictionary() for source in self.sources],
            "perceptualHash": self.perceptualHash,
            "videoFingerprint": self.videoFingerprint,
            "durationMilliseconds": self.durationMilliseconds,
        }

    @classmethod
    def fromDictionary(cls, data: Any) -> "MediaCacheEntry":
        if not isinstance(data, dict):
            raise _invalidManifest()
        try:
            contentHash = str(data["contentHash"])
            relativePath = str(data["relativePath"])
            sizeBytes = int(data["sizeBytes"])
            createdAt = datetime.fromisoformat(str(data["createdAt"]))
            lastAccessedAt = datetime.fromisoformat(str(data["lastAccessedAt"]))
            sourcesData = data["sources"]
            if (
                len(contentHash) != 64
                or sizeBytes < 0
                or createdAt.tzinfo is None
                or lastAccessedAt.tzinfo is None
                or not isinstance(sourcesData, list)
            ):
                raise ValueError
            sources = tuple(
                MediaCacheSource.fromDictionary(source) for source in sourcesData
            )
            perceptualHash = _optionalString(data.get("perceptualHash"))
            videoFingerprint = _optionalString(data.get("videoFingerprint"))
            durationValue = data.get("durationMilliseconds")
            durationMilliseconds = (
                int(durationValue) if durationValue is not None else None
            )
            if durationMilliseconds is not None and durationMilliseconds <= 0:
                raise ValueError
            if perceptualHash is not None and not _validPerceptualHash(perceptualHash):
                raise ValueError
            if videoFingerprint is not None and not _validVideoFingerprint(
                videoFingerprint
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError) as error:
            raise _invalidManifest() from error
        return cls(
            contentHash,
            relativePath,
            sizeBytes,
            createdAt,
            lastAccessedAt,
            sources,
            perceptualHash,
            videoFingerprint,
            durationMilliseconds,
        )


@dataclass(frozen=True)
class MediaCacheManifest:
    entries: tuple[MediaCacheEntry, ...]
    schemaVersion: int = CACHE_MANIFEST_VERSION

    @property
    def totalSizeBytes(self) -> int:
        return sum(entry.sizeBytes for entry in self.entries)

    def toDictionary(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schemaVersion,
            "totalSizeBytes": self.totalSizeBytes,
            "entries": [entry.toDictionary() for entry in self.entries],
        }

    @classmethod
    def fromDictionary(cls, data: Any) -> "MediaCacheManifest":
        if not isinstance(data, dict) or data.get("schemaVersion") != 1:
            raise _invalidManifest()
        entriesData = data.get("entries")
        if not isinstance(entriesData, list):
            raise _invalidManifest()
        entries = tuple(MediaCacheEntry.fromDictionary(entry) for entry in entriesData)
        if len({entry.contentHash for entry in entries}) != len(entries):
            raise _invalidManifest()
        return cls(entries)


@dataclass(frozen=True)
class MediaCacheCleanupResult:
    dryRun: bool
    removedEntries: tuple[MediaCacheEntry, ...]
    remainingEntries: int
    remainingSizeBytes: int

    def toDictionary(self) -> dict[str, Any]:
        return {
            "dryRun": self.dryRun,
            "removedCount": len(self.removedEntries),
            "removedSizeBytes": sum(entry.sizeBytes for entry in self.removedEntries),
            "remainingEntries": self.remainingEntries,
            "remainingSizeBytes": self.remainingSizeBytes,
            "removedContentHashes": [
                entry.contentHash for entry in self.removedEntries
            ],
        }


@dataclass(frozen=True)
class OrphanCacheFile:
    relativePath: str
    sizeBytes: int

    def toDictionary(self) -> dict[str, Any]:
        return {"relativePath": self.relativePath, "sizeBytes": self.sizeBytes}


@dataclass(frozen=True)
class MediaCacheReconciliationResult:
    dryRun: bool
    orphanFiles: tuple[OrphanCacheFile, ...]
    missingEntries: tuple[MediaCacheEntry, ...]

    def toDictionary(self) -> dict[str, Any]:
        return {
            "dryRun": self.dryRun,
            "orphanCount": len(self.orphanFiles),
            "orphanSizeBytes": sum(file.sizeBytes for file in self.orphanFiles),
            "orphanFiles": [file.toDictionary() for file in self.orphanFiles],
            "missingEntryCount": len(self.missingEntries),
            "missingContentHashes": [
                entry.contentHash for entry in self.missingEntries
            ],
        }


@dataclass(frozen=True)
class MediaMetadataBackfillResult:
    scannedVideos: int
    updatedVideos: int
    skippedVideos: int
    failedContentHashes: tuple[str, ...]

    def toDictionary(self) -> dict[str, Any]:
        return {
            "scannedVideos": self.scannedVideos,
            "updatedVideos": self.updatedVideos,
            "skippedVideos": self.skippedVideos,
            "failedCount": len(self.failedContentHashes),
            "failedContentHashes": list(self.failedContentHashes),
        }


@dataclass(frozen=True)
class MediaFingerprintBackfillResult:
    scannedMedia: int
    updatedMedia: int
    skippedMedia: int
    failedContentHashes: tuple[str, ...]

    def toDictionary(self) -> dict[str, Any]:
        return {
            "scannedMedia": self.scannedMedia,
            "updatedMedia": self.updatedMedia,
            "skippedMedia": self.skippedMedia,
            "failedCount": len(self.failedContentHashes),
            "failedContentHashes": list(self.failedContentHashes),
        }


def _invalidManifest() -> MediaError:
    return MediaError(
        "INVALID_MEDIA_CACHE_MANIFEST", "Media cache manifest is invalid."
    )


def _optionalString(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError
    return value


def _validPerceptualHash(value: str) -> bool:
    prefix = "dhash64-v1:"
    digest = value.removeprefix(prefix)
    return value.startswith(prefix) and len(digest) == 16 and _isHex(digest)


def _validVideoFingerprint(value: str) -> bool:
    prefix = "dhash64-sequence-v1:"
    frames = value.removeprefix(prefix).split(",")
    return (
        value.startswith(prefix)
        and 1 <= len(frames) <= 12
        and all(len(frame) == 16 and _isHex(frame) for frame in frames)
    )


def _isHex(value: str) -> bool:
    return all(character in "0123456789abcdef" for character in value)
