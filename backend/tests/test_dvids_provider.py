import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from app.media.dvids_provider import DvidsProvider
from app.media.errors import MediaError
from app.media.models import MediaSearchQuery, MediaType
from app.repositories.dvids_search_cache_repository import DvidsSearchCacheRepository


def testDvidsProviderSearchesImageAndVideoSummariesLazily() -> None:
    requests: list[tuple[str, str | None]] = []

    def handleRequest(request: httpx.Request) -> httpx.Response:
        requests.append((request.url.path, request.url.params.get("type")))
        assert request.url.params["api_key"] == "key-secret"
        mediaType = request.url.params["type"]
        assetId = "image:10" if mediaType == "image" else "video:20"
        return httpx.Response(
            200,
            json={
                "page_info": {"total_results": 5, "results_per_page": 10},
                "results": [
                    {
                        "id": assetId,
                        "title": f"DVIDS {mediaType}",
                        "type": mediaType,
                        "thumbnail": "https://d1ldvf68ux039x.cloudfront.net/thumb.jpg",
                        "url": f"https://www.dvidshub.net/{mediaType}/1",
                        "rating": 4,
                        "timestamp": "2026-01-02T03:04:05Z",
                        "credit": "Courtesy media",
                    }
                ],
            },
        )

    provider = DvidsProvider(
        "key-secret",
        "https://api.dvidshub.net",
        5,
        httpx.MockTransport(handleRequest),
    )

    page = asyncio.run(
        provider.search(MediaSearchQuery("operations", tuple(MediaType), 2, 0))
    )

    assert sorted(requests) == [("/search", "image"), ("/search", "video")]
    assert page.totalResults == 10
    assert [item.id for item in page.items] == [
        "dvids-image-10",
        "dvids-video-20",
    ]
    assert page.items[0].sourceUri == "dvids://asset/image%3A10?type=image"
    assert page.items[0].previewUri == "https://d1ldvf68ux039x.cloudfront.net/thumb.jpg"
    assert page.items[0].sourcePageUri == "https://www.dvidshub.net/image/1"
    assert page.items[0].creator == "Courtesy media"
    assert page.items[0].fileSizeBytes is None
    assert page.items[0].license == "Public Domain unless otherwise specified"


