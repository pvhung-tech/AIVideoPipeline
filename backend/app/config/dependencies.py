from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Depends

from app.config.settings import AppSettings, getSettings

if TYPE_CHECKING:
    from app.ai.prompt_manager import PromptManager
    from app.ai.provider_registry import AIProviderRegistry
    from app.media.dvids_provider import DvidsProvider
    from app.media.provider_registry import MediaProviderRegistry
    from app.repositories.file_scene_analysis_repository import (
        FileSceneAnalysisRepository,
    )
    from app.services.media_cache_reconciliation_service import (
        MediaCacheReconciliationService,
    )
    from app.services.media_cache_service import MediaCacheService
    from app.services.media_fingerprint_backfill_service import (
        MediaFingerprintBackfillService,
    )
    from app.services.media_metadata_backfill_service import (
        MediaMetadataBackfillService,
    )
    from app.services.media_search_service import MediaSearchService
    from app.services.project_service import ProjectService
    from app.services.render_job_service import RenderJobService
    from app.services.render_service import RenderService
    from app.services.scene_analysis_service import SceneAnalysisService
    from app.services.scene_service import SceneService
    from app.services.script_service import ScriptService
    from app.services.setup_service import SetupService
    from app.services.timeline_media_service import TimelineMediaService
    from app.services.timeline_service import TimelineService


@lru_cache(maxsize=4)
def createProjectService(appDataDirectory: str) -> ProjectService:
    from app.repositories.sqlite_project_repository import SQLiteProjectRepository
    from app.services.project_service import ProjectService

    repository = SQLiteProjectRepository(Path(appDataDirectory))
    return ProjectService(repository)


def getProjectService(
    settings: Annotated[AppSettings, Depends(getSettings)],
) -> ProjectService:
    return createProjectService(str(settings.appDataDirectory))


@lru_cache(maxsize=4)
def createPromptManager(configPath: str) -> PromptManager:
    from app.ai.prompt_manager import PromptManager
    from app.repositories.file_prompt_repository import FilePromptRepository

    return PromptManager(FilePromptRepository(Path(configPath)))


def getPromptManager(
    settings: Annotated[AppSettings, Depends(getSettings)],
) -> PromptManager:
    return createPromptManager(str(settings.promptConfigPath))


@lru_cache(maxsize=4)
def createAIProviderRegistry(
    ollamaBaseUrl: str,
    openaiApiKey: str | None,
    openaiBaseUrl: str,
    timeoutSeconds: float,
    maxAttempts: int,
    initialDelaySeconds: float,
    maxDelaySeconds: float,
) -> AIProviderRegistry:
    from app.ai.ollama_provider import OllamaProvider
    from app.ai.openai_provider import OpenAIProvider
    from app.ai.provider_registry import AIProviderRegistry
    from app.ai.retrying_provider import RetryingAIProvider

    retrySettings = (maxAttempts, initialDelaySeconds, maxDelaySeconds)
    providers = (
        RetryingAIProvider(
            OllamaProvider(ollamaBaseUrl, timeoutSeconds), *retrySettings
        ),
        RetryingAIProvider(
            OpenAIProvider(openaiApiKey, openaiBaseUrl, timeoutSeconds),
            *retrySettings,
        ),
    )
    return AIProviderRegistry(providers)


@lru_cache(maxsize=1)
def createSceneAnalysisRepository() -> FileSceneAnalysisRepository:
    from app.repositories.file_scene_analysis_repository import (
        FileSceneAnalysisRepository,
    )

    return FileSceneAnalysisRepository()


def getSceneAnalysisService(
    settings: Annotated[AppSettings, Depends(getSettings)],
    projectService: Annotated[Any, Depends(getProjectService)],
    promptManager: Annotated[PromptManager, Depends(getPromptManager)],
) -> SceneAnalysisService:
    from app.ai.scene_analysis_parser import SceneAnalysisParser
    from app.repositories.file_scene_repository import FileSceneRepository
    from app.services.scene_analysis_service import SceneAnalysisService

    return SceneAnalysisService(
        promptManager=promptManager,
        providerRegistry=createAIProviderRegistry(
            settings.ollamaBaseUrl,
            settings.openaiApiKey,
            settings.openaiBaseUrl,
            settings.aiRequestTimeoutSeconds,
            settings.aiMaxAttempts,
            settings.aiRetryInitialDelaySeconds,
            settings.aiRetryMaxDelaySeconds,
        ),
        sceneRepository=FileSceneRepository(),
        analysisRepository=createSceneAnalysisRepository(),
        projectService=projectService,
        parser=SceneAnalysisParser(),
        defaultProviderId="ollama",
        defaultModels={
            "ollama": settings.ollamaModel,
            "openai": settings.openaiModel,
        },
    )


