from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.media.errors import MediaError


class MediaType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


@dataclass(frozen=True)
class MediaSearchQuery:
    text: str
    mediaTypes: tuple[MediaType, ...]
    limit: int
    offset: int

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise MediaError("INVALID_MEDIA_QUERY", "Media query cannot be empty.")
        if not self.mediaTypes or len(set(self.mediaTypes)) != len(self.mediaTypes):
            raise MediaError(
                "INVALID_MEDIA_TYPES", "Media types must be non-empty and unique."
            )
        if self.limit < 1 or self.limit > 100:
            raise MediaError(
                "INVALID_MEDIA_LIMIT", "Media result limit must be between 1 and 100."
            )
        if self.offset < 0:
            raise MediaError(
                "INVALID_MEDIA_OFFSET", "Media result offset cannot be negative."
            )


@dataclass(frozen=True)
class MediaSearchItem:
    id: str
    providerId: str
    mediaType: MediaType
    title: str
    sourceUri: str
    previewUri: str | None
    fileSizeBytes: int | None
    modifiedAt: datetime | None
    score: float
    license: str | None = None
    sourcePageUri: str | None = None
    creator: str | None = None
    creatorUri: str | None = None

    def toDictionary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "providerId": self.providerId,
            "mediaType": self.mediaType.value,
            "title": self.title,
            "sourceUri": self.sourceUri,
            "previewUri": self.previewUri,
            "fileSizeBytes": self.fileSizeBytes,
            "modifiedAt": self.modifiedAt.isoformat() if self.modifiedAt else None,
            "score": self.score,
            "license": self.license,
            "sourcePageUri": self.sourcePageUri,
            "creator": self.creator,
            "creatorUri": self.creatorUri,
        }


@dataclass(frozen=True)
class MediaProviderError:
    providerId: str
    code: str
    message: str

    def toDictionary(self) -> dict[str, str]:
        return {
            "providerId": self.providerId,
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True)
class MediaDeduplicationStatistics:
    totalCandidates: int
    retainedItems: int
    fingerprintedCandidates: int
    canonicalDuplicates: int
    perceptualImageDuplicates: int
    perceptualVideoDuplicates: int
    imageHammingThreshold: int
    videoAverageHammingThreshold: int

    def toDictionary(self) -> dict[str, int]:
        return {
            "totalCandidates": self.totalCandidates,
            "retainedItems": self.retainedItems,
            "fingerprintedCandidates": self.fingerprintedCandidates,
            "canonicalDuplicates": self.canonicalDuplicates,
            "perceptualImageDuplicates": self.perceptualImageDuplicates,
            "perceptualVideoDuplicates": self.perceptualVideoDuplicates,
            "imageHammingThreshold": self.imageHammingThreshold,
            "videoAverageHammingThreshold": self.videoAverageHammingThreshold,
        }


@dataclass(frozen=True)
class MediaSearchPage:
    providerId: str
    query: str
    totalResults: int
    offset: int
    limit: int
    truncated: bool
    items: tuple[MediaSearchItem, ...]
    providerErrors: tuple[MediaProviderError, ...] = ()
    deduplication: MediaDeduplicationStatistics | None = None

    def toDictionary(self) -> dict[str, Any]:
        return {
            "providerId": self.providerId,
            "query": self.query,
            "totalResults": self.totalResults,
            "offset": self.offset,
            "limit": self.limit,
            "truncated": self.truncated,
            "items": [item.toDictionary() for item in self.items],
            "providerErrors": [error.toDictionary() for error in self.providerErrors],
            "deduplication": (
                self.deduplication.toDictionary() if self.deduplication else None
            ),
        }
