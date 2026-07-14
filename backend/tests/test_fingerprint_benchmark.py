import json
from pathlib import Path

from PIL import Image

from app.media.fingerprint_benchmark import (
    MediaFingerprintBenchmark,
    loadBenchmarkPairs,
)
from app.media.media_fingerprint_service import MediaFingerprintService


def testBenchmarkRecommendsThresholdFromRealImageFiles(tmp_path: Path) -> None:
    original = tmp_path / "original.png"
    reencoded = tmp_path / "reencoded.jpg"
    unrelated = tmp_path / "unrelated.png"
    _writeGradient(original, False)
    with Image.open(original) as image:
        image.save(reencoded, quality=70)
    _writeGradient(unrelated, True)
    manifest = tmp_path / "benchmark.json"
    manifest.write_text(
        json.dumps(
            {
                "pairs": [
                    _pair("reencode", original, reencoded, True),
                    _pair("unrelated", original, unrelated, False),
                ]
            }
        ),
        encoding="utf-8-sig",
    )

    report = MediaFingerprintBenchmark(MediaFingerprintService()).run(
        loadBenchmarkPairs(manifest)
    )

    recommendation = report.recommendations[0]
    assert recommendation.category == "news"
    assert recommendation.mediaType.value == "image"
    assert recommendation.precision == 1.0
    assert recommendation.recall == 1.0
    assert recommendation.f1 == 1.0
    assert len(report.observations) == 2


def _writeGradient(path: Path, reversedValues: bool) -> None:
    values = [round(column * 255 / 89) for _row in range(80) for column in range(90)]
    if reversedValues:
        values.reverse()
    image = Image.new("L", (90, 80))
    image.putdata(values)
    image.save(path)


def _pair(pairId: str, first: Path, second: Path, duplicate: bool) -> dict[str, object]:
    return {
        "id": pairId,
        "category": "news",
        "mediaType": "image",
        "firstPath": first.name,
        "secondPath": second.name,
        "expectedDuplicate": duplicate,
    }