def getSetupService(
    settings: Annotated[AppSettings, Depends(getSettings)],
) -> SetupService:
    from app.services.setup_service import SetupService

    return SetupService(settings)


@lru_cache(maxsize=4)
def createMediaProviderRegistry(
    libraryPaths: tuple[str, ...],
    maxScannedFiles: int,
    pexelsApiKey: str | None,
    pexelsBaseUrl: str,
    dvidsApiKey: str | None,
    dvidsBaseUrl: str,
    dvidsVideoQuality: str,
    dvidsVideoMaxFileSizeBytes: int,
    dvidsMaxAttempts: int,
    dvidsRetryInitialDelaySeconds: float,
    dvidsRetryMaxDelaySeconds: float,
    dvidsRetryJitterRatio: float,
    dvidsSearchCacheTtlSeconds: int,
    dvidsAssetCacheTtlSeconds: int,
    dvidsNegativeCacheTtlSeconds: int,
    pixabayApiKey: str | None,
    pixabayBaseUrl: str,
    appDataDirectory: str,
    pixabayMaxAttempts: int,
    pixabayRetryInitialDelaySeconds: float,
    pixabayRetryMaxDelaySeconds: float,
    pixabayRetryJitterRatio: float,
    pixabaySearchCacheTtlSeconds: int,
    wikimediaCommonsBaseUrl: str,
    wikimediaUserAgent: str | None,
    wikimediaMaxAttempts: int,
    wikimediaRetryInitialDelaySeconds: float,
    wikimediaRetryMaxDelaySeconds: float,
    wikimediaRetryJitterRatio: float,
    wikimediaSearchCacheTtlSeconds: int,
    timeoutSeconds: float,
) -> MediaProviderRegistry:
    from app.media.local_library_provider import LocalLibraryProvider
    from app.media.pexels_provider import PexelsProvider
    from app.media.pixabay_provider import PixabayProvider
    from app.media.provider_registry import MediaProviderRegistry
    from app.media.wikimedia_commons_provider import WikimediaCommonsProvider
    from app.repositories.pixabay_search_cache_repository import (
        PixabaySearchCacheRepository,
    )
    from app.repositories.wikimedia_search_cache_repository import (
        WikimediaSearchCacheRepository,
    )

    localProvider = LocalLibraryProvider(
        tuple(Path(path) for path in libraryPaths), maxScannedFiles
    )
    pexelsProvider = PexelsProvider(pexelsApiKey, pexelsBaseUrl, timeoutSeconds)
    dvidsProvider = createDvidsProvider(
        dvidsApiKey,
        dvidsBaseUrl,
        timeoutSeconds,
        dvidsVideoQuality,
        dvidsVideoMaxFileSizeBytes,
        dvidsMaxAttempts,
        dvidsRetryInitialDelaySeconds,
        dvidsRetryMaxDelaySeconds,
        dvidsRetryJitterRatio,
        dvidsSearchCacheTtlSeconds,
        dvidsAssetCacheTtlSeconds,
        dvidsNegativeCacheTtlSeconds,
        appDataDirectory,
    )
    pixabayCache = PixabaySearchCacheRepository(
        Path(appDataDirectory) / "cache" / "providers" / "pixabay" / "search"
    )
    pixabayProvider = PixabayProvider(
        pixabayApiKey,
        pixabayBaseUrl,
        timeoutSeconds,
        pixabayCache,
        maxAttempts=pixabayMaxAttempts,
        initialDelaySeconds=pixabayRetryInitialDelaySeconds,
        maxDelaySeconds=pixabayRetryMaxDelaySeconds,
        jitterRatio=pixabayRetryJitterRatio,
        cacheTtlSeconds=pixabaySearchCacheTtlSeconds,
    )
    wikimediaCache = WikimediaSearchCacheRepository(
        Path(appDataDirectory) / "cache" / "providers" / "wikimedia" / "search"
    )
    wikimediaProvider = WikimediaCommonsProvider(
        wikimediaCommonsBaseUrl,
        wikimediaUserAgent,
        timeoutSeconds,
        cacheRepository=wikimediaCache,
        maxAttempts=wikimediaMaxAttempts,
        initialDelaySeconds=wikimediaRetryInitialDelaySeconds,
        maxDelaySeconds=wikimediaRetryMaxDelaySeconds,
        jitterRatio=wikimediaRetryJitterRatio,
        cacheTtlSeconds=wikimediaSearchCacheTtlSeconds,
    )
    return MediaProviderRegistry(
        (
            localProvider,
            pexelsProvider,
            dvidsProvider,
            pixabayProvider,
            wikimediaProvider,
        )
    )


