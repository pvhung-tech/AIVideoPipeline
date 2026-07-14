from dataclasses import dataclass
from typing import Any

from app.timeline.models import TimelineMediaType


@dataclass(frozen=True)
class TimelineMediaAsset:
    contentHash: str
    mediaType: TimelineMediaType
    fileName: str
    uri: str
    sizeBytes: int
    providerIds: tuple[str, ...]
    durationMilliseconds: int | None = None

    def toDictionary(self) -> dict[str, Any]:
        return {
            "contentHash": self.contentHash,
            "mediaType": self.mediaType.value,
            "fileName": self.fileName,
            "uri": self.uri,
            "sizeBytes": self.sizeBytes,
            "providerIds": list(self.providerIds),
            "durationMilliseconds": self.durationMilliseconds,
        }


@dataclass(frozen=True)
class TimelineMediaAssetPage:
    assets: tuple[TimelineMediaAsset, ...]
    offset: int
    limit: int | None
    totalEntries: int
    hasMore: bool

    def toDictionary(self) -> dict[str, Any]:
        return {
            "assets": [asset.toDictionary() for asset in self.assets],
            "offset": self.offset,
            "limit": self.limit,
            "totalEntries": self.totalEntries,
            "hasMore": self.hasMore,
        }
