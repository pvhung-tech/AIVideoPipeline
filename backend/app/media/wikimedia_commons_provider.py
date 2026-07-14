import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from functools import partial
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

import httpx

from app.media.errors import MediaError
from app.media.http_retry_policy import HttpRetryPolicy
from app.media.models import (
    MediaSearchItem,
    MediaSearchPage,
    MediaSearchQuery,
    MediaType,
)
from app.repositories.wikimedia_search_cache_repository import (
    WikimediaSearchCacheRepository,
)

logger = logging.getLogger(__name__)
SEARCH_BATCH_SIZE = 50
MAX_SEARCH_BATCHES = 10
SEARCH_CACHE_TTL_SECONDS = 24 * 60 * 60


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.firstLink: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a" and self.firstLink is None:
            self.firstLink = next(
                (value for name, value in attrs if name == "href" and value), None
            )

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    @property
    def text(self) -> str:
        return " ".join("".join(self.parts).split())


class WikimediaCommonsProvider:
    providerId = "wikimedia"

    def __init__(
        self,
        baseUrl: str,
        userAgent: str | None,
        timeoutSeconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
        cacheRepository: WikimediaSearchCacheRepository | None = None,
        maxAttempts: int = 3,
        initialDelaySeconds: float = 1,
        maxDelaySeconds: float = 60,
        jitterRatio: float = 0.25,
        cacheTtlSeconds: int = SEARCH_CACHE_TTL_SECONDS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        nowProvider: Callable[[], datetime] | None = None,
        randomProvider: Callable[[], float] = random.random,
    ) -> None:
        if maxAttempts < 1 or cacheTtlSeconds < 1:
            raise ValueError("Wikimedia retry and cache settings are invalid.")
        self.baseUrl = baseUrl.rstrip("/")
        self.userAgent = userAgent.strip() if userAgent else None
        self.timeoutSeconds = timeoutSeconds
        self.transport = transport
        self.cacheRepository = cacheRepository
        self.maxAttempts = maxAttempts
        self.cacheTtlSeconds = cacheTtlSeconds
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
        if self.userAgent is None:
            raise MediaError(
                "MEDIA_PROVIDER_NOT_CONFIGURED",
                "Wikimedia Commons is not configured. Set WIKIMEDIA_USER_AGENT "
                "with contact information.",
            )
        required = query.offset + query.limit
        collected: list[MediaSearchItem] = []
        continuation: int | None = 0
        totalResults = 0
        batches = 0
        while continuation is not None and len(collected) < required:
            data = await self._request(query.text, continuation)
            batches += 1
            queryData = data.get("query")
            if not isinstance(queryData, dict):
                raise self._invalidResponse()
            searchInfo = queryData.get("searchinfo")
            if isinstance(searchInfo, dict):
                totalResults = self._integer(searchInfo.get("totalhits"))
            pages = queryData.get("pages")
            if not isinstance(pages, list):
                raise self._invalidResponse()
            for page in pages:
                item = self._parseItem(page, len(collected))
                if item is not None and item.mediaType in query.mediaTypes:
                    collected.append(item)
            continuation = self._continuation(data)
            if batches >= MAX_SEARCH_BATCHES:
                break
        return MediaSearchPage(
            providerId=self.providerId,
            query=query.text,
            totalResults=max(totalResults, len(collected)),
            offset=query.offset,
            limit=query.limit,
            truncated=continuation is not None,
            items=tuple(collected[query.offset : required]),
        )

    async def _request(self, text: str, offset: int) -> dict[str, Any]:
        if self.cacheRepository is None:
            return await self._fetch(text, offset)
        cacheKey = self.cacheRepository.makeKey(
            f"{self.baseUrl}/w/api.php", text, offset, SEARCH_BATCH_SIZE
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
            logger.exception("Unable to read persistent Wikimedia search cache")
        task = self.inFlightRequests.get(cacheKey)
        if task is None:
            task = asyncio.create_task(self._fetchAndCache(cacheKey, text, offset))
            self.inFlightRequests[cacheKey] = task
            task.add_done_callback(partial(self._removeInFlight, cacheKey))
        return await asyncio.shield(task)

    async def _fetchAndCache(
        self, cacheKey: str, text: str, offset: int
    ) -> dict[str, Any]:
        data = await self._fetch(text, offset)
        if self.cacheRepository is not None:
            try:
                await asyncio.to_thread(
                    self.cacheRepository.set, cacheKey, data, self.nowProvider()
                )
            except MediaError:
                logger.exception("Unable to persist Wikimedia search response")
        return data

    def _removeInFlight(
        self, cacheKey: str, completed: asyncio.Task[dict[str, Any]]
    ) -> None:
        if self.inFlightRequests.get(cacheKey) is completed:
            self.inFlightRequests.pop(cacheKey, None)

    async def _fetch(self, text: str, offset: int) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=self.baseUrl,
            timeout=self.timeoutSeconds,
            transport=self.transport,
            headers={"User-Agent": self.userAgent or ""},
        ) as client:
            return await self._sendRequest(client, text, offset)

    async def _sendRequest(
        self, client: httpx.AsyncClient, text: str, offset: int
    ) -> dict[str, Any]:
        response: httpx.Response | None = None
        for attempt in range(self.maxAttempts):
            try:
                response = await client.get(
                    "/w/api.php", params=self._requestParameters(text, offset)
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
                    "Wikimedia status %s; retrying attempt %s after %.3f seconds",
                    response.status_code,
                    attempt + 2,
                    delay,
                )
                await self.sleep(delay)
                continue
            break
        if response is None:
            raise MediaError(
                "MEDIA_PROVIDER_REQUEST_FAILED",
                "The Wikimedia Commons request failed.",
            )
        try:
            response.raise_for_status()
            data: Any = response.json()
        except httpx.HTTPStatusError as error:
            raise self._httpError(error.response.status_code) from error
        except (httpx.RequestError, ValueError) as error:
            logger.exception("Wikimedia Commons response processing failed")
            raise MediaError(
                "MEDIA_PROVIDER_REQUEST_FAILED",
                "The Wikimedia Commons request failed.",
            ) from error
        if not isinstance(data, dict) or "error" in data:
            raise self._invalidResponse()
        return data

    def _requestParameters(self, text: str, offset: int) -> dict[str, Any]:
        return {
            "action": "query",
            "generator": "search",
            "gsrsearch": text,
            "gsrnamespace": 6,
            "gsrlimit": SEARCH_BATCH_SIZE,
            "gsroffset": offset,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|mediatype|timestamp|extmetadata",
            "iiurlwidth": 640,
            "iiextmetadatafilter": (
                "LicenseShortName|UsageTerms|Artist|Credit|ImageDescription"
            ),
            "format": "json",
            "formatversion": 2,
        }

    def _requestError(self, error: httpx.RequestError) -> MediaError:
        if isinstance(error, httpx.TimeoutException):
            return MediaError(
                "MEDIA_PROVIDER_TIMEOUT", "Wikimedia Commons request timed out."
            )
        return MediaError(
            "MEDIA_PROVIDER_UNAVAILABLE",
            "Wikimedia Commons is currently unavailable.",
        )

    def _parseItem(self, page: Any, rank: int) -> MediaSearchItem | None:
        if not isinstance(page, dict) or not isinstance(page.get("pageid"), int):
            return None
        imageInfoList = page.get("imageinfo")
        if not isinstance(imageInfoList, list) or not imageInfoList:
            return None
        imageInfo = imageInfoList[0]
        if not isinstance(imageInfo, dict):
            return None
        sourceUri = self._string(imageInfo.get("url"))
        mediaType = self._mediaType(imageInfo)
        if sourceUri is None or mediaType is None:
            return None
        metadata = imageInfo.get("extmetadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        creatorParser = self._metadataParser(metadata.get("Artist"))
        creator = creatorParser.text if creatorParser and creatorParser.text else None
        title = self._string(page.get("title")) or f"Wikimedia file {page['pageid']}"
        if title.startswith("File:"):
            title = title[5:]
        return MediaSearchItem(
            id=f"wikimedia-file-{page['pageid']}",
            providerId=self.providerId,
            mediaType=mediaType,
            title=title,
            sourceUri=sourceUri,
            previewUri=self._string(imageInfo.get("thumburl")) or sourceUri,
            fileSizeBytes=self._integer(imageInfo.get("size")) or None,
            modifiedAt=self._timestamp(imageInfo.get("timestamp")),
            score=1.0 / (rank + 1),
            license=(
                self._metadataText(metadata.get("LicenseShortName"))
                or self._metadataText(metadata.get("UsageTerms"))
            ),
            sourcePageUri=self._string(imageInfo.get("descriptionurl")),
            creator=creator or self._metadataText(metadata.get("Credit")),
            creatorUri=(
                urljoin(f"{self.baseUrl}/", creatorParser.firstLink)
                if creatorParser and creatorParser.firstLink
                else None
            ),
        )

    def _mediaType(self, imageInfo: dict[str, Any]) -> MediaType | None:
        mime = (self._string(imageInfo.get("mime")) or "").lower()
        mediaType = (self._string(imageInfo.get("mediatype")) or "").upper()
        if mime.startswith("image/") or mediaType in {"BITMAP", "DRAWING"}:
            return MediaType.IMAGE
        if mime.startswith("video/") or mediaType == "VIDEO":
            return MediaType.VIDEO
        return None

    def _metadataParser(self, value: Any) -> _MetadataParser | None:
        raw = value.get("value") if isinstance(value, dict) else None
        if not isinstance(raw, str) or not raw.strip():
            return None
        parser = _MetadataParser()
        parser.feed(raw)
        parser.close()
        return parser

    def _metadataText(self, value: Any) -> str | None:
        parser = self._metadataParser(value)
        return parser.text if parser and parser.text else None

    def _continuation(self, data: dict[str, Any]) -> int | None:
        continuation = data.get("continue")
        if not isinstance(continuation, dict):
            return None
        return self._integerOrNone(continuation.get("gsroffset"))

    def _timestamp(self, value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _httpError(self, statusCode: int) -> MediaError:
        if statusCode == 429:
            return MediaError(
                "MEDIA_PROVIDER_RATE_LIMITED",
                "Wikimedia Commons rate limit was exceeded.",
            )
        if statusCode >= 500:
            return MediaError(
                "MEDIA_PROVIDER_UNAVAILABLE",
                "Wikimedia Commons is currently unavailable.",
            )
        return MediaError(
            "MEDIA_PROVIDER_REQUEST_REJECTED",
            f"Wikimedia Commons rejected the request with status {statusCode}.",
        )

    def _invalidResponse(self) -> MediaError:
        return MediaError(
            "INVALID_MEDIA_PROVIDER_RESPONSE",
            "Wikimedia Commons returned an invalid response.",
        )

    def _integer(self, value: Any) -> int:
        return value if isinstance(value, int) and value >= 0 else 0

    def _integerOrNone(self, value: Any) -> int | None:
        return value if isinstance(value, int) and value >= 0 else None

    def _string(self, value: Any) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None
