import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from functools import partial
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

import httpx

from app.media.errors import MediaError
from app.media.http_retry_policy import HttpRetryPolicy
from app.media.models import (
    MediaSearchItem,
    MediaSearchPage,
    MediaSearchQuery,
    MediaType,
)
from app.media.search_pagination import (
    calculateResultCounts,
    calculateTypeOffsets,
    mergeTypeItems,
)
from app.repositories.dvids_search_cache_repository import DvidsSearchCacheRepository

logger = logging.getLogger(__name__)
DVIDS_VIDEO_HEIGHT_LIMITS = {"highest": None, "1080p": 1080, "720p": 720}
DVIDS_SEARCH_CACHE_TTL_SECONDS = 24 * 60 * 60
DVIDS_ASSET_CACHE_TTL_SECONDS = 60 * 60
DVIDS_NEGATIVE_CACHE_TTL_SECONDS = 5 * 60
DVIDS_LAZY_SOURCE_SCHEME = "dvids"


class _DvidsAssetUnavailable(Exception):
    def __init__(self, statusCode: int) -> None:
        super().__init__(f"DVIDS asset is unavailable with status {statusCode}.")
        self.statusCode = statusCode


class DvidsProvider:
    providerId = "dvids"

    def __init__(
        self,
        apiKey: str | None,
        baseUrl: str,
        timeoutSeconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
        videoQuality: str = "highest",
        maxVideoFileSizeBytes: int = 0,
        cacheRepository: DvidsSearchCacheRepository | None = None,
        maxAttempts: int = 3,
        initialDelaySeconds: float = 1,
        maxDelaySeconds: float = 60,
        jitterRatio: float = 0.25,
        cacheTtlSeconds: int = DVIDS_SEARCH_CACHE_TTL_SECONDS,
        assetCacheTtlSeconds: int = DVIDS_ASSET_CACHE_TTL_SECONDS,
        negativeCacheRepository: DvidsSearchCacheRepository | None = None,
        negativeCacheTtlSeconds: int = DVIDS_NEGATIVE_CACHE_TTL_SECONDS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        nowProvider: Callable[[], datetime] | None = None,
        randomProvider: Callable[[], float] = random.random,
    ) -> None:
        normalizedQuality = videoQuality.strip().lower()
        if normalizedQuality not in DVIDS_VIDEO_HEIGHT_LIMITS:
            raise ValueError("DVIDS video quality must be highest, 1080p, or 720p.")
        if maxVideoFileSizeBytes < 0:
            raise ValueError("DVIDS video size limit cannot be negative.")
        if (
            maxAttempts < 1
            or cacheTtlSeconds < 1
            or assetCacheTtlSeconds < 1
            or assetCacheTtlSeconds > cacheTtlSeconds
            or negativeCacheTtlSeconds < 1
            or negativeCacheTtlSeconds > assetCacheTtlSeconds
        ):
            raise ValueError("DVIDS retry and cache settings are invalid.")
        self.apiKey = apiKey.strip() if apiKey else None
        self.baseUrl = baseUrl.rstrip("/")
        self.timeoutSeconds = timeoutSeconds
        self.transport = transport
        self.videoQuality = normalizedQuality
        self.maxVideoFileSizeBytes = maxVideoFileSizeBytes
        self.cacheRepository = cacheRepository
        self.maxAttempts = maxAttempts
        self.cacheTtlSeconds = cacheTtlSeconds
        self.assetCacheTtlSeconds = assetCacheTtlSeconds
        self.negativeCacheRepository = negativeCacheRepository
        self.negativeCacheTtlSeconds = negativeCacheTtlSeconds
        self.sleep = sleep
        self.nowProvider = nowProvider or (lambda: datetime.now(UTC))
        self.retryPolicy = HttpRetryPolicy(
            initialDelaySeconds,
            maxDelaySeconds,
            jitterRatio,
            self.nowProvider,
            randomProvider,
        )
        self.cachePruned = False
        self.negativeCachePruned = False
        self.inFlightRequests: dict[str, asyncio.Task[dict[str, Any]]] = {}

    async def search(self, query: MediaSearchQuery) -> MediaSearchPage:
        if self.apiKey is None:
            raise MediaError(
                "MEDIA_PROVIDER_NOT_CONFIGURED",
                "DVIDS is not configured. Set DVIDS_API_KEY.",
            )
        counts = calculateResultCounts(query)
        offsets = calculateTypeOffsets(query)
        results = await asyncio.gather(
            *(
                self._searchType(
                    query.text,
                    mediaType,
                    offsets[mediaType],
                    counts[mediaType],
                )
                for mediaType in query.mediaTypes
            )
        )
        pages = dict(zip(query.mediaTypes, results, strict=True))
        items = mergeTypeItems(query, {key: value[1] for key, value in pages.items()})
        return MediaSearchPage(
            providerId=self.providerId,
            query=query.text,
            totalResults=sum(value[0] for value in pages.values()),
            offset=query.offset,
            limit=query.limit,
            truncated=False,
            items=items,
        )

    async def _searchType(
        self,
        text: str,
        mediaType: MediaType,
        offset: int,
        count: int,
    ) -> tuple[int, list[MediaSearchItem]]:
        if count == 0:
            return 0, []
        pageSize = min(50, max(count, 10))
        page = (offset // pageSize) + 1
        pageOffset = offset % pageSize
        collected: list[MediaSearchItem] = []
        totalResults = 0
        while len(collected) < count:
            data = await self._request(
                "/search",
                {
                    "q": text,
                    "type": mediaType.value,
                    "page": page,
                    "max_results": pageSize,
                    "thumb_width": 640,
                    "api_key": self.apiKey or "",
                },
            )
            totalResults = self._totalResults(data)
            rawItems = data.get("results")
            if not isinstance(rawItems, list):
                raise self._invalidResponse("search results")
            selected = rawItems[pageOffset:]
            collected.extend(
                item
                for item in (
                    self._parseSearchSummary(result, mediaType)
                    for result in selected[: max(0, count - len(collected))]
                )
                if item is not None
            )
            if len(rawItems) < pageSize or not rawItems:
                break
            page += 1
            pageOffset = 0
        return totalResults, collected[:count]

    async def resolveAssetSource(self, sourceUri: str) -> str:
        if self.apiKey is None:
            raise MediaError(
                "MEDIA_PROVIDER_NOT_CONFIGURED",
                "DVIDS is not configured. Set DVIDS_API_KEY.",
            )
        assetId, mediaType = self._parseLazySourceUri(sourceUri)
        try:
            data = await self._request(
                "/asset", {"id": assetId, "api_key": self.apiKey or ""}
            )
        except _DvidsAssetUnavailable as error:
            raise MediaError(
                "MEDIA_SOURCE_NOT_FOUND", "DVIDS media asset is unavailable."
            ) from error
        asset = data.get("results")
        if not isinstance(asset, dict):
            raise self._invalidResponse("asset details")
        resolvedSourceUri, _fileSize = self._source(asset, mediaType)
        if resolvedSourceUri is None:
            raise MediaError(
                "MEDIA_SOURCE_NOT_FOUND",
                "DVIDS media asset has no eligible download source.",
            )
        return resolvedSourceUri

    def _parseSearchSummary(
        self, result: Any, mediaType: MediaType
    ) -> MediaSearchItem | None:
        if not isinstance(result, dict):
            return None
        assetId = self._string(result.get("id"))
        if assetId is None:
            return None
        creator = self._string(result.get("credit"))
        return MediaSearchItem(
            id=f"dvids-{assetId.replace(':', '-')}",
            providerId=self.providerId,
            mediaType=mediaType,
            title=self._string(result.get("title")) or "DVIDS media",
            sourceUri=self._lazySourceUri(assetId, mediaType),
            previewUri=self._previewUri(result.get("thumbnail")),
            fileSizeBytes=None,
            modifiedAt=self._timestamp(result.get("timestamp")),
            score=self._score(result.get("rating")),
            license="Public Domain unless otherwise specified",
            sourcePageUri=self._string(result.get("url")),
            creator=creator,
        )

    def _lazySourceUri(self, assetId: str, mediaType: MediaType) -> str:
        return (
            f"{DVIDS_LAZY_SOURCE_SCHEME}://asset/"
            f"{quote(assetId, safe='')}?type={mediaType.value}"
        )

    def _parseLazySourceUri(self, sourceUri: str) -> tuple[str, MediaType]:
        parsed = urlparse(sourceUri)
        query = parse_qs(parsed.query)
        mediaTypeValue = query.get("type", [""])[0]
        if (
            parsed.scheme != DVIDS_LAZY_SOURCE_SCHEME
            or parsed.netloc != "asset"
            or not parsed.path.strip("/")
            or mediaTypeValue not in {MediaType.IMAGE.value, MediaType.VIDEO.value}
        ):
            raise MediaError(
                "INVALID_MEDIA_SOURCE", "DVIDS lazy asset source is invalid."
            )
        return unquote(parsed.path.strip("/")), MediaType(mediaTypeValue)

    def _previewUri(self, value: Any) -> str | None:
        if isinstance(value, dict):
            return self._string(value.get("url"))
        return self._string(value)

    async def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.cacheRepository is None:
            return await self._fetch(path, params)
        cacheKey = self.cacheRepository.makeKey(f"{self.baseUrl}{path}", params)
        now = self.nowProvider()
        entryTtlSeconds = self._cacheTtlSeconds(path)
        if path == "/asset" and await self._isNegativeCached(cacheKey, now):
            raise _DvidsAssetUnavailable(404)
        if not self.cachePruned:
            await asyncio.to_thread(
                self.cacheRepository.pruneExpired, now, self.cacheTtlSeconds
            )
            self.cachePruned = True
        try:
            cached = await asyncio.to_thread(
                self.cacheRepository.get, cacheKey, now, entryTtlSeconds
            )
            if cached is not None:
                return cached
        except MediaError:
            logger.exception("Unable to read persistent DVIDS search cache")
        task = self.inFlightRequests.get(cacheKey)
        if task is None:
            task = asyncio.create_task(self._fetchAndCache(cacheKey, path, params))
            self.inFlightRequests[cacheKey] = task
            task.add_done_callback(partial(self._removeInFlight, cacheKey))
        return await asyncio.shield(task)

    async def _isNegativeCached(self, cacheKey: str, now: datetime) -> bool:
        if self.negativeCacheRepository is None:
            return False
        if not self.negativeCachePruned:
            await asyncio.to_thread(
                self.negativeCacheRepository.pruneExpired,
                now,
                self.negativeCacheTtlSeconds,
            )
            self.negativeCachePruned = True
        try:
            cached = await asyncio.to_thread(
                self.negativeCacheRepository.get,
                cacheKey,
                now,
                self.negativeCacheTtlSeconds,
            )
            return cached is not None
        except MediaError:
            logger.exception("Unable to read DVIDS negative asset cache")
            return False

    def _cacheTtlSeconds(self, path: str) -> int:
        return self.assetCacheTtlSeconds if path == "/asset" else self.cacheTtlSeconds

    async def _fetchAndCache(
        self, cacheKey: str, path: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            data = await self._fetch(path, params)
        except _DvidsAssetUnavailable as error:
            await self._persistNegative(cacheKey, error.statusCode)
            raise
        if self.cacheRepository is not None:
            try:
                await asyncio.to_thread(
                    self.cacheRepository.set, cacheKey, data, self.nowProvider()
                )
            except MediaError:
                logger.exception("Unable to persist DVIDS response")
        return data

    async def _persistNegative(self, cacheKey: str, statusCode: int) -> None:
        if self.negativeCacheRepository is None:
            return
        try:
            await asyncio.to_thread(
                self.negativeCacheRepository.set,
                cacheKey,
                {"statusCode": statusCode},
                self.nowProvider(),
            )
        except MediaError:
            logger.exception("Unable to persist DVIDS negative asset cache")

    def _removeInFlight(
        self, cacheKey: str, completed: asyncio.Task[dict[str, Any]]
    ) -> None:
        if self.inFlightRequests.get(cacheKey) is completed:
            self.inFlightRequests.pop(cacheKey, None)

    async def _fetch(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=self.baseUrl,
            timeout=self.timeoutSeconds,
            transport=self.transport,
        ) as client:
            return await self._sendRequest(client, path, params)

    async def _sendRequest(
        self, client: httpx.AsyncClient, path: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        response: httpx.Response | None = None
        for attempt in range(self.maxAttempts):
            try:
                response = await client.get(path, params=params)
            except (httpx.TimeoutException, httpx.ConnectError) as error:
                if attempt + 1 < self.maxAttempts:
                    await self.sleep(self.retryPolicy.fallbackDelay(attempt))
                    continue
                raise self._requestError(error) from error
            if (
                self.retryPolicy.isRetryableStatus(response.status_code)
                and attempt + 1 < self.maxAttempts
            ):
                delay = self.retryPolicy.delay(response, attempt)
                logger.warning(
                    "DVIDS status %s; retrying attempt %s after %.3f seconds",
                    response.status_code,
                    attempt + 2,
                    delay,
                )
                await self.sleep(delay)
                continue
            break
        if response is None:
            raise MediaError(
                "MEDIA_PROVIDER_REQUEST_FAILED", "The DVIDS request failed."
            )
        if path == "/asset" and response.status_code in (403, 404):
            raise _DvidsAssetUnavailable(response.status_code)
        try:
            response.raise_for_status()
            data: Any = response.json()
        except httpx.HTTPStatusError as error:
            raise self._httpError(error.response.status_code) from error
        except (httpx.RequestError, ValueError) as error:
            logger.exception("DVIDS request failed")
            raise MediaError(
                "MEDIA_PROVIDER_REQUEST_FAILED", "The DVIDS request failed."
            ) from error
        if not isinstance(data, dict) or data.get("errors"):
            raise self._invalidResponse("response")
        return data

    def _requestError(self, error: httpx.RequestError) -> MediaError:
        if isinstance(error, httpx.TimeoutException):
            return MediaError("MEDIA_PROVIDER_TIMEOUT", "DVIDS request timed out.")
        return MediaError(
            "MEDIA_PROVIDER_UNAVAILABLE", "DVIDS is currently unavailable."
        )

    def _source(
        self, asset: dict[str, Any], mediaType: MediaType
    ) -> tuple[str | None, int | None]:
        if mediaType is MediaType.IMAGE:
            return self._string(asset.get("image")), None
        files = asset.get("files")
        if not isinstance(files, list):
            return None, None
        candidates = [
            item
            for item in files
            if isinstance(item, dict) and self._isAllowedRendition(item)
        ]
        candidates.sort(
            key=lambda item: (
                self._integer(item.get("width")) * self._integer(item.get("height")),
                self._integer(item.get("size")),
            ),
            reverse=True,
        )
        for candidate in candidates:
            uri = self._firstString(candidate, "src", "url", "file", "path")
            if uri:
                size = self._integer(candidate.get("size")) or self._integer(
                    candidate.get("filesize")
                )
                return uri, size or None
        return None, None

    def _isAllowedRendition(self, candidate: dict[str, Any]) -> bool:
        mimeType = self._string(candidate.get("type"))
        if mimeType is not None and mimeType.lower() != "video/mp4":
            return False
        heightLimit = DVIDS_VIDEO_HEIGHT_LIMITS[self.videoQuality]
        height = self._integer(candidate.get("height"))
        if heightLimit is not None and (height == 0 or height > heightLimit):
            return False
        if self.maxVideoFileSizeBytes == 0:
            return True
        size = self._integer(candidate.get("size")) or self._integer(
            candidate.get("filesize")
        )
        return 0 < size <= self.maxVideoFileSizeBytes

    def _totalResults(self, data: dict[str, Any]) -> int:
        pageInfo = data.get("page_info")
        return (
            self._integer(pageInfo.get("total_results"))
            if isinstance(pageInfo, dict)
            else 0
        )

    def _timestamp(self, value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _score(self, value: Any) -> float:
        return float(value) / 5 if isinstance(value, (int, float)) else 1.0

    def _httpError(self, statusCode: int) -> MediaError:
        if statusCode == 403:
            return MediaError(
                "MEDIA_PROVIDER_AUTHENTICATION_FAILED",
                "DVIDS authentication failed or the asset is unavailable.",
            )
        if statusCode == 429:
            return MediaError(
                "MEDIA_PROVIDER_RATE_LIMITED", "DVIDS rate limit was exceeded."
            )
        if statusCode >= 500:
            return MediaError(
                "MEDIA_PROVIDER_UNAVAILABLE", "DVIDS is currently unavailable."
            )
        return MediaError(
            "MEDIA_PROVIDER_REQUEST_REJECTED",
            f"DVIDS rejected the request with status {statusCode}.",
        )

    def _invalidResponse(self, section: str) -> MediaError:
        return MediaError(
            "INVALID_MEDIA_PROVIDER_RESPONSE",
            f"DVIDS returned invalid {section}.",
        )

    def _firstString(self, data: dict[str, Any], *keys: str) -> str | None:
        return next(
            (value for key in keys if (value := self._string(data.get(key)))), None
        )

    def _integer(self, value: Any) -> int:
        return value if isinstance(value, int) and value >= 0 else 0

    def _string(self, value: Any) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None
