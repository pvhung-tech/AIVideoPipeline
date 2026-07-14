import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.media.media_fingerprint_service import MediaFingerprintService
from app.media.models import MediaType
from app.media.perceptual_fingerprint import (
    imageHammingDistance,
    videoAverageHammingDistance,
)


@dataclass(frozen=True)
class BenchmarkPair:
    id: str
    category: str
    mediaType: MediaType
    firstPath: Path
    secondPath: Path
    expectedDuplicate: bool


@dataclass(frozen=True)
class BenchmarkObservation:
    pair: BenchmarkPair
    distance: float | None

    def toDictionary(self) -> dict[str, Any]:
        return {
            "id": self.pair.id,
            "category": self.pair.category,
            "mediaType": self.pair.mediaType.value,
            "expectedDuplicate": self.pair.expectedDuplicate,
            "distance": self.distance,
        }


@dataclass(frozen=True)
class BenchmarkMetrics:
    category: str
    mediaType: MediaType
    threshold: int
    pairs: int
    truePositives: int
    falsePositives: int
    falseNegatives: int
    trueNegatives: int
    precision: float
    recall: float
    f1: float

    def toDictionary(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "mediaType": self.mediaType.value,
            "recommendedThreshold": self.threshold,
            "pairs": self.pairs,
            "truePositives": self.truePositives,
            "falsePositives": self.falsePositives,
            "falseNegatives": self.falseNegatives,
            "trueNegatives": self.trueNegatives,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
        }


@dataclass(frozen=True)
class BenchmarkReport:
    observations: tuple[BenchmarkObservation, ...]
    recommendations: tuple[BenchmarkMetrics, ...]

    def toDictionary(self) -> dict[str, Any]:
        return {
            "observations": [item.toDictionary() for item in self.observations],
            "recommendations": [item.toDictionary() for item in self.recommendations],
        }


class MediaFingerprintBenchmark:
    def __init__(self, fingerprintService: MediaFingerprintService) -> None:
        self.fingerprintService = fingerprintService

    def run(self, pairs: tuple[BenchmarkPair, ...]) -> BenchmarkReport:
        observations = tuple(self._observe(pair) for pair in pairs)
        groups = sorted(
            {(item.pair.mediaType, item.pair.category) for item in observations}
        )
        recommendations = tuple(
            self._recommend(
                tuple(
                    item
                    for item in observations
                    if (item.pair.mediaType, item.pair.category) == group
                )
            )
            for group in groups
        )
        return BenchmarkReport(observations, recommendations)

    def _observe(self, pair: BenchmarkPair) -> BenchmarkObservation:
        first = self.fingerprintService.fingerprint(pair.firstPath)
        second = self.fingerprintService.fingerprint(pair.secondPath)
        distance: float | None
        if pair.mediaType == MediaType.IMAGE:
            distance = imageHammingDistance(
                first.perceptualHash or "", second.perceptualHash or ""
            )
        else:
            distance = videoAverageHammingDistance(
                first.videoFingerprint or "", second.videoFingerprint or ""
            )
        return BenchmarkObservation(pair, distance)

    def _recommend(
        self, observations: tuple[BenchmarkObservation, ...]
    ) -> BenchmarkMetrics:
        candidates = tuple(self._metrics(observations, value) for value in range(65))
        return max(
            candidates, key=lambda item: (item.f1, item.precision, -item.threshold)
        )

    def _metrics(
        self, observations: tuple[BenchmarkObservation, ...], threshold: int
    ) -> BenchmarkMetrics:
        outcomes = tuple(
            (
                item.pair.expectedDuplicate,
                item.distance is not None and item.distance <= threshold,
            )
            for item in observations
        )
        truePositives = sum(expected and predicted for expected, predicted in outcomes)
        falsePositives = sum(
            not expected and predicted for expected, predicted in outcomes
        )
        falseNegatives = sum(
            expected and not predicted for expected, predicted in outcomes
        )
        trueNegatives = sum(
            not expected and not predicted for expected, predicted in outcomes
        )
        precision = _ratio(truePositives, truePositives + falsePositives)
        recall = _ratio(truePositives, truePositives + falseNegatives)
        f1 = _ratio(2 * precision * recall, precision + recall)
        sample = observations[0].pair
        return BenchmarkMetrics(
            sample.category,
            sample.mediaType,
            threshold,
            len(observations),
            truePositives,
            falsePositives,
            falseNegatives,
            trueNegatives,
            precision,
            recall,
            f1,
        )


def loadBenchmarkPairs(path: Path) -> tuple[BenchmarkPair, ...]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        rows = data["pairs"]
        if not isinstance(rows, list) or not rows:
            raise ValueError
        return tuple(_parsePair(row, path.parent) for row in rows)
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError("Media benchmark manifest is invalid.") from error


def _parsePair(data: Any, root: Path) -> BenchmarkPair:
    if not isinstance(data, dict):
        raise ValueError("Media benchmark pair is invalid.")
    try:
        expectedDuplicate = data["expectedDuplicate"]
        if not isinstance(expectedDuplicate, bool):
            raise ValueError
        pair = BenchmarkPair(
            id=str(data["id"]),
            category=str(data["category"]),
            mediaType=MediaType(str(data["mediaType"])),
            firstPath=(root / str(data["firstPath"])).resolve(),
            secondPath=(root / str(data["secondPath"])).resolve(),
            expectedDuplicate=expectedDuplicate,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Media benchmark pair is invalid.") from error
    if not pair.id.strip() or not pair.category.strip():
        raise ValueError("Media benchmark pair is invalid.")
    return pair


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0
