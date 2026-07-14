import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.media.errors import MediaError
from app.media.models import MediaSearchQuery, MediaType
from app.media.wikimedia_commons_provider import WikimediaCommonsProvider
from app.repositories.wikimedia_search_cache_repository import (
    WikimediaSearchCacheRepository,
)

EMPTY_RESPONSE: dict[str, Any] = {"query": {"pages": []}}


def testWikimediaProviderNormalizesImageAndVideoMetadata() -> None:
    def handleRequest(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/w/api.php"
        assert request.headers["User-Agent"] == "Studio/1.0 (test@example.com)"
        assert request.url.params["gsrnamespace"] == "6"
        assert request.url.params["iiurlwidth"] == "640"
        return httpx.Response(
            200,
            json={
                "query": {
                    "searchinfo": {"totalhits": 12},
                    "pages": [
                        {
                            "pageid": 10,
                            "title": "File:City skyline.jpg",
                            "imageinfo": [
                                {
                                    "url": "https://upload.wikimedia.org/city.jpg",
                                    "thumburl": "https://upload.wikimedia.org/thumb.jpg",
                                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:City.jpg",
                                    "size": 1234,
                                    "mime": "image/jpeg",
                                    "mediatype": "BITMAP",
                                    "timestamp": "2026-01-02T03:04:05Z",
                                    "extmetadata": {
                                        "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                        "Artist": {
                                            "value": (
                                                '<a href="//commons.wikimedia.org/'
                                                'wiki/User:Alex"><b>Alex</b></a>'
                                            )
                                        },
                                    },
                                }
                            ],
                        },
                        {
                            "pageid": 20,
                            "title": "File:City.webm",
                            "imageinfo": [
                                {
                                    "url": "https://upload.wikimedia.org/city.webm",
                                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:City.webm",
                                    "size": 4321,
                                    "mime": "video/webm",
                                    "mediatype": "VIDEO",
                                    "extmetadata": {
                                        "UsageTerms": {"value": "Public domain"},
                                        "Credit": {"value": "City archive"},
                                    },
                                }
                            ],
                        },
                    ],
                }
            },
        )

    provider = WikimediaCommonsProvider(
        "https://commons.wikimedia.org",
        "Studio/1.0 (test@example.com)",
        5,
        httpx.MockTransport(handleRequest),
    )

    page = asyncio.run(
        provider.search(MediaSearchQuery("city", tuple(MediaType), 2, 0))
    )

    assert page.totalResults == 12
    assert [item.id for item in page.items] == [
        "wikimedia-file-10",
        "wikimedia-file-20",
    ]
    assert page.items[0].title == "City skyline.jpg"
    assert page.items[0].creator == "Alex"
    assert page.items[0].creatorUri == "https://commons.wikimedia.org/wiki/User:Alex"
    assert page.items[0].license == "CC BY-SA 4.0"
    assert page.items[1].mediaType is MediaType.VIDEO
    assert page.items[1].creator == "City archive"
    assert page.items[1].previewUri == page.items[1].sourceUri


