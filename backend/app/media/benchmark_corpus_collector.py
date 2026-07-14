import asyncio
import hashlib
import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageEnhance, UnidentifiedImageError

from app.media.errors import MediaError
from app.media.media_fingerprint_service import MediaFingerprintService
from app.media.models import MediaSearchItem, MediaSearchQuery, MediaType
from app.media.perceptual_fingerprint import (
    imageHammingDistance,
    videoAverageHammingDistance,
)
from app.media.pexels_provider import PexelsProvider
from app.media.pixabay_provider import PixabayProvider
from app.media.wikimedia_commons_provider import WikimediaCommonsProvider
from app.repositories.pixabay_search_cache_repository import (
    PixabaySearchCacheRepository,
)

logger = logging.getLogger(__name__)
IMAGE_SOURCE_COUNT = 11
VIDEO_SOURCE_COUNT = 4
PEXELS_IMAGE_SOURCE_COUNT = 5
PEXELS_VIDEO_SOURCE_COUNT = 2
PIXABAY_VIDEO_SOURCE_COUNT = 2
IMAGE_POSITIVE_PAIRS = 42
VIDEO_POSITIVE_PAIRS = 15
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 50 * 1024 * 1024
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_VIDEO_SUFFIXES = {".webm", ".mp4"}
CATEGORY_QUERIES = {
    "news": ("press conference news", "press conference"),
    "documentary": ("wildlife nature", "wildlife nature"),
    "history": ("historical archive", "historical archive"),
    "education": ("classroom teaching", "classroom teaching"),
    "podcast": ("podcast microphone studio", "recording studio"),
    "kids": ("children playing", "children playing"),
}


@dataclass(frozen=True)
class CollectedSource:
    item: MediaSearchItem
    downloadedPath: Path
    baselinePath: Path

    def toDictionary(self, root: Path) -> dict[str, object]:
        return {
            "id": self.item.id,
            "providerId": self.item.providerId,
            "mediaType": self.item.mediaType.value,
            "title": self.item.title,
            "sourceUri": self.item.sourceUri,
            "sourcePageUri": self.item.sourcePageUri,
            "license": self.item.license,
            "creator": self.item.creator,
            "creatorUri": self.item.creatorUri,
            "downloadedPath": self.downloadedPath.relative_to(root).as_posix(),
            "baselinePath": self.baselinePath.relative_to(root).as_posix(),
        }