@lru_cache(maxsize=4)
def createDvidsProvider(
    dvidsApiKey: str | None,
    dvidsBaseUrl: str,
    timeoutSeconds: float,
    dvidsVideoQuality: str,
    dvidsVideoMaxFileSizeBytes: int,
    dvidsMaxAttempts: int,
    dvidsRetryInitialDelaySeconds: float,
    dvidsRetryMaxDelaySeconds: float,
    dvidsRetryJitterRatio: float,
    dvidsSearchCacheTtlSeconds: int,
    dvidsAssetCacheTtlSeconds: int,
    dvidsNegativeCacheTtlSeconds: int,
    appDataDirectory: str,
) -> DvidsProvider:
    from app.media.dvids_provider import DvidsProvider
    from app.repositories.dvids_search_cache_repository import (
        DvidsSearchCacheRepository,
    )

    dvidsCache = DvidsSearchCacheRepository(
        Path(appDataDirectory) / "cache" / "providers" / "dvids" / "search"
    )
    dvidsNegativeCache = DvidsSearchCacheRepository(
        Path(appDataDirectory) / "cache" / "providers" / "dvids" / "negative"
    )
    return DvidsProvider(
        dvidsApiKey,
        dvidsBaseUrl,
        timeoutSeconds,
        videoQuality=dvidsVideoQuality,
        maxVideoFileSizeBytes=dvidsVideoMaxFileSizeBytes,
        cacheRepository=dvidsCache,
        maxAttempts=dvidsMaxAttempts,
        initialDelaySeconds=dvidsRetryInitialDelaySeconds,
        maxDelaySeconds=dvidsRetryMaxDelaySeconds,
        jitterRatio=dvidsRetryJitterRatio,
        cacheTtlSeconds=dvidsSearchCacheTtlSeconds,
        assetCacheTtlSeconds=dvidsAssetCacheTtlSeconds,
        negativeCacheRepository=dvidsNegativeCache,
        negativeCacheTtlSeconds=dvidsNegativeCacheTtlSeconds,
    )


def getMediaSearchService(
    settings: Annotated[AppSettings, Depends(getSettings)],
    projectService: Annotated[Any, Depends(getProjectService)],
) -> MediaSearchService:
    from app.media.deduplication_thresholds import loadMediaDeduplicationThresholds
    from app.media.media_result_ranker import MediaResultRanker
    from app.services.media_search_service import MediaSearchService

    registry = createMediaProviderRegistry(
        tuple(str(path) for path in settings.localMediaLibraryPaths),
        settings.localMediaMaxScannedFiles,
        settings.pexelsApiKey,
        settings.pexelsBaseUrl,
        settings.dvidsApiKey,
        settings.dvidsBaseUrl,
        settings.dvidsVideoQuality,
        settings.dvidsVideoMaxFileSizeBytes,
        settings.dvidsMaxAttempts,
        settings.dvidsRetryInitialDelaySeconds,
        settings.dvidsRetryMaxDelaySeconds,
        settings.dvidsRetryJitterRatio,
        settings.dvidsSearchCacheTtlSeconds,
        settings.dvidsAssetCacheTtlSeconds,
        settings.dvidsNegativeCacheTtlSeconds,
        settings.pixabayApiKey,
        settings.pixabayBaseUrl,
        str(settings.appDataDirectory),
        settings.pixabayMaxAttempts,
        settings.pixabayRetryInitialDelaySeconds,
        settings.pixabayRetryMaxDelaySeconds,
        settings.pixabayRetryJitterRatio,
        settings.pixabaySearchCacheTtlSeconds,
        settings.wikimediaCommonsBaseUrl,
        settings.wikimediaUserAgent,
        settings.wikimediaMaxAttempts,
        settings.wikimediaRetryInitialDelaySeconds,
        settings.wikimediaRetryMaxDelaySeconds,
        settings.wikimediaRetryJitterRatio,
        settings.wikimediaSearchCacheTtlSeconds,
        settings.mediaDownloadTimeoutSeconds,
    )
    return MediaSearchService(
        registry,
        resultRanker=MediaResultRanker(
            loadMediaDeduplicationThresholds(settings.mediaDedupThresholdsPath)
        ),
        projectService=projectService,
    )