def testWikimediaProviderContinuesUntilRequestedMediaTypeIsFound() -> None:
    offsets: list[int] = []

    def handleRequest(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["gsroffset"])
        offsets.append(offset)
        if offset == 0:
            return httpx.Response(
                200,
                json={
                    "continue": {"gsroffset": 50, "continue": "||"},
                    "query": {
                        "pages": [
                            {
                                "pageid": 1,
                                "title": "File:Audio.ogg",
                                "imageinfo": [
                                    {
                                        "url": "https://upload.wikimedia.org/audio.ogg",
                                        "mime": "audio/ogg",
                                        "mediatype": "AUDIO",
                                    }
                                ],
                            }
                        ]
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "query": {
                    "pages": [
                        {
                            "pageid": 2,
                            "title": "File:Image.png",
                            "imageinfo": [
                                {
                                    "url": "https://upload.wikimedia.org/image.png",
                                    "mime": "image/png",
                                    "mediatype": "BITMAP",
                                }
                            ],
                        }
                    ]
                }
            },
        )

    provider = WikimediaCommonsProvider(
        "https://commons.wikimedia.org",
        "Studio/1.0",
        5,
        httpx.MockTransport(handleRequest),
    )

    page = asyncio.run(
        provider.search(MediaSearchQuery("city", (MediaType.IMAGE,), 1, 0))
    )

    assert offsets == [0, 50]
    assert page.items[0].id == "wikimedia-file-2"
    assert page.truncated is False


def testWikimediaProviderMapsRateLimit() -> None:
    provider = WikimediaCommonsProvider(
        "https://commons.wikimedia.org",
        "Studio/1.0",
        5,
        httpx.MockTransport(lambda _request: httpx.Response(429)),
    )

    with pytest.raises(MediaError) as error:
        asyncio.run(provider.search(MediaSearchQuery("city", (MediaType.IMAGE,), 1, 0)))

    assert error.value.code == "MEDIA_PROVIDER_RATE_LIMITED"


def testWikimediaProviderRequiresIdentifyingUserAgent() -> None:
    provider = WikimediaCommonsProvider("https://commons.wikimedia.org", None, 5)

    with pytest.raises(MediaError, match="WIKIMEDIA_USER_AGENT") as error:
        asyncio.run(provider.search(MediaSearchQuery("city", (MediaType.IMAGE,), 1, 0)))

    assert error.value.code == "MEDIA_PROVIDER_NOT_CONFIGURED"


def testWikimediaRetriesAndPersistsSuccessfulResponse(tmp_path: Path) -> None:
    attempts = 0
    delays: list[float] = []

    def handleRequest(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json=EMPTY_RESPONSE)

    async def recordSleep(delay: float) -> None:
        delays.append(delay)

    cache = WikimediaSearchCacheRepository(tmp_path)
    provider = WikimediaCommonsProvider(
        "https://commons.wikimedia.org",
        "Studio/1.0 (test@example.com)",
        5,
        httpx.MockTransport(handleRequest),
        cache,
        sleep=recordSleep,
    )
    query = MediaSearchQuery("city", (MediaType.IMAGE,), 1, 0)

    firstPage = asyncio.run(provider.search(query))
    restarted = WikimediaCommonsProvider(
        "https://commons.wikimedia.org",
        "Studio/1.0 (test@example.com)",
        5,
        httpx.MockTransport(lambda _request: pytest.fail("cache miss")),
        WikimediaSearchCacheRepository(tmp_path),
    )
    secondPage = asyncio.run(restarted.search(query))

    assert attempts == 2
    assert delays == [2.0]
    assert secondPage == firstPage


def testWikimediaUsesJitteredExponentialFallback(tmp_path: Path) -> None:
    attempts = 0
    delays: list[float] = []

    def handleRequest(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return (
            httpx.Response(503)
            if attempts == 1
            else httpx.Response(200, json=EMPTY_RESPONSE)
        )

    async def recordSleep(delay: float) -> None:
        delays.append(delay)

    provider = WikimediaCommonsProvider(
        "https://commons.wikimedia.org",
        "Studio/1.0 (test@example.com)",
        5,
        httpx.MockTransport(handleRequest),
        WikimediaSearchCacheRepository(tmp_path),
        initialDelaySeconds=1.5,
        jitterRatio=0.2,
        sleep=recordSleep,
        randomProvider=lambda: 0.5,
    )

    asyncio.run(provider.search(MediaSearchQuery("city", (MediaType.IMAGE,), 1, 0)))

    assert attempts == 2
    assert delays == pytest.approx([1.65])


def testWikimediaCoalescesConcurrentIdenticalRequests(tmp_path: Path) -> None:
    requests = 0

    async def handleRequest(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        await asyncio.sleep(0.02)
        return httpx.Response(200, json=EMPTY_RESPONSE)

    provider = WikimediaCommonsProvider(
        "https://commons.wikimedia.org",
        "Studio/1.0 (test@example.com)",
        5,
        httpx.MockTransport(handleRequest),
        WikimediaSearchCacheRepository(tmp_path),
    )
    query = MediaSearchQuery("city", (MediaType.IMAGE,), 1, 0)

    async def searchConcurrently() -> list[object]:
        return await asyncio.gather(*(provider.search(query) for _ in range(8)))

    pages = asyncio.run(searchConcurrently())

    assert requests == 1
    assert len(pages) == 8
    assert all(page == pages[0] for page in pages)
    assert provider.inFlightRequests == {}
