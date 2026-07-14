import re
from dataclasses import dataclass, replace
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

from app.media.cache_manifest import MediaCacheManifest
from app.media.deduplication_thresholds import MediaDeduplicationThresholds
from app.media.models import (
    MediaDeduplicationStatistics,
    MediaSearchItem,
    MediaSearchPage,
    MediaType,
)
from app.media.perceptual_fingerprint import (
    IMAGE_HASH_PREFIX,
    VIDEO_HASH_PREFIX,
    imageHammingDistance,
    videoAverageHammingDistance,
)

FingerprintIndex = dict[str, str]


@dataclass(frozen=True)
class MediaRankingResult:
    items: tuple[MediaSearchItem, ...]
    statistics: MediaDeduplicationStatistics


class MediaResultRanker:
    def __init__(self, thresholds: MediaDeduplicationThresholds | None = None) -> None:
        self.thresholds = thresholds or MediaDeduplicationThresholds(8, 8, {})

    def rankAndDeduplicate(
        self,
        pages: tuple[MediaSearchPage, ...],
        manifest: MediaCacheManifest | None = None,
        contentCategory: str | None = None,
    ) -> tuple[MediaSearchItem, ...]:
        return self.rankWithStatistics(pages, manifest, contentCategory).items

    def rankWithStatistics(
        self,
        pages: tuple[MediaSearchPage, ...],
        manifest: MediaCacheManifest | None = None,
        contentCategory: str | None = None,
    ) -> MediaRankingResult:
        ranked: list[tuple[float, int, MediaSearchItem]] = []
        for page in pages:
            for rank, item in enumerate(page.items):
                normalizedScore = min(1.0, max(0.0, item.score))
                reciprocalRank = 1.0 / (rank + 1)
                score = 0.75 * reciprocalRank + 0.25 * normalizedScore
                ranked.append((score, rank, replace(item, score=score)))
        ranked.sort(
            key=lambda value: (
                -value[0],
                value[1],
                value[2].providerId,
                value[2].id,
            )
        )
        deduplicated: list[MediaSearchItem] = []
        seenKeys: set[str] = set()
        seenFingerprints: dict[str, list[str]] = {"image": [], "video": []}
        fingerprintIndex = self._fingerprintIndex(manifest)
        fingerprintedCandidates = 0
        canonicalDuplicates = 0
        imageDuplicates = 0
        videoDuplicates = 0
        imageThreshold = self.thresholds.threshold(contentCategory, MediaType.IMAGE)
        videoThreshold = self.thresholds.threshold(contentCategory, MediaType.VIDEO)
        for _score, _rank, item in ranked:
            keys = self._identityKeys(item)
            fingerprint = self._itemFingerprint(item, fingerprintIndex)
            fingerprintedCandidates += int(fingerprint is not None)
            if keys & seenKeys:
                canonicalDuplicates += 1
                continue
            if self._matchesFingerprint(
                fingerprint,
                seenFingerprints[item.mediaType.value],
                imageThreshold if item.mediaType == MediaType.IMAGE else videoThreshold,
            ):
                if item.mediaType.value == "image":
                    imageDuplicates += 1
                else:
                    videoDuplicates += 1
                continue
            deduplicated.append(item)
            seenKeys.update(keys)
            if fingerprint:
                seenFingerprints[item.mediaType.value].append(fingerprint)
        statistics = MediaDeduplicationStatistics(
            len(ranked),
            len(deduplicated),
            fingerprintedCandidates,
            canonicalDuplicates,
            imageDuplicates,
            videoDuplicates,
            imageThreshold,
            videoThreshold,
        )
        return MediaRankingResult(tuple(deduplicated), statistics)

    def _fingerprintIndex(
        self, manifest: MediaCacheManifest | None
    ) -> FingerprintIndex:
        index: FingerprintIndex = {}
        if manifest is None:
            return index
        for entry in manifest.entries:
            fingerprint = entry.perceptualHash or entry.videoFingerprint
            if fingerprint is None:
                continue
            for source in entry.sources:
                index[f"id:{source.providerId}:{source.mediaId}"] = fingerprint
                index[f"source:{self._canonicalUri(source.sourceUri)}"] = fingerprint
        return index

    def _itemFingerprint(
        self, item: MediaSearchItem, index: FingerprintIndex
    ) -> str | None:
        fingerprint = index.get(f"id:{item.providerId}:{item.id}") or index.get(
            f"source:{self._canonicalUri(item.sourceUri)}"
        )
        if fingerprint is None:
            return None
        expectedPrefix = (
            IMAGE_HASH_PREFIX if item.mediaType.value == "image" else VIDEO_HASH_PREFIX
        )
        return fingerprint if fingerprint.startswith(expectedPrefix) else None

    def _matchesFingerprint(
        self, candidate: str | None, retained: list[str], threshold: int
    ) -> bool:
        if candidate is None:
            return False
        return any(
            self._isFingerprintMatch(candidate, value, threshold) for value in retained
        )

    def _isFingerprintMatch(self, first: str, second: str, threshold: int) -> bool:
        imageDistance = imageHammingDistance(first, second)
        if imageDistance is not None:
            return imageDistance <= threshold
        videoDistance = videoAverageHammingDistance(first, second)
        return videoDistance is not None and videoDistance <= threshold

    def _identityKeys(self, item: MediaSearchItem) -> set[str]:
        keys = {f"source:{self._canonicalUri(item.sourceUri)}"}
        if item.sourcePageUri:
            keys.add(f"page:{self._canonicalUri(item.sourcePageUri)}")
        title = self._normalizeText(item.title)
        if item.fileSizeBytes is not None and title:
            keys.add(f"metadata:{item.mediaType.value}:{item.fileSizeBytes}:{title}")
        return keys

    def _canonicalUri(self, value: str) -> str:
        parsed = urlsplit(value.strip())
        path = unquote(parsed.path)
        if parsed.scheme.lower() == "file":
            path = path.casefold()
        query = urlencode(
            sorted(
                (key, itemValue)
                for key, itemValue in parse_qsl(parsed.query, keep_blank_values=True)
                if not self._isTrackingParameter(key)
            )
        )
        return urlunsplit(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                path.rstrip("/"),
                query,
                "",
            )
        )

    def _isTrackingParameter(self, key: str) -> bool:
        normalized = key.casefold()
        return normalized.startswith("utm_") or normalized in {
            "download",
            "expires",
            "signature",
            "token",
        }

    def _normalizeText(self, value: str) -> str:
        return " ".join(re.findall(r"\w+", value.casefold()))
