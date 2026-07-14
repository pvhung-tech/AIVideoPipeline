import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.media.cache_manifest import (
    MediaCacheEntry,
    MediaCacheManifest,
    MediaCacheSource,
)
from app.media.errors import MediaError
from app.media.models import (
    MediaSearchItem,
    MediaSearchPage,
    MediaSearchQuery,
    MediaType,
)
from app.media.provider_registry import MediaProviderRegistry
from app.project.project_model import Project
from app.repositories.file_media_cache_repository import FileMediaCacheRepository
from app.services.media_search_service import MediaSearchService
from app.services.project_service import ProjectService


class FakeMediaProvider:
    providerId = "local"

    def __init__(self) -> None:
        self.query: MediaSearchQuery | None = None

    async def search(self, query: MediaSearchQuery) -> MediaSearchPage:
        self.query = query
        return MediaSearchPage("local", query.text, 0, 0, query.limit, False, ())


def testMediaSearchServiceNormalizesAndDelegatesQuery() -> None:
    provider = FakeMediaProvider()
    service = MediaSearchService(MediaProviderRegistry((provider,)))

    page = asyncio.run(service.search("  city skyline  ", (MediaType.IMAGE,), limit=25))

    assert page.providerId == "local"
    assert provider.query is not None
    assert provider.query.text == "city skyline"
    assert provider.query.limit == 25


class AggregateMediaProvider:
    def __init__(
        self,
        providerId: str,
        items: tuple[MediaSearchItem, ...] = (),
        error: MediaError | None = None,
    ) -> None:
        self.providerId = providerId
        self.items = items
        self.error = error
        self.query: MediaSearchQuery | None = None

    async def search(self, query: MediaSearchQuery) -> MediaSearchPage:
        self.query = query
        if self.error:
            raise self.error
        return MediaSearchPage(
            self.providerId,
            query.text,
            len(self.items),
            query.offset,
            query.limit,
            False,
            self.items,
        )


def testMediaSearchServiceAggregatesDeduplicatesAndReportsPartialFailure() -> None:
    local = AggregateMediaProvider(
        "local",
        (createItem("local", "one", "file:///media/city.jpg", 0.8),),
    )
    pexels = AggregateMediaProvider(
        "pexels",
        (
            createItem("pexels", "duplicate", "file:///media/city.jpg?download=1", 1.0),
            createItem("pexels", "unique", "https://cdn.test/forest.jpg", 1.0),
        ),
    )
    pixabay = AggregateMediaProvider(
        "pixabay",
        error=MediaError("MEDIA_PROVIDER_NOT_CONFIGURED", "Pixabay is disabled."),
    )
    service = MediaSearchService(MediaProviderRegistry((local, pexels, pixabay)))

    page = asyncio.run(
        service.search("city", (MediaType.IMAGE,), providerId="all", limit=10, offset=0)
    )

    assert page.providerId == "all"
    assert [item.id for item in page.items] == ["pexels-duplicate", "pexels-unique"]
    assert page.providerErrors[0].providerId == "pixabay"
    assert page.providerErrors[0].code == "MEDIA_PROVIDER_NOT_CONFIGURED"
    assert page.truncated is True
    assert local.query is not None and local.query.limit == 10
    assert pexels.query is not None and pexels.query.offset == 0
    assert service.listProviderIds() == ("all", "local", "pexels", "pixabay")


def testMediaSearchServiceFailsWhenEveryProviderFails() -> None:
    providers = tuple(
        AggregateMediaProvider(
            providerId,
            error=MediaError("MEDIA_PROVIDER_NOT_CONFIGURED", "disabled"),
        )
        for providerId in ("local", "pexels")
    )
    service = MediaSearchService(MediaProviderRegistry(providers))

    with pytest.raises(MediaError) as error:
        asyncio.run(
            service.search("city", (MediaType.IMAGE,), providerId="all", limit=10)
        )

    assert error.value.code == "MEDIA_ALL_PROVIDERS_FAILED"


def testMediaSearchServiceUsesActiveProjectFingerprints(tmp_path: Path) -> None:
    first = createItem("local", "one", "file:///media/one.jpg", 1.0)
    second = createItem("pexels", "two", "https://cdn.test/two.jpg", 1.0)
    providers = (
        AggregateMediaProvider("local", (first,)),
        AggregateMediaProvider("pexels", (second,)),
    )
    projectPath = tmp_path / "project"
    projectPath.mkdir()
    projectService = ProjectService(FakeProjectRepository())
    projectService.activeProject = Project(
        "project-id", "Project", projectPath, datetime.now(UTC), datetime.now(UTC)
    )
    FileMediaCacheRepository().save(
        projectPath / "cache", createFingerprintManifest(first, second)
    )
    service = MediaSearchService(
        MediaProviderRegistry(providers), projectService=projectService
    )

    page = asyncio.run(
        service.search("city", (MediaType.IMAGE,), providerId="all", limit=10)
    )

    assert [item.id for item in page.items] == [first.id]
    assert page.deduplication is not None
    assert page.deduplication.perceptualImageDuplicates == 1


def createItem(
    providerId: str, itemId: str, sourceUri: str, score: float
) -> MediaSearchItem:
    return MediaSearchItem(
        id=f"{providerId}-{itemId}",
        providerId=providerId,
        mediaType=MediaType.IMAGE,
        title=itemId,
        sourceUri=sourceUri,
        previewUri=sourceUri,
        fileSizeBytes=100,
        modifiedAt=datetime.now(UTC),
        score=score,
        creator="Creator",
    )


class FakeProjectRepository:
    def createProject(self, project: Project) -> Project:
        return project

    def saveProject(self, project: Project) -> Project:
        return project

    def openProject(self, projectPath: Path) -> Project:
        raise NotImplementedError

    def listRecentProjects(self, limit: int) -> list[Project]:
        return []


def createFingerprintManifest(
    first: MediaSearchItem, second: MediaSearchItem
) -> MediaCacheManifest:
    timestamp = datetime.now(UTC)
    entries = tuple(
        MediaCacheEntry(
            contentHash=str(index) * 64,
            relativePath=f"aa/{index}.jpg",
            sizeBytes=100,
            createdAt=timestamp,
            lastAccessedAt=timestamp,
            sources=(MediaCacheSource(item.providerId, item.id, item.sourceUri),),
            perceptualHash=fingerprint,
        )
        for index, (item, fingerprint) in enumerate(
            (
                (first, "dhash64-v1:0000000000000000"),
                (second, "dhash64-v1:000000000000000f"),
            ),
            start=1,
        )
    )
    return MediaCacheManifest(entries)
