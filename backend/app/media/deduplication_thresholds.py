import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.media.models import MediaType


@dataclass(frozen=True)
class MediaDeduplicationThresholds:
    defaultImage: int
    defaultVideo: int
    categories: dict[str, dict[MediaType, int]]

    def threshold(self, category: str | None, mediaType: MediaType) -> int:
        normalized = category.strip().casefold() if category else ""
        categoryThresholds = self.categories.get(normalized, {})
        fallback = (
            self.defaultImage if mediaType == MediaType.IMAGE else self.defaultVideo
        )
        return categoryThresholds.get(mediaType, fallback)


def loadMediaDeduplicationThresholds(path: Path) -> MediaDeduplicationThresholds:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or data.get("schemaVersion") != 1:
            raise ValueError
        defaults = _thresholdPair(data.get("default"))
        categoryData = data.get("categories")
        if not isinstance(categoryData, dict):
            raise ValueError
        categories = {
            _category(name): _thresholdPair(value)
            for name, value in categoryData.items()
        }
        return MediaDeduplicationThresholds(
            defaults[MediaType.IMAGE],
            defaults[MediaType.VIDEO],
            categories,
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            "Media deduplication threshold configuration is invalid."
        ) from error


def _thresholdPair(value: Any) -> dict[MediaType, int]:
    if not isinstance(value, dict):
        raise ValueError
    image = value.get("image")
    video = value.get("video")
    if (
        not isinstance(image, int)
        or isinstance(image, bool)
        or not isinstance(video, int)
        or isinstance(video, bool)
        or not 0 <= image <= 64
        or not 0 <= video <= 64
    ):
        raise ValueError
    return {MediaType.IMAGE: image, MediaType.VIDEO: video}


def _category(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError
    return value.strip().casefold()
