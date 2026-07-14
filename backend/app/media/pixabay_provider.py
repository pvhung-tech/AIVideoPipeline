import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from functools import partial
from typing import Any
from urllib.parse import quote

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
from app.repositories.pixabay_search_cache_repository import (
    PixabaySearchCacheRepository,
)

logger = logging.getLogger(__name__)
SEARCH_CACHE_TTL_SECONDS = 24 * 60 * 60


class PixabayProvider:
    providerId = "pixabay"

    def __init__(
        self,
        apiKey: str | None,
        baseUrl: str,
        timeoutSeconds: float,
        cacheRepository: PixabaySearchCacheRepository,
        maxAttempts: int = 3,
        initialDelaySeconds: float = 1,
        maxDelaySeconds: float = 60,
        jitterRatio: float = 0.25,
        cacheTtlSeconds: int = SEARCH_CACHE_TTL_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        nowProvider: Callable[[], datetime] | None = None,
        randomProvider: Callable[[], float] | None = None,
    ) -> None:
        if (
            maxAttempts < 1
            or initialDelaySeconds < 0
            or maxDelaySeconds < initialDelaySeconds
            or jitterRatio < 0
            or jitterRatio > 1
            or cacheTtlSeconds < 1
        ):
            raise ValueError("Pixabay retry and cache settings are invalid.")
        self.apiKey = apiKey.strip() if apiKey else None
        self.baseUrl = baseUrl.rstrip("/")
        self.timeoutSeconds = timeoutSeconds
        self.cacheRepository = cacheRepository
        self.maxAttempts = maxAttempts
        self.initialDelaySeconds = initialDelaySeconds
        self.maxDelaySeconds = maxDelaySeconds
        self.jitterRatio = jitterRatio
        self.cacheTtlSeconds = cacheTtlSeconds
        self.transport = transport
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
        self.inFlightRequests: dict[str, asyncio.Task[dict[str, Any]]] = {}

    async def search(self, query: MediaSearchQuery) -> MediaSearchPage:
        if self.apiKey is None:
            raise MediaError(
                "MEDIA_PROVIDER_NOT_CONFIGURED",
                "Pixabay is not configured. Set PIXABAY_API_KEY.",
            )
        if len(query.text) > 100:
            raise MediaError(
                "INVALID_MEDIA_QUERY",
                "Pixabay search queries cannot exceed 100 characters.",
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
        pageSize = min(200, max(count, 3))
        page = (offset // pageSize) + 1
        pageOffset = offset % pageSize
        collected: list[MediaSearchItem] = []
        totalResults = 0
        while len(collected) < count:
            data = await self._request(text, mediaType, page, pageSize)
            totalResults = self._integer(data.get("totalHits"))
            rawItems = data.get("hits")
            if not isinstance(rawItems, list):
                raise MediaError(
                    "INVALID_MEDIA_PROVIDER_RESPONSE",
                    "Pixabay returned an invalid result collection.",
                )
            parsed = [self._parseItem(item, mediaType) for item in rawItems]
            validItems = [item for item in parsed if item is not None]
            collected.extend(validItems[pageOffset:])
            if len(rawItems) < pageSize or not rawItems:
                break
            page += 1
            pageOffset = 0
        return totalResults, collected[:count]

    async def _request(
        self,
        text: str,
        mediaType: MediaType,
        page: int,
        pageSize: int,
    ) -> dict[str, Any]:
        path = "/api/" if mediaType is MediaType.IMAGE else "/api/videos/"
        cacheKey = self.cacheRepository.makeKey(
            f"{self.baseUrl}{path}", text, page, pageSize
        )
        now = self.nowProvider()
        if not self.cachePruned:
            await asyncio.to_thread(
                self.cacheRepository.pruneExpired, now, self.cacheTtlSeconds
            )
            self.cachePruned = True
        try:
            cached = await asyncio.to_thread(
                self.cacheRepository.get, cacheKey, now, self.cacheTtlSeconds
            )
            if cached is not None:
                return cached
        except MediaError:
            logger.exception("Unable to read persistent Pixabay search cache")
        task = self.inFlightRequests.get(cacheKey)
        if task is None:
            task = asyncio.create_task(
                self._fetchAndCache(cacheKey, path, text, page, pageSize)
            )
            self.inFlightRequests[cacheKey] = task
            task.add_done_callback(partial(self._removeInFlight, cacheKey))
        return await asyncio.shield(task)

    async def _fetchAndCache(
        self,
        cacheKey: str,
        path: str,
        text: str,
        page: int,
        pageSize: int,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=self.baseUrl,
            timeout=self.timeoutSeconds,
            transport=self.transport,
        ) as client:
            data = await self._sendRequest(client, path, text, page, pageSize)
        try:
            await asyncio.to_thread(
                self.cacheRepository.set, cacheKey, data, self.nowProvider()
            )
        except MediaError:
            logger.exception("Unable to persist Pixabay search response")
        return data

    def _removeInFlight(
        self, cacheKey: str, completed: asyncio.Task[dict[str, Any]]
    ) -> None:
        if self.inFlightRequests.get(cacheKey) is completed:
            self.inFlightRequests.pop(cacheKey, None)

    async def _sendRequest(
        self,
        client: httpx.AsyncClient,
        path: str,
        text: str,
        page: int,
        pageSize: int,
    ) -> dict[str, Any]:
        response: httpx.Response | None = None
        for attempt in range(self.maxAttempts):
            try:
                response = await client.get(
                    path,
                    params={
                        "key": self.apiKey or "",
                        "q": text,
                        "page": page,
                        "per_page": pageSize,
                        "safesearch": "true",
                    },
                )
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
                    "Pixabay request status %s; retrying attempt %s after %.3f seconds",
                    response.status_code,
                    attempt + 2,
                    delay,
                )
                await self.sleep(delay)
                continue
            break
        if response is None:
            raise MediaError(
                "MEDIA_PROVIDER_REQUEST_FAILED", "The Pixabay request failed."
            )
        try:
            response.raise_for_status()
            data: Any = response.json()
        except httpx.HTTPStatusError as error:
            raise self._httpError(error.response.status_code) from error
        except (httpx.RequestError, ValueError) as error:
            logger.exception("Pixabay response processing failed")
            raise MediaError(
                "MEDIA_PROVIDER_REQUEST_FAILED", "The Pixabay request failed."
            ) from error
        if not isinstance(data, dict):
            raise MediaError(
                "INVALID_MEDIA_PROVIDER_RESPONSE",
                "Pixabay returned an invalid response.",
            )
        return data

    def _requestError(self, error: httpx.RequestError) -> MediaError:
        if isinstance(error, httpx.TimeoutException):
            return MediaError("MEDIA_PROVIDER_TIMEOUT", "Pixabay request timed out.")
        return MediaError(
            "MEDIA_PROVIDER_UNAVAILABLE", "Pixabay is currently unavailable."
        )

    def _parseItem(self, data: Any, mediaType: MediaType) -> MediaSearchItem | None:
        if not isinstance(data, dict) or not isinstance(data.get("id"), int):
            return None
        if mediaType is MediaType.IMAGE:
            return self._parseImage(data)
        return self._parseVideo(data)

    def _parseImage(self, data: dict[str, Any]) -> MediaSearchItem | None:
        sourceUri = self._firstString(
            data, "imageURL", "fullHDURL", "largeImageURL", "webformatURL"
        )
        if sourceUri is None:
            return None
        creator = self._string(data.get("user")) or "Pixabay contributor"
        originalUri = self._string(data.get("imageURL"))
        return self._item(
            data,
            MediaType.IMAGE,
            sourceUri,
            self._string(data.get("previewURL")),
            (
                self._integer(data.get("imageSize")) or None
                if sourceUri == originalUri
                else None
            ),
            creator,
        )

    def _parseVideo(self, data: dict[str, Any]) -> MediaSearchItem | None:
        videos = data.get("videos")
        if not isinstance(videos, dict):
            return None
        candidates = [value for value in videos.values() if isinstance(value, dict)]
        candidates.sort(
            key=lambda item: (
                self._integer(item.get("width")) * self._integer(item.get("height")),
                self._integer(item.get("size")),
            ),
            reverse=True,
        )
        selected = next(
            (item for item in candidates if self._string(item.get("url"))), None
        )
        if selected is None:
            return None
        creator = self._string(data.get("user")) or "Pixabay contributor"
        return self._item(
            data,
            MediaType.VIDEO,
            self._string(selected.get("url")) or "",
            self._string(selected.get("thumbnail")),
            self._integer(selected.get("size")) or None,
            creator,
        )

    def _item(
        self,
        data: dict[str, Any],
        mediaType: MediaType,
        sourceUri: str,
        previewUri: str | None,
        fileSizeBytes: int | None,
        creator: str,
    ) -> MediaSearchItem:
        return MediaSearchItem(
            id=f"pixabay-{mediaType.value}-{data['id']}",
            providerId=self.providerId,
            mediaType=mediaType,
            title=self._title(data, f"Pixabay {mediaType.value}"),
            sourceUri=sourceUri,
            previewUri=previewUri,
            fileSizeBytes=fileSizeBytes,
            modifiedAt=None,
            score=1.0,
            license="Pixabay Content License",
            sourcePageUri=self._string(data.get("pageURL")),
            creator=creator,
            creatorUri=self._creatorUri(creator, data.get("user_id")),
        )

    def _title(self, data: dict[str, Any], fallback: str) -> str:
        tags = self._string(data.get("tags"))
        return tags.replace(",", " -").strip() if tags else fallback

    def _creatorUri(self, creator: str, userId: Any) -> str | None:
        if not isinstance(userId, int) or userId < 0:
            return None
        return f"https://pixabay.com/users/{quote(creator, safe='')}-{userId}/"

    def _firstString(self, data: dict[str, Any], *keys: str) -> str | None:
        return next(
            (value for key in keys if (value := self._string(data.get(key)))), None
        )

    def _httpError(self, statusCode: int) -> MediaError:
        if statusCode in (400, 401, 403):
            return MediaError(
                "MEDIA_PROVIDER_AUTHENTICATION_FAILED",
                "Pixabay authentication failed.",
            )
        if statusCode == 429:
            return MediaError(
                "MEDIA_PROVIDER_RATE_LIMITED", "Pixabay rate limit was exceeded."
            )
        if statusCode >= 500:
            return MediaError(
                "MEDIA_PROVIDER_UNAVAILABLE", "Pixabay is currently unavailable."
            )
        return MediaError(
            "MEDIA_PROVIDER_REQUEST_REJECTED",
            f"Pixabay rejected the request with status {statusCode}.",
        )

    def _integer(self, value: Any) -> int:
        return value if isinstance(value, int) and value >= 0 else 0

    def _string(self, value: Any) -> str | None:
        return value if isinstance(value, str) and value.strip() else None
