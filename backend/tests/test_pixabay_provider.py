import asyncio
from contextlib import suppress
from pathlib import Path

import httpx
import pytest

from app.media.errors import MediaError
from app.media.models import MediaSearchPage, MediaSearchQuery, MediaType
from app.media.pixabay_provider import PixabayProvider
from app.repositories.pixabay_search_cache_repository import (
    PixabaySearchCacheRepository,
)


def testPixabayProviderSearchesAndPersistsResponsesAcrossInstances(
    tmp_path: Path,
) -> None:
    requests: list[str] = []

    def handleRequest(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        assert request.url.params["key"] == "secret"
        assert request.url.params["safesearch"] == "true"
        if request.url.path == "/api/":
            return httpx.Response(
                200,
                json={
                    "totalHits": 20,
                    "hits": [
                        {
                            "id": 10,
                            "pageURL": "https://pixabay.com/photos/city-10/",
                            "tags": "city, skyline",
                            "largeImageURL": "https://cdn.pixabay.com/photo/10.jpg",
                            "previewURL": "https://cdn.pixabay.com/photo/10_small.jpg",
                            "user": "Alex Doe",
                            "user_id": 7,
                        }
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "totalHits": 8,
                "hits": [
                    {
                        "id": 20,
                        "pageURL": "https://pixabay.com/videos/city-20/",
                        "tags": "city, night",
                        "user": "Sam",
                        "user_id": 8,
                        "videos": {
                            "medium": {
                                "url": "https://cdn.pixabay.com/video/20.mp4",
                                "width": 1920,
                                "height": 1080,
                                "size": 400,
                                "thumbnail": "https://cdn.pixabay.com/video/20.jpg",
                            }
                        },
                    }
                ],
            },
        )

    provider = PixabayProvider(
        "secret",
        "https://pixabay.com",
        5,
        PixabaySearchCacheRepository(tmp_path / "search-cache"),
        transport=httpx.MockTransport(handleRequest),
    )
    query = MediaSearchQuery("city", tuple(MediaType), 2, 0)

    firstPage = asyncio.run(provider.search(query))
    restartedProvider = PixabayProvider(
        "secret",
        "https://pixabay.com",
        5,
        PixabaySearchCacheRepository(tmp_path / "search-cache"),
        transport=httpx.MockTransport(
            lambda _request: (_ for _ in ()).throw(AssertionError("network called"))
        ),
    )
    secondPage = asyncio.run(restartedProvider.search(query))

    assert sorted(requests) == ["/api/", "/api/videos/"]
    assert firstPage == secondPage
    assert firstPage.totalResults == 28
    assert [item.id for item in firstPage.items] == [
        "pixabay-image-10",
        "pixabay-video-20",
    ]
    assert firstPage.items[0].creatorUri == ("https://pixabay.com/users/Alex%20Doe-7/")
    assert firstPage.items[1].fileSizeBytes == 400


def testPixabayProviderRequiresApiKey(tmp_path: Path) -> None:
    provider = PixabayProvider(
        None,
        "https://pixabay.com",
        5,
        PixabaySearchCacheRepository(tmp_path),
    )
    query = MediaSearchQuery("city", (MediaType.IMAGE,), 10, 0)

    with pytest.raises(MediaError, match="PIXABAY_API_KEY") as error:
        asyncio.run(provider.search(query))

    assert error.value.code == "MEDIA_PROVIDER_NOT_CONFIGURED"


def testPixabayProviderRetriesUsingRetryAfter(tmp_path: Path) -> None:
    attempts = 0
    delays: list[float] = []

    def handleRequest(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"totalHits": 0, "hits": []})

    async def recordSleep(delay: float) -> None:
        delays.append(delay)

    provider = PixabayProvider(
        "secret",
        "https://pixabay.com",
        5,
        PixabaySearchCacheRepository(tmp_path),
        transport=httpx.MockTransport(handleRequest),
        sleep=recordSleep,
    )
    query = MediaSearchQuery("city", (MediaType.IMAGE,), 10, 0)

    page = asyncio.run(provider.search(query))

    assert page.items == ()
    assert attempts == 2
    assert delays == [2.0]


def testPixabayProviderUsesRateLimitResetAndBoundsDelay(tmp_path: Path) -> None:
    attempts = 0
    delays: list[float] = []

    def handleRequest(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"X-RateLimit-Reset": "120"})
        return httpx.Response(200, json={"totalHits": 0, "hits": []})

    async def recordSleep(delay: float) -> None:
        delays.append(delay)

    provider = PixabayProvider(
        "secret",
        "https://pixabay.com",
        5,
        PixabaySearchCacheRepository(tmp_path),
        maxDelaySeconds=30,
        transport=httpx.MockTransport(handleRequest),
        sleep=recordSleep,
    )

    asyncio.run(provider.search(MediaSearchQuery("city", (MediaType.IMAGE,), 3, 0)))

    assert delays == [30]


