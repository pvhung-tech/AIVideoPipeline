import asyncio
import logging

from app.media.cache_manifest import MediaCacheManifest
from app.media.errors import MediaError
from app.media.media_result_ranker import MediaResultRanker
from app.media.models import (
    MediaProviderError,
    MediaSearchPage,
    MediaSearchQuery,
    MediaType,
)
from app.media.provider_registry import MediaProviderRegistry
from app.repositories.file_media_cache_repository import FileMediaCacheRepository
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)
MULTI_PROVIDER_ID = "all"


class MediaSearchService:
    def __init__(
        self,
        registry: MediaProviderRegistry,
        defaultProviderId: str = "local",
        resultRanker: MediaResultRanker | None = None,
        projectService: ProjectService | None = None,
        cacheRepository: FileMediaCacheRepository | None = None,
    ) -> None:
        self.registry = registry
        self.defaultProviderId = defaultProviderId
        self.resultRanker = resultRanker or MediaResultRanker()
        self.projectService = projectService
        self.cacheRepository = cacheRepository or FileMediaCacheRepository()

    async def search(
        self,
        text: str,
        mediaTypes: tuple[MediaType, ...],
        providerId: str | None = None,
        limit: int = 50,
        offset: int = 0,
        contentCategory: str | None = None,
    ) -> MediaSearchPage:
        query = MediaSearchQuery(
            text=text.strip(),
            mediaTypes=mediaTypes,
            limit=limit,
            offset=offset,
        )
        selectedProviderId = (providerId or self.defaultProviderId).strip().lower()
        if selectedProviderId == MULTI_PROVIDER_ID:
            return await self._searchAll(query, contentCategory)
        return await self.registry.get(selectedProviderId).search(query)

    def listProviderIds(self) -> tuple[str, ...]:
        return (MULTI_PROVIDER_ID, *self.registry.listProviderIds())

    async def _searchAll(
        self, query: MediaSearchQuery, contentCategory: str | None
    ) -> MediaSearchPage:
        providerIds = self.registry.listProviderIds()
        requested = min(100, max(5, query.offset + query.limit))
        providerQuery = MediaSearchQuery(query.text, query.mediaTypes, requested, 0)
        results = await asyncio.gather(
            *(
                self.registry.get(providerId).search(providerQuery)
                for providerId in providerIds
            ),
            return_exceptions=True,
        )
        pages: list[MediaSearchPage] = []
        errors: list[MediaProviderError] = []
        for providerId, result in zip(providerIds, results, strict=True):
            if isinstance(result, MediaSearchPage):
                pages.append(result)
            elif isinstance(result, MediaError):
                errors.append(
                    MediaProviderError(providerId, result.code, result.message)
                )
            else:
                logger.error(
                    "Unexpected media provider failure for %s: %s",
                    providerId,
                    type(result).__name__,
                )
                errors.append(
                    MediaProviderError(
                        providerId,
                        "MEDIA_PROVIDER_FAILED",
                        f"Media provider '{providerId}' failed unexpectedly.",
                    )
                )
        if not pages:
            raise MediaError(
                "MEDIA_ALL_PROVIDERS_FAILED", "All media providers failed."
            )
        ranking = self.resultRanker.rankWithStatistics(
            tuple(pages), self._loadCacheManifest(), contentCategory
        )
        end = query.offset + query.limit
        items = ranking.items[query.offset : end]
        totalResults = sum(page.totalResults for page in pages)
        truncated = (
            end < len(ranking.items)
            or any(
                page.truncated or page.totalResults > len(page.items) for page in pages
            )
            or bool(errors)
        )
        return MediaSearchPage(
            MULTI_PROVIDER_ID,
            query.text,
            totalResults,
            query.offset,
            query.limit,
            truncated,
            items,
            tuple(errors),
            ranking.statistics,
        )

    def _loadCacheManifest(self) -> MediaCacheManifest:
        project = (
            self.projectService.getCurrentProject() if self.projectService else None
        )
        if project is None:
            return MediaCacheManifest(())
        try:
            return self.cacheRepository.load(project.path / "cache")
        except MediaError as error:
            logger.warning("Media fingerprint index unavailable: %s", error.code)
            return MediaCacheManifest(())
