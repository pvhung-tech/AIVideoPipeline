import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from app.media.errors import MediaError
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

logger = logging.getLogger(__name__)


class PexelsProvider:
    providerId = "pexels"

    def __init__(
        self,
        apiKey: str | None,
        baseUrl: str,
        timeoutSeconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.apiKey = apiKey.strip() if apiKey else None
        self.baseUrl = baseUrl.rstrip("/")
        self.timeoutSeconds = timeoutSeconds
        self.transport = transport

    async def search(self, query: MediaSearchQuery) -> MediaSearchPage:
        if self.apiKey is None:
            raise MediaError(
                "MEDIA_PROVIDER_NOT_CONFIGURED",
                "Pexels is not configured. Set PEXELS_API_KEY.",
            )
        counts = calculateResultCounts(query)
        offsets = calculateTypeOffsets(query)
        async with httpx.AsyncClient(
            base_url=self.baseUrl,
            timeout=self.timeoutSeconds,
            transport=self.transport,
        ) as client:
            results = await asyncio.gather(
                *(
                    self._searchType(
                        client,
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
        client: httpx.AsyncClient,
        text: str,
        mediaType: MediaType,
        offset: int,
        count: int,
    ) -> tuple[int, list[MediaSearchItem]]:
        if count == 0:
            return 0, []
        pageSize = min(80, max(count, 15))
        page = (offset // pageSize) + 1
        pageOffset = offset % pageSize
        collected: list[MediaSearchItem] = []
        totalResults = 0
        while len(collected) < count:
            data = await self._request(client, text, mediaType, page, pageSize)
            totalResults = self._integer(data.get("total_results"))
            rawItems = data.get("photos" if mediaType is MediaType.IMAGE else "videos")
            if not isinstance(rawItems, list):
                raise MediaError(
                    "INVALID_MEDIA_PROVIDER_RESPONSE",
                    "Pexels returned an invalid result collection.",
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
        client: httpx.AsyncClient,
        text: str,
        mediaType: MediaType,
        page: int,
        pageSize: int,
    ) -> dict[str, Any]:
        path = "/v1/search" if mediaType is MediaType.IMAGE else "/v1/videos/search"
        try:
            response = await client.get(
                path,
                params={"query": text, "page": page, "per_page": pageSize},
                headers={"Authorization": self.apiKey or ""},
            )
            response.raise_for_status()
            data: Any = response.json()
        except httpx.TimeoutException as error:
            raise MediaError(
                "MEDIA_PROVIDER_TIMEOUT", "Pexels request timed out."
            ) from error
        except httpx.ConnectError as error:
            raise MediaError(
                "MEDIA_PROVIDER_UNAVAILABLE", "Pexels is currently unavailable."
            ) from error
        except httpx.HTTPStatusError as error:
            raise self._httpError(error.response.status_code) from error
        except (httpx.RequestError, ValueError) as error:
            logger.exception("Pexels request failed")
            raise MediaError(
                "MEDIA_PROVIDER_REQUEST_FAILED", "The Pexels request failed."
            ) from error
        if not isinstance(data, dict):
            raise MediaError(
                "INVALID_MEDIA_PROVIDER_RESPONSE",
                "Pexels returned an invalid response.",
            )
        return data

    def _parseItem(self, data: Any, mediaType: MediaType) -> MediaSearchItem | None:
        if not isinstance(data, dict) or not isinstance(data.get("id"), int):
            return None
        return (
            self._parsePhoto(data)
            if mediaType is MediaType.IMAGE
            else self._parseVideo(data)
        )

    def _parsePhoto(self, data: dict[str, Any]) -> MediaSearchItem | None:
        source = data.get("src")
        if not isinstance(source, dict):
            return None
        sourceUri = self._string(source.get("original"))
        if sourceUri is None:
            return None
        photographer = self._string(data.get("photographer")) or "Pexels contributor"
        return MediaSearchItem(
            id=f"pexels-photo-{data['id']}",
            providerId=self.providerId,
            mediaType=MediaType.IMAGE,
            title=self._title(data, "Pexels photo"),
            sourceUri=sourceUri,
            previewUri=self._string(source.get("medium")),
            fileSizeBytes=None,
            modifiedAt=None,
            score=1.0,
            license="Pexels License",
            sourcePageUri=self._string(data.get("url")),
            creator=photographer,
            creatorUri=self._string(data.get("photographer_url")),
        )

    def _parseVideo(self, data: dict[str, Any]) -> MediaSearchItem | None:
        videoFiles = data.get("video_files")
        if not isinstance(videoFiles, list):
            return None
        candidates = [item for item in videoFiles if isinstance(item, dict)]
        candidates.sort(
            key=lambda item: (
                self._integer(item.get("width")) * self._integer(item.get("height")),
                self._integer(item.get("file_size")),
            ),
            reverse=True,
        )
        sourceUri = next(
            (
                self._string(item.get("link"))
                for item in candidates
                if self._string(item.get("link"))
            ),
            None,
        )
        if sourceUri is None:
            return None
        pictures = data.get("video_pictures")
        previewUri = None
        if isinstance(pictures, list) and pictures and isinstance(pictures[0], dict):
            previewUri = self._string(pictures[0].get("picture"))
        user = data.get("user")
        creator = self._string(user.get("name")) if isinstance(user, dict) else None
        return MediaSearchItem(
            id=f"pexels-video-{data['id']}",
            providerId=self.providerId,
            mediaType=MediaType.VIDEO,
            title=self._title(data, "Pexels video"),
            sourceUri=sourceUri,
            previewUri=previewUri,
            fileSizeBytes=self._integer(candidates[0].get("file_size")) or None,
            modifiedAt=None,
            score=1.0,
            license="Pexels License",
            sourcePageUri=self._string(data.get("url")),
            creator=creator or "Pexels contributor",
            creatorUri=(
                self._string(user.get("url")) if isinstance(user, dict) else None
            ),
        )

    def _title(self, data: dict[str, Any], fallback: str) -> str:
        alt = self._string(data.get("alt"))
        if alt:
            return alt
        url = self._string(data.get("url"))
        slug = urlparse(url).path.rstrip("/").split("/")[-1] if url else ""
        return slug.replace("-", " ").strip().title() or fallback

    def _httpError(self, statusCode: int) -> MediaError:
        if statusCode in (401, 403):
            return MediaError(
                "MEDIA_PROVIDER_AUTHENTICATION_FAILED", "Pexels authentication failed."
            )
        if statusCode == 429:
            return MediaError(
                "MEDIA_PROVIDER_RATE_LIMITED", "Pexels rate limit was exceeded."
            )
        if statusCode >= 500:
            return MediaError(
                "MEDIA_PROVIDER_UNAVAILABLE", "Pexels is currently unavailable."
            )
        return MediaError(
            "MEDIA_PROVIDER_REQUEST_REJECTED",
            f"Pexels rejected the request with status {statusCode}.",
        )

    def _integer(self, value: Any) -> int:
        return value if isinstance(value, int) and value >= 0 else 0

    def _string(self, value: Any) -> str | None:
        return value if isinstance(value, str) and value.strip() else None
