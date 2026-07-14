import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.media.deduplication_thresholds import MediaDeduplicationThresholds
from app.media.models import MediaType

REVIEW_STATUSES = {"pending", "confirmed_distinct", "confirmed_duplicate", "excluded"}


@dataclass(frozen=True)
class HardNegativeReviewSummary:
    totalItems: int
    pendingItems: int
    confirmedDistinct: int
    confirmedDuplicate: int
    excluded: int


def prepareHardNegativeReview(
    manifestPath: Path,
    queuePath: Path,
    thresholds: MediaDeduplicationThresholds,
    margin: float = 5,
) -> HardNegativeReviewSummary:
    if margin < 0:
        raise ValueError("Review margin cannot be negative.")
    manifest = _loadJson(manifestPath, "benchmark manifest")
    pairs = manifest.get("pairs")
    if not isinstance(pairs, list):
        raise ValueError("Benchmark manifest is invalid.")
    items: list[dict[str, object]] = []
    for pair in pairs:
        item = _reviewCandidate(pair, thresholds, margin)
        if item is not None:
            items.append(item)
    queue = {
        "schemaVersion": 1,
        "manifestPath": os.path.relpath(
            manifestPath.resolve(), queuePath.parent.resolve()
        ),
        "margin": margin,
        "instructions": (
            "Set status to confirmed_distinct, confirmed_duplicate, or excluded; "
            "set reviewedBy and optionally notes for every item before apply."
        ),
        "items": items,
    }
    _writeJson(queuePath, queue)
    return summarizeHardNegativeReview(queuePath)


def summarizeHardNegativeReview(queuePath: Path) -> HardNegativeReviewSummary:
    queue = _loadQueue(queuePath)
    statuses = [item["status"] for item in queue["items"]]
    return HardNegativeReviewSummary(
        len(statuses),
        statuses.count("pending"),
        statuses.count("confirmed_distinct"),
        statuses.count("confirmed_duplicate"),
        statuses.count("excluded"),
    )


def applyHardNegativeReview(queuePath: Path) -> HardNegativeReviewSummary:
    queue = _loadQueue(queuePath)
    summary = summarizeHardNegativeReview(queuePath)
    if summary.pendingItems:
        raise ValueError("Hard-negative review still contains pending items.")
    manifestPath = (queuePath.parent / queue["manifestPath"]).resolve()
    manifest = _loadJson(manifestPath, "benchmark manifest")
    pairs = manifest.get("pairs")
    if not isinstance(pairs, list):
        raise ValueError("Benchmark manifest is invalid.")
    decisions = {item["id"]: item for item in queue["items"]}
    updated: list[dict[str, Any]] = []
    for pair in pairs:
        if not isinstance(pair, dict) or not isinstance(pair.get("id"), str):
            raise ValueError("Benchmark manifest is invalid.")
        decision = decisions.get(pair["id"])
        if decision is None:
            updated.append(pair)
            continue
        if decision["status"] == "excluded":
            continue
        revised = dict(pair)
        revised["expectedDuplicate"] = decision["status"] == "confirmed_duplicate"
        revised["manualReview"] = {
            "status": decision["status"],
            "reviewedBy": decision["reviewedBy"],
            "notes": decision.get("notes", ""),
        }
        updated.append(revised)
    _writeJson(manifestPath, {**manifest, "pairs": updated})
    return summary


def _reviewCandidate(
    pair: Any, thresholds: MediaDeduplicationThresholds, margin: float
) -> dict[str, object] | None:
    if not isinstance(pair, dict) or not pair.get("hardNegative"):
        return None
    try:
        mediaType = MediaType(str(pair["mediaType"]))
        category = str(pair["category"])
        distance = float(pair["selectionDistance"])
        threshold = thresholds.threshold(category, mediaType)
        if distance > threshold + margin:
            return None
        return {
            "id": str(pair["id"]),
            "category": category,
            "mediaType": mediaType.value,
            "firstPath": str(pair["firstPath"]),
            "secondPath": str(pair["secondPath"]),
            "sourceProviderIds": pair.get("sourceProviderIds", []),
            "distance": distance,
            "threshold": threshold,
            "distanceAboveThreshold": distance - threshold,
            "status": "pending",
            "reviewedBy": "",
            "notes": "",
        }
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Benchmark hard-negative pair is invalid.") from error


def _loadQueue(path: Path) -> dict[str, Any]:
    queue = _loadJson(path, "hard-negative review queue")
    items = queue.get("items")
    if (
        queue.get("schemaVersion") != 1
        or not isinstance(queue.get("manifestPath"), str)
        or not isinstance(items, list)
    ):
        raise ValueError("Hard-negative review queue is invalid.")
    for item in items:
        if not isinstance(item, dict) or item.get("status") not in REVIEW_STATUSES:
            raise ValueError("Hard-negative review queue is invalid.")
        if item["status"] != "pending" and not str(item.get("reviewedBy", "")).strip():
            raise ValueError("Completed hard-negative reviews require reviewedBy.")
    return queue


def _loadJson(path: Path, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError
        return data
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"Invalid {label}.") from error


def _writeJson(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(data, ensure_ascii=True, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
