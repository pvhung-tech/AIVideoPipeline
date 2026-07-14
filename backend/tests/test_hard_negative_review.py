import json
from pathlib import Path

import pytest

from app.media.deduplication_thresholds import MediaDeduplicationThresholds
from app.media.hard_negative_review import (
    applyHardNegativeReview,
    prepareHardNegativeReview,
)


def testReviewQueueRequiresDecisionsBeforeAtomicApply(tmp_path: Path) -> None:
    manifest = tmp_path / "benchmark.json"
    queue = tmp_path / "review.json"
    manifest.write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "id": "near",
                        "category": "news",
                        "mediaType": "image",
                        "firstPath": "first.jpg",
                        "secondPath": "second.jpg",
                        "expectedDuplicate": False,
                        "hardNegative": True,
                        "selectionDistance": 12,
                    },
                    {
                        "id": "far",
                        "category": "news",
                        "mediaType": "image",
                        "firstPath": "first.jpg",
                        "secondPath": "far.jpg",
                        "expectedDuplicate": False,
                        "hardNegative": True,
                        "selectionDistance": 30,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    thresholds = MediaDeduplicationThresholds(8, 8, {})

    summary = prepareHardNegativeReview(manifest, queue, thresholds, margin=5)

    assert summary.totalItems == 1
    with pytest.raises(ValueError, match="pending"):
        applyHardNegativeReview(queue)

    review = json.loads(queue.read_text(encoding="utf-8"))
    review["items"][0].update(
        {"status": "confirmed_duplicate", "reviewedBy": "reviewer"}
    )
    queue.write_text(json.dumps(review), encoding="utf-8")

    applied = applyHardNegativeReview(queue)
    pairs = json.loads(manifest.read_text(encoding="utf-8"))["pairs"]
    assert applied.confirmedDuplicate == 1
    assert pairs[0]["expectedDuplicate"] is True
    assert pairs[0]["manualReview"]["reviewedBy"] == "reviewer"