def testDvidsResolvesLazyAssetSourceWhenSelected() -> None:
    requests: list[str] = []

    def handleRequest(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        assert request.url.params["api_key"] == "key-secret"
        return httpx.Response(
            200,
            json={
                "results": {
                    "id": request.url.params["id"],
                    "title": "Flight operations",
                    "files": [
                        {
                            "src": "https://d34w7g4gy10iej.cloudfront.net/video/20.mp4",
                            "type": "video/mp4",
                            "width": 1920,
                            "height": 1080,
                            "size": 4000,
                        }
                    ],
                    "thumbnail": {
                        "url": "https://d1ldvf68ux039x.cloudfront.net/20.jpg",
                        "width": 122,
                        "height": 92,
                    },
                    "url": "https://www.dvidshub.net/video/20/flight-operations",
                    "credit": "Courtesy video",
                }
            },
        )

    provider = DvidsProvider(
        "key-secret",
        "https://api.dvidshub.net",
        5,
        httpx.MockTransport(handleRequest),
    )

    sourceUri = asyncio.run(
        provider.resolveAssetSource("dvids://asset/video%3A20?type=video")
    )

    assert requests == ["/asset"]
    assert sourceUri == "https://d34w7g4gy10iej.cloudfront.net/video/20.mp4"


def testDvidsProviderRequiresApiKey() -> None:
    provider = DvidsProvider(None, "https://api.dvidshub.net", 5)

    with pytest.raises(MediaError, match="DVIDS_API_KEY") as error:
        asyncio.run(provider.search(MediaSearchQuery("city", (MediaType.IMAGE,), 1, 0)))

    assert error.value.code == "MEDIA_PROVIDER_NOT_CONFIGURED"


def testDvidsProviderMapsAuthenticationFailure() -> None:
    provider = DvidsProvider(
        "invalid",
        "https://api.dvidshub.net",
        5,
        httpx.MockTransport(lambda _request: httpx.Response(403)),
    )

    with pytest.raises(MediaError) as error:
        asyncio.run(provider.search(MediaSearchQuery("city", (MediaType.IMAGE,), 1, 0)))

    assert error.value.code == "MEDIA_PROVIDER_AUTHENTICATION_FAILED"


@pytest.mark.parametrize(
    ("quality", "expectedFile"),
    (("highest", "4k.mp4"), ("1080p", "1080.mp4"), ("720p", "720.mp4")),
)
def testDvidsVideoQualityCapsRenditionHeight(quality: str, expectedFile: str) -> None:
    provider = DvidsProvider(
        "key-secret", "https://api.dvidshub.net", 5, videoQuality=quality
    )
    asset = {
        "files": [
            createVideoFile("720.mp4", 1280, 720, 20_000_000),
            createVideoFile("4k.mp4", 3840, 2160, 100_000_000),
            createVideoFile("1080.mp4", 1920, 1080, 50_000_000),
        ]
    }

    sourceUri, _size = provider._source(asset, MediaType.VIDEO)

    assert sourceUri == f"https://d34w7g4gy10iej.cloudfront.net/{expectedFile}"


def testDvidsVideoSizeLimitSelectsBestEligibleRendition() -> None:
    provider = DvidsProvider(
        "key-secret",
        "https://api.dvidshub.net",
        5,
        videoQuality="highest",
        maxVideoFileSizeBytes=30_000_000,
    )
    asset = {
        "files": [
            createVideoFile("4k.mp4", 3840, 2160, 100_000_000),
            createVideoFile("1080.mp4", 1920, 1080, 50_000_000),
            createVideoFile("720.mp4", 1280, 720, 20_000_000),
            {
                "src": "https://d34w7g4gy10iej.cloudfront.net/unknown.mp4",
                "type": "video/mp4",
                "width": 3840,
                "height": 2160,
            },
        ]
    }

    sourceUri, size = provider._source(asset, MediaType.VIDEO)

    assert sourceUri == "https://d34w7g4gy10iej.cloudfront.net/720.mp4"
    assert size == 20_000_000


def testDvidsRejectsInvalidVideoPolicy() -> None:
    with pytest.raises(ValueError, match="quality"):
        DvidsProvider("key-secret", "https://api.dvidshub.net", 5, videoQuality="4k")

    with pytest.raises(ValueError, match="size limit"):
        DvidsProvider(
            "key-secret",
            "https://api.dvidshub.net",
            5,
            maxVideoFileSizeBytes=-1,
        )


def createVideoFile(name: str, width: int, height: int, size: int) -> dict[str, object]:
    return {
        "src": f"https://d34w7g4gy10iej.cloudfront.net/{name}",
        "type": "video/mp4",
        "width": width,
        "height": height,
        "size": size,
    }


def testDvidsRetriesAndPersistsSearchResponses(tmp_path: Path) -> None:
    requests: list[str] = []
    delays: list[float] = []

    def handleRequest(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if requests == ["/search"]:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return dvidsResponse(request.url.path)

    async def recordSleep(delay: float) -> None:
        delays.append(delay)

    query = MediaSearchQuery("tank", (MediaType.VIDEO,), 1, 0)
    provider = DvidsProvider(
        "key-secret",
        "https://api.dvidshub.net",
        5,
        httpx.MockTransport(handleRequest),
        cacheRepository=DvidsSearchCacheRepository(tmp_path),
        sleep=recordSleep,
    )

    firstPage = asyncio.run(provider.search(query))
    restarted = DvidsProvider(
        "key-secret",
        "https://api.dvidshub.net",
        5,
        httpx.MockTransport(lambda _request: pytest.fail("cache miss")),
        cacheRepository=DvidsSearchCacheRepository(tmp_path),
    )
    secondPage = asyncio.run(restarted.search(query))

    assert requests == ["/search", "/search"]
    assert delays == [2.0]
    assert len(tuple(tmp_path.glob("*.json"))) == 1
    assert secondPage == firstPage


def testDvidsCoalescesConcurrentSearchRequests(tmp_path: Path) -> None:
    requests: list[str] = []

    async def handleRequest(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        await asyncio.sleep(0.02)
        return dvidsResponse(request.url.path)

    provider = DvidsProvider(
        "key-secret",
        "https://api.dvidshub.net",
        5,
        httpx.MockTransport(handleRequest),
        cacheRepository=DvidsSearchCacheRepository(tmp_path),
    )
    query = MediaSearchQuery("tank", (MediaType.VIDEO,), 1, 0)

    async def searchConcurrently() -> list[object]:
        return await asyncio.gather(*(provider.search(query) for _ in range(8)))

    pages = asyncio.run(searchConcurrently())

    assert requests == ["/search"]
    assert len(pages) == 8
    assert all(page == pages[0] for page in pages)
    assert provider.inFlightRequests == {}


def testDvidsSearchesMediaTypesConcurrently(tmp_path: Path) -> None:
    activeSearches = 0
    maxActiveSearches = 0

    async def handleRequest(request: httpx.Request) -> httpx.Response:
        nonlocal activeSearches, maxActiveSearches
        activeSearches += 1
        maxActiveSearches = max(maxActiveSearches, activeSearches)
        await asyncio.sleep(0.02)
        activeSearches -= 1
        mediaType = request.url.params["type"]
        assetId = "image:1" if mediaType == "image" else "video:2"
        return httpx.Response(
            200,
            json={
                "page_info": {"total_results": 3, "results_per_page": 10},
                "results": [{"id": assetId, "title": f"{mediaType} result"}],
            },
        )

    provider = DvidsProvider(
        "key-secret",
        "https://api.dvidshub.net",
        5,
        httpx.MockTransport(handleRequest),
        cacheRepository=DvidsSearchCacheRepository(tmp_path),
    )

    page = asyncio.run(
        provider.search(MediaSearchQuery("tank", tuple(MediaType), 2, 0))
    )

    assert maxActiveSearches > 1
    assert [item.id for item in page.items] == ["dvids-image-1", "dvids-video-2"]


def testDvidsSearchDoesNotResolveAssetDetails(tmp_path: Path) -> None:
    assetRequests: list[str] = []

    def handleRequest(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/search":
            return httpx.Response(
                200,
                json={
                    "page_info": {"total_results": 10, "results_per_page": 10},
                    "results": [
                        {"id": f"video:{index}", "title": f"Video {index}"}
                        for index in range(10)
                    ],
                },
            )
        assetId = request.url.params["id"]
        assetRequests.append(assetId)
        return httpx.Response(
            200,
            json={
                "results": {
                    "id": assetId,
                    "title": f"Asset {assetId}",
                    "files": [
                        {
                            "src": f"https://cdn.dvidshub.net/{assetId}.mp4",
                            "type": "video/mp4",
                            "width": 1280,
                            "height": 720,
                            "size": 1024,
                        }
                    ],
                    "url": f"https://www.dvidshub.net/video/{assetId}",
                }
            },
        )

    provider = DvidsProvider(
        "key-secret",
        "https://api.dvidshub.net",
        5,
        httpx.MockTransport(handleRequest),
        cacheRepository=DvidsSearchCacheRepository(tmp_path),
    )

    page = asyncio.run(
        provider.search(MediaSearchQuery("tank", (MediaType.VIDEO,), 3, 0))
    )

    assert assetRequests == []
    assert [item.id for item in page.items] == [
        "dvids-video-0",
        "dvids-video-1",
        "dvids-video-2",
    ]
    assert [item.sourceUri for item in page.items] == [
        "dvids://asset/video%3A0?type=video",
        "dvids://asset/video%3A1?type=video",
        "dvids://asset/video%3A2?type=video",
    ]


def testDvidsResolveRaisesWhenSelectedAssetIsUnavailable(
    tmp_path: Path,
) -> None:
    assetRequests: list[str] = []

    def handleRequest(request: httpx.Request) -> httpx.Response:
        assetId = request.url.params["id"]
        assetRequests.append(assetId)
        return httpx.Response(404)

    provider = DvidsProvider(
        "key-secret",
        "https://api.dvidshub.net",
        5,
        httpx.MockTransport(handleRequest),
        cacheRepository=DvidsSearchCacheRepository(tmp_path),
        negativeCacheRepository=DvidsSearchCacheRepository(tmp_path / "negative"),
    )

    with pytest.raises(MediaError) as error:
        asyncio.run(provider.resolveAssetSource("dvids://asset/video%3A0?type=video"))

    assert error.value.code == "MEDIA_SOURCE_NOT_FOUND"
    assert assetRequests == ["video:0"]


def testDvidsRevalidatesAssetBeforeSearchCacheExpires(tmp_path: Path) -> None:
    requests: list[str] = []
    cachedAt = datetime(2026, 7, 1, tzinfo=UTC)

    def handleRequest(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return dvidsResponse(request.url.path)

    repository = DvidsSearchCacheRepository(tmp_path)
    firstProvider = DvidsProvider(
        "key-secret",
        "https://api.dvidshub.net",
        5,
        httpx.MockTransport(handleRequest),
        cacheRepository=repository,
        cacheTtlSeconds=86_400,
        assetCacheTtlSeconds=3_600,
        nowProvider=lambda: cachedAt,
    )
    sourceUri = "dvids://asset/video%3A20?type=video"
    asyncio.run(firstProvider.resolveAssetSource(sourceUri))

    restarted = DvidsProvider(
        "key-secret",
        "https://api.dvidshub.net",
        5,
        httpx.MockTransport(handleRequest),
        cacheRepository=DvidsSearchCacheRepository(tmp_path),
        cacheTtlSeconds=86_400,
        assetCacheTtlSeconds=3_600,
        nowProvider=lambda: cachedAt + timedelta(seconds=3_601),
    )
    resolved = asyncio.run(restarted.resolveAssetSource(sourceUri))

    assert requests == ["/asset", "/asset"]
    assert resolved == "https://d34w7g4gy10iej.cloudfront.net/tank.mp4"


def testDvidsRejectsAssetTtlLongerThanSearchTtl() -> None:
    with pytest.raises(ValueError, match="cache settings"):
        DvidsProvider(
            "key-secret",
            "https://api.dvidshub.net",
            5,
            cacheTtlSeconds=3_600,
            assetCacheTtlSeconds=3_601,
        )


def dvidsResponse(path: str) -> httpx.Response:
    if path == "/search":
        return httpx.Response(
            200,
            json={
                "page_info": {"total_results": 1, "results_per_page": 10},
                "results": [
                    {
                        "id": "video:20",
                        "type": "video",
                        "title": "Tank operations",
                    }
                ],
            },
        )
    return httpx.Response(
        200,
        json={
            "results": {
                "id": "video:20",
                "title": "Tank operations",
                "files": [createVideoFile("tank.mp4", 1280, 720, 20_000_000)],
                "url": "https://www.dvidshub.net/video/20/tank-operations",
            }
        },
    )


@pytest.mark.parametrize("missingStatus", (403, 404))
def testDvidsPersistsNegativeAssetCache(tmp_path: Path, missingStatus: int) -> None:
    requests: list[str] = []

    def handleRequest(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return httpx.Response(missingStatus)

    cache = DvidsSearchCacheRepository(tmp_path / "responses")
    negative = DvidsSearchCacheRepository(tmp_path / "negative")
    provider = DvidsProvider(
        "key-secret",
        "https://api.dvidshub.net",
        5,
        httpx.MockTransport(handleRequest),
        cacheRepository=cache,
        negativeCacheRepository=negative,
    )
    sourceUri = "dvids://asset/video%3A20?type=video"

    with pytest.raises(MediaError) as firstError:
        asyncio.run(provider.resolveAssetSource(sourceUri))
    restarted = DvidsProvider(
        "key-secret",
        "https://api.dvidshub.net",
        5,
        httpx.MockTransport(lambda _request: pytest.fail("cache miss")),
        cacheRepository=DvidsSearchCacheRepository(tmp_path / "responses"),
        negativeCacheRepository=DvidsSearchCacheRepository(tmp_path / "negative"),
    )
    with pytest.raises(MediaError) as secondError:
        asyncio.run(restarted.resolveAssetSource(sourceUri))

    assert firstError.value.code == "MEDIA_SOURCE_NOT_FOUND"
    assert secondError.value.code == "MEDIA_SOURCE_NOT_FOUND"
    assert requests == ["/asset"]
    assert len(tuple((tmp_path / "negative").glob("*.json"))) == 1


def testDvidsRetriesMissingAssetAfterNegativeTtlExpires(tmp_path: Path) -> None:
    cachedAt = datetime(2026, 7, 1, tzinfo=UTC)

    provider = DvidsProvider(
        "key-secret",
        "https://api.dvidshub.net",
        5,
        httpx.MockTransport(lambda _request: httpx.Response(404)),
        cacheRepository=DvidsSearchCacheRepository(tmp_path / "responses"),
        negativeCacheRepository=DvidsSearchCacheRepository(tmp_path / "negative"),
        negativeCacheTtlSeconds=300,
        nowProvider=lambda: cachedAt,
    )
    sourceUri = "dvids://asset/video%3A20?type=video"
    with pytest.raises(MediaError):
        asyncio.run(provider.resolveAssetSource(sourceUri))

    retriedAssets: list[str] = []

    def retryMissing(request: httpx.Request) -> httpx.Response:
        retriedAssets.append(request.url.params["id"])
        return httpx.Response(404)

    restarted = DvidsProvider(
        "key-secret",
        "https://api.dvidshub.net",
        5,
        httpx.MockTransport(retryMissing),
        cacheRepository=DvidsSearchCacheRepository(tmp_path / "responses"),
        negativeCacheRepository=DvidsSearchCacheRepository(tmp_path / "negative"),
        negativeCacheTtlSeconds=300,
        nowProvider=lambda: cachedAt + timedelta(seconds=301),
    )
    with pytest.raises(MediaError):
        asyncio.run(restarted.resolveAssetSource(sourceUri))

    assert retriedAssets == ["video:20"]