class BenchmarkCorpusCollector:
    def __init__(
        self,
        userAgent: str,
        pexelsApiKey: str | None = None,
        pixabayApiKey: str | None = None,
        ffmpegPath: str | None = None,
        timeoutSeconds: float = 120,
    ) -> None:
        if not userAgent.strip():
            raise ValueError("Wikimedia User-Agent is required.")
        self.userAgent = userAgent.strip()
        self.ffmpegPath = ffmpegPath or shutil.which("ffmpeg")
        if self.ffmpegPath is None:
            raise ValueError("FFmpeg is required to collect a benchmark corpus.")
        self.timeoutSeconds = timeoutSeconds
        self.provider = WikimediaCommonsProvider(
            "https://commons.wikimedia.org", self.userAgent, timeoutSeconds
        )
        self.pexelsProvider = (
            PexelsProvider(pexelsApiKey, "https://api.pexels.com", timeoutSeconds)
            if pexelsApiKey
            else None
        )
        self.pixabayApiKey = pixabayApiKey.strip() if pixabayApiKey else None
        self.fingerprintService = MediaFingerprintService(
            self.ffmpegPath, timeoutSeconds
        )

    async def collect(
        self,
        outputRoot: Path,
        pairsPerCategory: int = 100,
        categories: tuple[str, ...] | None = None,
    ) -> tuple[Path, Path]:
        if pairsPerCategory < 100 or pairsPerCategory > 500 or pairsPerCategory % 2:
            raise ValueError(
                "Pairs per category must be an even number from 100 to 500."
            )
        outputRoot.mkdir(parents=True, exist_ok=True)
        pixabayProvider = (
            PixabayProvider(
                self.pixabayApiKey,
                "https://pixabay.com",
                self.timeoutSeconds,
                PixabaySearchCacheRepository(
                    outputRoot / ".provider-cache" / "pixabay"
                ),
            )
            if self.pixabayApiKey
            else None
        )
        selectedCategories = categories or tuple(CATEGORY_QUERIES)
        if not selectedCategories or any(
            category not in CATEGORY_QUERIES for category in selectedCategories
        ):
            raise ValueError("Benchmark categories are invalid.")
        allPairs: list[dict[str, object]] = []
        provenance: dict[str, list[dict[str, object]]] = {}
        for category in selectedCategories:
            queries = CATEGORY_QUERIES[category]
            logger.info("Collecting benchmark category %s", category)
            images = await self._collectSources(
                outputRoot, category, MediaType.IMAGE, queries[0], IMAGE_SOURCE_COUNT
            )
            videos = await self._collectSources(
                outputRoot, category, MediaType.VIDEO, queries[1], VIDEO_SOURCE_COUNT
            )
            if self.pexelsProvider is not None:
                images += await self._collectSources(
                    outputRoot,
                    category,
                    MediaType.IMAGE,
                    queries[0],
                    PEXELS_IMAGE_SOURCE_COUNT,
                    self.pexelsProvider,
                )
                videos += await self._collectSources(
                    outputRoot,
                    category,
                    MediaType.VIDEO,
                    queries[1],
                    PEXELS_VIDEO_SOURCE_COUNT,
                    self.pexelsProvider,
                )
            if pixabayProvider is not None:
                videos += await self._collectSources(
                    outputRoot,
                    category,
                    MediaType.VIDEO,
                    queries[1],
                    PIXABAY_VIDEO_SOURCE_COUNT,
                    pixabayProvider,
                )
            provenance[category] = [
                source.toDictionary(outputRoot) for source in (*images, *videos)
            ]
            allPairs.extend(
                self._buildPairs(outputRoot, category, images, videos, pairsPerCategory)
            )
        manifestPath = outputRoot / "benchmark.json"
        provenancePath = outputRoot / "provenance.json"
        self._writeJson(manifestPath, {"pairs": allPairs})
        self._writeJson(
            provenancePath,
            {
                "sources": ["Wikimedia Commons", "Pexels", "Pixabay"],
                "userAgentPolicy": (
                    "https://foundation.wikimedia.org/wiki/"
                    "Policy:Wikimedia_Foundation_User-Agent_Policy/en"
                ),
                "categories": provenance,
            },
        )
        return manifestPath, provenancePath

    async def _collectSources(
        self,
        root: Path,
        category: str,
        mediaType: MediaType,
        query: str,
        required: int,
        provider: (
            WikimediaCommonsProvider | PexelsProvider | PixabayProvider | None
        ) = None,
    ) -> tuple[CollectedSource, ...]:
        selectedProvider = provider or self.provider
        searchText = (
            query
            if isinstance(selectedProvider, (PexelsProvider, PixabayProvider))
            else self._searchText(query, mediaType)
        )
        page = await selectedProvider.search(
            MediaSearchQuery(searchText, (mediaType,), 50, 0)
        )
        candidates = tuple(
            item for item in page.items if self._eligible(item, mediaType)
        )
        collected: list[CollectedSource] = []
        for item in candidates:
            try:
                collected.append(await self._downloadAndNormalize(root, category, item))
            except (MediaError, OSError, UnidentifiedImageError):
                logger.exception("Skipping unusable benchmark asset %s", item.id)
            if len(collected) >= required:
                break
        if len(collected) < required:
            raise MediaError(
                "BENCHMARK_CORPUS_INSUFFICIENT",
                f"Category '{category}' has only {len(collected)} usable "
                f"{mediaType.value} sources; {required} required.",
            )
        return tuple(collected)

    def _searchText(self, query: str, mediaType: MediaType) -> str:
        if mediaType == MediaType.IMAGE:
            return f"{query} filetype:bitmap -filemime:image/tiff filesize:<10240"
        return f"{query} filetype:video filemime:webm filesize:<51200"

    def _eligible(self, item: MediaSearchItem, mediaType: MediaType) -> bool:
        suffix = Path(urlparse(item.sourceUri).path).suffix.lower()
        allowed = (
            SUPPORTED_IMAGE_SUFFIXES
            if mediaType == MediaType.IMAGE
            else SUPPORTED_VIDEO_SUFFIXES
        )
        sizeLimit = MAX_IMAGE_BYTES if mediaType == MediaType.IMAGE else MAX_VIDEO_BYTES
        return bool(
            item.license
            and item.sourcePageUri
            and (item.fileSizeBytes is None or item.fileSizeBytes <= sizeLimit)
            and suffix in allowed
        )

    async def _downloadAndNormalize(
        self, root: Path, category: str, item: MediaSearchItem
    ) -> CollectedSource:
        suffix = Path(urlparse(item.sourceUri).path).suffix.lower()
        sourceDirectory = root / "sources" / category
        baselineDirectory = root / "files" / category / item.mediaType.value
        sourceDirectory.mkdir(parents=True, exist_ok=True)
        baselineDirectory.mkdir(parents=True, exist_ok=True)
        name = hashlib.sha256(item.sourceUri.encode("utf-8")).hexdigest()[:16]
        downloaded = sourceDirectory / f"{name}{suffix}"
        baseline = (
            baselineDirectory
            / f"{name}-baseline.{'jpg' if item.mediaType == MediaType.IMAGE else 'mp4'}"
        )
        if not downloaded.exists():
            await self._download(
                item.sourceUri, downloaded, item.mediaType, item.providerId
            )
        if not baseline.exists():
            if item.mediaType == MediaType.IMAGE:
                await asyncio.to_thread(self._normalizeImage, downloaded, baseline)
            else:
                await asyncio.to_thread(self._normalizeVideo, downloaded, baseline)
        return CollectedSource(item, downloaded, baseline)

    async def _download(
        self,
        sourceUri: str,
        target: Path,
        mediaType: MediaType,
        providerId: str,
    ) -> None:
        limit = MAX_IMAGE_BYTES if mediaType == MediaType.IMAGE else MAX_VIDEO_BYTES
        temporary = target.with_suffix(target.suffix + ".part")
        size = 0
        try:
            async with httpx.AsyncClient(
                timeout=self.timeoutSeconds,
                follow_redirects=True,
                headers={"User-Agent": self.userAgent},
            ) as client:
                async with client.stream("GET", sourceUri) as response:
                    response.raise_for_status()
                    self._validateSourceUri(str(response.url), providerId)
                    with temporary.open("wb") as output:
                        async for chunk in response.aiter_bytes(1024 * 1024):
                            size += len(chunk)
                            if size > limit:
                                raise MediaError(
                                    "BENCHMARK_ASSET_TOO_LARGE",
                                    "Benchmark asset exceeded its size limit.",
                                )
                            output.write(chunk)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

    def _validateSourceUri(self, value: str, providerId: str) -> None:
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        trustedSuffixes = {
            "wikimedia": (".wikimedia.org",),
            "pexels": (".pexels.com",),
            "pixabay": (".pixabay.com",),
        }
        trusted = any(
            host.endswith(suffix) for suffix in trustedSuffixes.get(providerId, ())
        )
        if parsed.scheme != "https" or not trusted:
            raise MediaError(
                "INVALID_BENCHMARK_SOURCE", "Benchmark source is not trusted."
            )

    def _normalizeImage(self, source: Path, target: Path) -> None:
        with Image.open(source) as image:
            normalized = image.convert("RGB")
            normalized.thumbnail((1280, 720), Image.Resampling.LANCZOS)
            normalized.save(target, "JPEG", quality=90, optimize=True)

    def _normalizeVideo(self, source: Path, target: Path) -> None:
        self._runFfmpeg(
            source,
            target,
            "scale=640:-2:force_original_aspect_ratio=decrease",
            "22",
        )

    def _buildPairs(
        self,
        root: Path,
        category: str,
        images: tuple[CollectedSource, ...],
        videos: tuple[CollectedSource, ...],
        pairCount: int,
    ) -> list[dict[str, object]]:
        positiveCount = pairCount // 2
        videoPositiveCount = min(VIDEO_POSITIVE_PAIRS, positiveCount // 4)
        imagePositiveCount = positiveCount - videoPositiveCount
        pairs = self._positivePairs(
            root, category, images, imagePositiveCount, MediaType.IMAGE
        )
        pairs += self._positivePairs(
            root, category, videos, videoPositiveCount, MediaType.VIDEO
        )
        pairs += self._negativePairs(root, category, images, imagePositiveCount)
        pairs += self._negativePairs(root, category, videos, videoPositiveCount)
        return pairs

    def _positivePairs(
        self,
        root: Path,
        category: str,
        sources: tuple[CollectedSource, ...],
        count: int,
        mediaType: MediaType,
    ) -> list[dict[str, object]]:
        pairs: list[dict[str, object]] = []
        for index in range(count):
            source = sources[index % len(sources)]
            variant = source.baselinePath.with_name(
                f"{source.baselinePath.stem}-variant-{index}{source.baselinePath.suffix}"
            )
            if not variant.exists():
                if mediaType == MediaType.IMAGE:
                    self._imageVariant(source.baselinePath, variant, index % 4)
                else:
                    self._videoVariant(source.baselinePath, variant, index % 4)
            pairs.append(
                self._pair(
                    root, category, mediaType, source.baselinePath, variant, True, index
                )
            )
        return pairs

    def _negativePairs(
        self,
        root: Path,
        category: str,
        sources: tuple[CollectedSource, ...],
        count: int,
    ) -> list[dict[str, object]]:
        ranked = self._rankNegativeCandidates(sources)
        return [
            self._pair(
                root,
                category,
                sources[0].item.mediaType,
                ranked[index % len(ranked)][1].baselinePath,
                ranked[index % len(ranked)][2].baselinePath,
                False,
                index,
                hardNegative=True,
                distance=ranked[index % len(ranked)][0],
                providerIds=(
                    ranked[index % len(ranked)][1].item.providerId,
                    ranked[index % len(ranked)][2].item.providerId,
                ),
            )
            for index in range(count)
        ]

    def _rankNegativeCandidates(
        self, sources: tuple[CollectedSource, ...]
    ) -> list[tuple[float, CollectedSource, CollectedSource]]:
        fingerprints = {
            source: self.fingerprintService.fingerprint(source.baselinePath)
            for source in sources
        }
        ranked: list[tuple[float, CollectedSource, CollectedSource]] = []
        for index, first in enumerate(sources):
            for second in sources[index + 1 :]:
                firstFingerprint = fingerprints[first]
                secondFingerprint = fingerprints[second]
                distance: float | None
                if first.item.mediaType == MediaType.IMAGE:
                    distance = imageHammingDistance(
                        firstFingerprint.perceptualHash or "",
                        secondFingerprint.perceptualHash or "",
                    )
                else:
                    distance = videoAverageHammingDistance(
                        firstFingerprint.videoFingerprint or "",
                        secondFingerprint.videoFingerprint or "",
                    )
                if distance is not None:
                    ranked.append((float(distance), first, second))
        if not ranked:
            raise MediaError(
                "BENCHMARK_HARD_NEGATIVES_UNAVAILABLE",
                "Unable to find compatible hard-negative media pairs.",
            )
        return sorted(ranked, key=lambda value: value[0])

    def _imageVariant(self, source: Path, target: Path, mode: int) -> None:
        with Image.open(source) as image:
            changed = image.convert("RGB")
            if mode == 0:
                changed.save(target, "JPEG", quality=55)
                return
            if mode == 1:
                changed.thumbnail((720, 480), Image.Resampling.LANCZOS)
            elif mode == 2:
                changed = ImageEnhance.Brightness(changed).enhance(0.75)
            else:
                width, height = changed.size
                changed = changed.crop(
                    (width // 20, height // 20, width * 19 // 20, height * 19 // 20)
                ).resize((width, height), Image.Resampling.LANCZOS)
            changed.save(target, "JPEG", quality=75)

    def _videoVariant(self, source: Path, target: Path, mode: int) -> None:
        filters = (
            "scale=640:-2:force_original_aspect_ratio=decrease",
            "scale=480:-2:force_original_aspect_ratio=decrease",
            "eq=brightness=-0.12",
            "crop=iw*0.9:ih*0.9,scale=640:-2",
        )
        self._runFfmpeg(source, target, filters[mode], "32")

    def _runFfmpeg(
        self, source: Path, target: Path, videoFilter: str, crf: str
    ) -> None:
        result = subprocess.run(
            (
                self.ffmpegPath or "ffmpeg",
                "-y",
                "-v",
                "error",
                "-nostdin",
                "-i",
                str(source),
                "-t",
                "30",
                "-an",
                "-vf",
                videoFilter,
                "-c:v",
                "libx264",
                "-crf",
                crf,
                "-pix_fmt",
                "yuv420p",
                str(target),
            ),
            capture_output=True,
            check=False,
            timeout=self.timeoutSeconds,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            raise MediaError(
                "BENCHMARK_TRANSFORM_FAILED", "Unable to transform benchmark media."
            )

    def _pair(
        self,
        root: Path,
        category: str,
        mediaType: MediaType,
        first: Path,
        second: Path,
        duplicate: bool,
        index: int,
        hardNegative: bool = False,
        distance: float | None = None,
        providerIds: tuple[str, str] | None = None,
    ) -> dict[str, object]:
        label = "positive" if duplicate else "negative"
        pair: dict[str, object] = {
            "id": f"{category}-{mediaType.value}-{label}-{index:03d}",
            "category": category,
            "mediaType": mediaType.value,
            "firstPath": first.relative_to(root).as_posix(),
            "secondPath": second.relative_to(root).as_posix(),
            "expectedDuplicate": duplicate,
        }
        if hardNegative:
            pair["hardNegative"] = True
            pair["selectionDistance"] = distance
            pair["sourceProviderIds"] = list(providerIds or ())
            pair["labelBasis"] = "distinct-source-pages"
        return pair

    def _writeJson(self, path: Path, data: object) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(data, ensure_ascii=True, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(path)
