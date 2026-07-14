import asyncio

import httpx
import pytest

from app.media.errors import MediaError
from app.media.models import MediaSearchQuery, MediaType
from app.media.pexels_provider import PexelsProvider


def testPexelsProviderSearchesPhotosAndVideos() -> None:
    requests: list[str] = []

    def handleRequest(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        assert request.headers["Authorization"] == "secret"
        if request.url.path == "/v1/search":
            return httpx.Response(
                200,
                json={
                    "total_results": 20,
                    "photos": [
                        {
                            "id": 10,
                            "url": "https://www.pexels.com/photo/city-light-10/",
                            "photographer": "Alex",
                            "photographer_url": "https://www.pexels.com/@alex",
                            "alt": "City light",
                            "src": {
                                "original": "https://images.pexels.com/photos/10/a.jpg",
                                "medium": "https://images.pexels.com/photos/10/m.jpg",
                            },
                        }
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "total_results": 8,
                "videos": [
                    {
                        "id": 20,
                        "url": "https://www.pexels.com/video/city-night-20/",
                        "user": {"name": "Sam"},
                        "video_files": [
                            {
                                "width": 1920,
                                "height": 1080,
                                "file_size": 400,
                                "link": "https://videos.pexels.com/video-files/20.mp4",
                            }
                        ],
                        "video_pictures": [
                            {"picture": "https://images.pexels.com/videos/20.jpg"}
                        ],
                    }
                ],
            },
        )

    provider = PexelsProvider(
        "secret",
        "https://api.pexels.com",
        5,
        httpx.MockTransport(handleRequest),
    )
    query = MediaSearchQuery("city", tuple(MediaType), 2, 0)

    page = asyncio.run(provider.search(query))

    assert requests == ["/v1/search", "/v1/videos/search"]
    assert page.totalResults == 28
    assert [item.id for item in page.items] == [
        "pexels-photo-10",
        "pexels-video-20",
    ]
    assert page.items[0].license == "Pexels License"
    assert page.items[0].creator == "Alex"
    assert page.items[0].creatorUri == "https://www.pexels.com/@alex"


def testPexelsProviderSearchesMediaTypesConcurrently() -> None:
    activeRequests = 0
    maxActiveRequests = 0

    async def handleRequest(request: httpx.Request) -> httpx.Response:
        nonlocal activeRequests, maxActiveRequests
        activeRequests += 1
        maxActiveRequests = max(maxActiveRequests, activeRequests)
        await asyncio.sleep(0.02)
        activeRequests -= 1
        if request.url.path == "/v1/search":
            return httpx.Response(200, json={"total_results": 1, "photos": []})
        return httpx.Response(200, json={"total_results": 1, "videos": []})

    provider = PexelsProvider(
        "secret",
        "https://api.pexels.com",
        5,
        httpx.MockTransport(handleRequest),
    )

    asyncio.run(provider.search(MediaSearchQuery("city", tuple(MediaType), 2, 0)))

    assert maxActiveRequests == 2


def testPexelsProviderRequiresApiKey() -> None:
    provider = PexelsProvider(None, "https://api.pexels.com", 5)
    query = MediaSearchQuery("city", (MediaType.IMAGE,), 10, 0)

    with pytest.raises(MediaError, match="PEXELS_API_KEY") as error:
        asyncio.run(provider.search(query))

    assert error.value.code == "MEDIA_PROVIDER_NOT_CONFIGURED"


def testPexelsProviderMapsRateLimit() -> None:
    provider = PexelsProvider(
        "secret",
        "https://api.pexels.com",
        5,
        httpx.MockTransport(lambda _request: httpx.Response(429)),
    )
    query = MediaSearchQuery("city", (MediaType.IMAGE,), 10, 0)

    with pytest.raises(MediaError) as error:
        asyncio.run(provider.search(query))

    assert error.value.code == "MEDIA_PROVIDER_RATE_LIMITED"
