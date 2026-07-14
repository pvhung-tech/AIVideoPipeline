import json
from pathlib import Path

import pytest

from app.media.deduplication_regression import checkDeduplicationRegression
from app.media.deduplication_thresholds import (
    MediaDeduplicationThresholds,
    loadMediaDeduplicationThresholds,
)
from app.media.models import MediaType


def testApprovedThresholdConfigurationPasses() -> None:
    root = Path(__file__).resolve().parents[2]
    thresholds = loadMediaDeduplicationThresholds(
        root / "configs" / "media_dedup_thresholds.json"
    )

    result = checkDeduplicationRegression(
        thresholds, root / "configs" / "media_dedup_approval.json"
    )

    assert result.groupsChecked == 10
    assert result.minimumPrecision == 1.0


def testRejectsThresholdThatReducesApprovedPrecision() -> None:
    root = Path(__file__).resolve().parents[2]
    thresholds = MediaDeduplicationThresholds(
        8,
        8,
        {
            "news": {MediaType.IMAGE: 16, MediaType.VIDEO: 15},
            "documentary": {MediaType.IMAGE: 10, MediaType.VIDEO: 7},
            "education": {MediaType.IMAGE: 16, MediaType.VIDEO: 8},
            "history": {MediaType.IMAGE: 13, MediaType.VIDEO: 13},
            "podcast": {MediaType.IMAGE: 12, MediaType.VIDEO: 11},
        },
    )

    with pytest.raises(ValueError, match="reduces precision"):
        checkDeduplicationRegression(
            thresholds, root / "configs" / "media_dedup_approval.json"
        )


def testRejectsIncompleteManualReview(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    approval = json.loads(
        (root / "configs" / "media_dedup_approval.json").read_text(encoding="utf-8")
    )
    approval["manualReview"]["status"] = "pending"
    path = tmp_path / "approval.json"
    path.write_text(json.dumps(approval), encoding="utf-8")
    thresholds = loadMediaDeduplicationThresholds(
        root / "configs" / "media_dedup_thresholds.json"
    )

    with pytest.raises(ValueError, match="manual review is incomplete"):
        checkDeduplicationRegression(thresholds, path)