def testPixabayProviderUsesExponentialFallbackForServerErrors(
    tmp_path: Path,
) -> None:
    attempts = 0
    delays: list[float] = []

    def handleRequest(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"totalHits": 0, "hits": []})

    async def recordSleep(delay: float) -> None:
        delays.append(delay)

    provider = PixabayProvider(
        "secret",
        "https://pixabay.com",
        5,
        PixabaySearchCacheRepository(tmp_path),
        initialDelaySeconds=1.5,
        jitterRatio=0.2,
        transport=httpx.MockTransport(handleRequest),
        sleep=recordSleep,
        randomProvider=lambda: 0.5,
    )

    asyncio.run(provider.search(MediaSearchQuery("city", (MediaType.IMAGE,), 3, 0)))

    assert attempts == 2
    assert delays == pytest.approx([1.65])


def testPixabayProviderCoalescesConcurrentIdenticalRequests(tmp_path: Path) -> None:
    requests = 0

    async def handleRequest(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        await asyncio.sleep(0.02)
        return httpx.Response(
            200,
            json={
                "totalHits": 1,
                "hits": [
                    {
                        "id": 99,
                        "pageURL": "https://pixabay.com/photos/city-99/",
                        "tags": "city",
                        "largeImageURL": "https://cdn.pixabay.com/photo/99.jpg",
                        "user": "Creator",
                        "user_id": 9,
                    }
                ],
            },
        )

    provider = PixabayProvider(
        "secret",
        "https://pixabay.com",
        5,
        PixabaySearchCacheRepository(tmp_path),
        transport=httpx.MockTransport(handleRequest),
    )
    query = MediaSearchQuery("city", (MediaType.IMAGE,), 1, 0)

    async def searchConcurrently() -> list[object]:
        return await asyncio.gather(*(provider.search(query) for _ in range(8)))

    pages = asyncio.run(searchConcurrently())

    assert requests == 1
    assert len(pages) == 8
    assert all(page == pages[0] for page in pages)
    assert provider.inFlightRequests == {}


def testPixabayProviderSearchesMediaTypesConcurrently(tmp_path: Path) -> None:
    activeRequests = 0
    maxActiveRequests = 0

    async def handleRequest(request: httpx.Request) -> httpx.Response:
        nonlocal activeRequests, maxActiveRequests
        activeRequests += 1
        maxActiveRequests = max(maxActiveRequests, activeRequests)
        await asyncio.sleep(0.02)
        activeRequests -= 1
        return httpx.Response(200, json={"totalHits": 1, "hits": []})

    provider = PixabayProvider(
        "secret",
        "https://pixabay.com",
        5,
        PixabaySearchCacheRepository(tmp_path),
        transport=httpx.MockTransport(handleRequest),
    )

    asyncio.run(
        provider.search(
            MediaSearchQuery("city", (MediaType.IMAGE, MediaType.VIDEO), 2, 0)
        )
    )

    assert maxActiveRequests == 2
    assert provider.inFlightRequests == {}


def testPixabayCoalescedRequestSurvivesLeaderCancellation(tmp_path: Path) -> None:
    requests = 0

    async def handleRequest(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        await asyncio.sleep(0.04)
        return httpx.Response(200, json={"totalHits": 0, "hits": []})

    provider = PixabayProvider(
        "secret",
        "https://pixabay.com",
        5,
        PixabaySearchCacheRepository(tmp_path),
        transport=httpx.MockTransport(handleRequest),
    )
    query = MediaSearchQuery("city", (MediaType.IMAGE,), 1, 0)

    async def cancelLeader() -> MediaSearchPage:
        leader = asyncio.create_task(provider.search(query))
        await asyncio.sleep(0.005)
        waiter = asyncio.create_task(provider.search(query))
        leader.cancel()
        with suppress(asyncio.CancelledError):
            await leader
        return await waiter

    page = asyncio.run(cancelLeader())

    assert page.items == ()
    assert requests == 1
    assert provider.inFlightRequests == {}


def testPixabayProviderMapsRateLimitAfterFinalAttempt(tmp_path: Path) -> None:
    provider = PixabayProvider(
        "secret",
        "https://pixabay.com",
        5,
        PixabaySearchCacheRepository(tmp_path),
        maxAttempts=1,
        transport=httpx.MockTransport(lambda _request: httpx.Response(429)),
    )

    with pytest.raises(MediaError) as error:
        asyncio.run(
            provider.search(MediaSearchQuery("city", (MediaType.IMAGE,), 10, 0))
        )

    assert error.value.code == "MEDIA_PROVIDER_RATE_LIMITED"
