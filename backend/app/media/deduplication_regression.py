import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.media.deduplication_thresholds import MediaDeduplicationThresholds
from app.media.models import MediaType

FINGERPRINTED_MEDIA_TYPES = (MediaType.IMAGE, MediaType.VIDEO)


@dataclass(frozen=True)
class DeduplicationRegressionResult:
    groupsChecked: int
    minimumPrecision: float


def checkDeduplicationRegression(
    thresholds: MediaDeduplicationThresholds, approvalPath: Path
) -> DeduplicationRegressionResult:
    data = _loadApproval(approvalPath)
    groups = data["groups"]
    minimumPrecision = float(data["minimumPrecision"])
    manualReview = data.get("manualReview")
    if (
        not isinstance(manualReview, dict)
        or manualReview.get("status") != "complete"
        or manualReview.get("pendingItems") != 0
        or not isinstance(manualReview.get("reviewedItems"), int)
        or isinstance(manualReview.get("reviewedItems"), bool)
        or manualReview["reviewedItems"] < 1
    ):
        raise ValueError("Media deduplication manual review is incomplete.")
    checked = 0
    for category, mediaGroups in groups.items():
        if not isinstance(category, str) or not isinstance(mediaGroups, dict):
            raise ValueError("Media deduplication approval is invalid.")
        for mediaType in FINGERPRINTED_MEDIA_TYPES:
            approved = _approvedGroup(mediaGroups.get(mediaType.value))
            threshold = thresholds.threshold(category, mediaType)
            if threshold < approved["maxPositiveDistance"]:
                raise ValueError(
                    f"{category}/{mediaType.value} threshold {threshold} reduces "
                    "approved recall."
                )
            if threshold >= approved["nearestNegativeDistance"]:
                raise ValueError(
                    f"{category}/{mediaType.value} threshold {threshold} reduces "
                    f"precision below {minimumPrecision:.3f}."
                )
            checked += 1
    return DeduplicationRegressionResult(checked, minimumPrecision)


def _loadApproval(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if (
            not isinstance(data, dict)
            or data.get("schemaVersion") != 1
            or not isinstance(data.get("groups"), dict)
            or not isinstance(data.get("minimumPrecision"), (int, float))
            or isinstance(data.get("minimumPrecision"), bool)
            or not 0 < float(data["minimumPrecision"]) <= 1
        ):
            raise ValueError
        return data
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("Media deduplication approval is invalid.") from error


def _approvedGroup(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        raise ValueError("Media deduplication approval is invalid.")
    maximum = value.get("maxPositiveDistance")
    nearest = value.get("nearestNegativeDistance")
    hardNegatives = value.get("hardNegatives")
    if (
        not isinstance(maximum, (int, float))
        or isinstance(maximum, bool)
        or not isinstance(nearest, (int, float))
        or isinstance(nearest, bool)
        or not isinstance(hardNegatives, int)
        or isinstance(hardNegatives, bool)
        or maximum < 0
        or nearest <= maximum
        or hardNegatives < 1
    ):
        raise ValueError("Media deduplication approval is invalid.")
    return {
        "maxPositiveDistance": float(maximum),
        "nearestNegativeDistance": float(nearest),
    }