@lru_cache(maxsize=4)
def createMediaCacheService(
    projectService: ProjectService,
    localLibraryPaths: tuple[Path, ...],
    maxFileSizeBytes: int,
    timeoutSeconds: float,
    maxTotalSizeBytes: int,
    maxAgeDays: int,
    ffmpegPath: str | None,
    metadataTimeoutSeconds: float,
    dvidsApiKey: str | None,
    dvidsBaseUrl: str,
    dvidsVideoQuality: str,
    dvidsVideoMaxFileSizeBytes: int,
    dvidsMaxAttempts: int,
    dvidsRetryInitialDelaySeconds: float,
    dvidsRetryMaxDelaySeconds: float,
    dvidsRetryJitterRatio: float,
    dvidsSearchCacheTtlSeconds: int,
    dvidsAssetCacheTtlSeconds: int,
    dvidsNegativeCacheTtlSeconds: int,
    appDataDirectory: str,
) -> MediaCacheService:
    from app.media.media_fingerprint_service import MediaFingerprintService
    from app.media.media_metadata_service import MediaMetadataService
    from app.services.media_cache_service import MediaCacheService

    return MediaCacheService(
        projectService=projectService,
        localLibraryPaths=localLibraryPaths,
        maxFileSizeBytes=maxFileSizeBytes,
        timeoutSeconds=timeoutSeconds,
        maxTotalSizeBytes=maxTotalSizeBytes,
        maxAgeDays=maxAgeDays,
        fingerprintService=MediaFingerprintService(ffmpegPath, metadataTimeoutSeconds),
        metadataService=MediaMetadataService(ffmpegPath, metadataTimeoutSeconds),
        dvidsSourceResolver=createDvidsProvider(
            dvidsApiKey,
            dvidsBaseUrl,
            timeoutSeconds,
            dvidsVideoQuality,
            dvidsVideoMaxFileSizeBytes,
            dvidsMaxAttempts,
            dvidsRetryInitialDelaySeconds,
            dvidsRetryMaxDelaySeconds,
            dvidsRetryJitterRatio,
            dvidsSearchCacheTtlSeconds,
            dvidsAssetCacheTtlSeconds,
            dvidsNegativeCacheTtlSeconds,
            appDataDirectory,
        ),
    )


def getMediaCacheService(
    settings: Annotated[AppSettings, Depends(getSettings)],
    projectService: Annotated[Any, Depends(getProjectService)],
) -> MediaCacheService:
    return createMediaCacheService(
        projectService,
        settings.localMediaLibraryPaths,
        settings.mediaCacheMaxFileSizeBytes,
        settings.mediaDownloadTimeoutSeconds,
        settings.mediaCacheMaxTotalSizeBytes,
        settings.mediaCacheMaxAgeDays,
        settings.ffmpegPath,
        settings.mediaFingerprintTimeoutSeconds,
        settings.dvidsApiKey,
        settings.dvidsBaseUrl,
        settings.dvidsVideoQuality,
        settings.dvidsVideoMaxFileSizeBytes,
        settings.dvidsMaxAttempts,
        settings.dvidsRetryInitialDelaySeconds,
        settings.dvidsRetryMaxDelaySeconds,
        settings.dvidsRetryJitterRatio,
        settings.dvidsSearchCacheTtlSeconds,
        settings.dvidsAssetCacheTtlSeconds,
        settings.dvidsNegativeCacheTtlSeconds,
        str(settings.appDataDirectory),
    )


@lru_cache(maxsize=4)
def createMediaMetadataBackfillService(
    mediaCacheService: MediaCacheService, projectService: ProjectService
) -> MediaMetadataBackfillService:
    from app.services.media_metadata_backfill_service import (
        MediaMetadataBackfillService,
    )

    return MediaMetadataBackfillService(mediaCacheService, projectService)


def getMediaMetadataBackfillService(
    mediaCacheService: Annotated[Any, Depends(getMediaCacheService)],
    projectService: Annotated[Any, Depends(getProjectService)],
) -> MediaMetadataBackfillService:
    return createMediaMetadataBackfillService(mediaCacheService, projectService)


