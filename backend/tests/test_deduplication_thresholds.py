import json
from pathlib import Path

import pytest

from app.media.deduplication_thresholds import loadMediaDeduplicationThresholds
from app.media.models import MediaType


def testLoadsCategoryThresholdsAndFallbacks(tmp_path: Path) -> None:
    path = tmp_path / "thresholds.json"
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "default": {"image": 8, "video": 7},
                "categories": {"News": {"image": 14, "video": 15}},
            }
        ),
        encoding="utf-8",
    )

    thresholds = loadMediaDeduplicationThresholds(path)

    assert thresholds.threshold(" news ", MediaType.IMAGE) == 14
    assert thresholds.threshold("unknown", MediaType.VIDEO) == 7


def testRejectsOutOfRangeThreshold(tmp_path: Path) -> None:
    path = tmp_path / "thresholds.json"
    path.write_text(
        '{"schemaVersion":1,"default":{"image":8,"video":8},'
        '"categories":{"news":{"image":65,"video":8}}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        loadMediaDeduplicationThresholds(path)