@lru_cache(maxsize=4)
def createMediaFingerprintBackfillService(
    mediaCacheService: MediaCacheService, projectService: ProjectService
) -> MediaFingerprintBackfillService:
    from app.services.media_fingerprint_backfill_service import (
        MediaFingerprintBackfillService,
    )

    return MediaFingerprintBackfillService(mediaCacheService, projectService)


def getMediaFingerprintBackfillService(
    mediaCacheService: Annotated[Any, Depends(getMediaCacheService)],
    projectService: Annotated[Any, Depends(getProjectService)],
) -> MediaFingerprintBackfillService:
    return createMediaFingerprintBackfillService(mediaCacheService, projectService)


def getMediaCacheReconciliationService(
    projectService: Annotated[Any, Depends(getProjectService)],
) -> MediaCacheReconciliationService:
    from app.services.media_cache_reconciliation_service import (
        MediaCacheReconciliationService,
    )

    return MediaCacheReconciliationService(projectService)


def getScriptService(
    projectService: Annotated[Any, Depends(getProjectService)],
) -> ScriptService:
    from app.pipeline.scene_parser import SceneParser
    from app.pipeline.subtitle_parser import SubtitleParser
    from app.repositories.file_scene_repository import FileSceneRepository
    from app.repositories.file_script_repository import FileScriptRepository
    from app.services.script_service import ScriptService

    return ScriptService(
        FileScriptRepository(),
        projectService,
        SubtitleParser(),
        SceneParser(),
        FileSceneRepository(),
    )


def getSceneService(
    projectService: Annotated[Any, Depends(getProjectService)],
) -> SceneService:
    from app.repositories.file_scene_repository import FileSceneRepository
    from app.services.scene_service import SceneService

    return SceneService(FileSceneRepository(), projectService)


def getTimelineService(
    projectService: Annotated[Any, Depends(getProjectService)],
) -> TimelineService:
    from app.repositories.file_scene_repository import FileSceneRepository
    from app.repositories.file_timeline_repository import FileTimelineRepository
    from app.services.timeline_service import TimelineService
    from app.timeline.initial_timeline_service import InitialTimelineService
    from app.timeline.validation_service import TimelineValidationService

    return TimelineService(
        FileTimelineRepository(),
        FileSceneRepository(),
        projectService,
        TimelineValidationService(),
        InitialTimelineService(),
    )


def getTimelineMediaService(
    timelineService: Annotated[Any, Depends(getTimelineService)],
    mediaCacheService: Annotated[Any, Depends(getMediaCacheService)],
    projectService: Annotated[Any, Depends(getProjectService)],
) -> TimelineMediaService:
    from app.services.timeline_media_service import TimelineMediaService

    return TimelineMediaService(timelineService, mediaCacheService, projectService)


def getRenderService(
    settings: Annotated[AppSettings, Depends(getSettings)],
    timelineService: Annotated[Any, Depends(getTimelineService)],
    mediaCacheService: Annotated[Any, Depends(getMediaCacheService)],
    projectService: Annotated[Any, Depends(getProjectService)],
) -> RenderService:
    from app.render.ffmpeg_command_builder import FFmpegCommandBuilder
    from app.services.render_service import RenderService

    return RenderService(
        timelineService,
        mediaCacheService,
        projectService,
        FFmpegCommandBuilder(),
        settings.ffmpegPath,
    )


_renderJobService: RenderJobService | None = None


def getRenderJobService(
    settings: Annotated[AppSettings, Depends(getSettings)],
    timelineService: Annotated[Any, Depends(getTimelineService)],
    mediaCacheService: Annotated[Any, Depends(getMediaCacheService)],
    projectService: Annotated[Any, Depends(getProjectService)],
) -> RenderJobService:
    from app.render.ffmpeg_command_builder import FFmpegCommandBuilder
    from app.repositories.file_render_job_repository import FileRenderJobRepository
    from app.services.render_job_service import RenderJobService
    from app.services.render_service import RenderService

    global _renderJobService
    if _renderJobService is None:
        _renderJobService = RenderJobService(
            RenderService(
                timelineService,
                mediaCacheService,
                projectService,
                FFmpegCommandBuilder(),
                settings.ffmpegPath,
            ),
            FileRenderJobRepository(),
        )
    return _renderJobService
