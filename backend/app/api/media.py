from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.config.dependencies import (
    getMediaCacheReconciliationService,
    getMediaCacheService,
    getMediaFingerprintBackfillService,
    getMediaMetadataBackfillService,
    getMediaSearchService,
)
from app.media.models import MediaType
from app.models.api_response import ApiResponse

router = APIRouter(prefix="/media", tags=["media"])


class CacheMediaRequest(BaseModel):
    providerId: str = Field(min_length=1, max_length=100)
    mediaId: str = Field(min_length=1, max_length=200)
    sourceUri: str = Field(min_length=1, max_length=4000)
    fileName: str | None = Field(default=None, min_length=1, max_length=255)


class CleanupMediaCacheRequest(BaseModel):
    dryRun: bool = True
    maxTotalSizeBytes: int | None = Field(default=None, ge=0)
    maxAgeDays: int | None = Field(default=None, ge=0)


class ReconcileMediaCacheRequest(BaseModel):
    dryRun: bool = True


@router.get("/search", response_model=ApiResponse)
async def searchMedia(
    service: Annotated[Any, Depends(getMediaSearchService)],
    query: Annotated[str, Query(min_length=1, max_length=500)],
    mediaType: Annotated[list[MediaType] | None, Query()] = None,
    providerId: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    contentCategory: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
) -> ApiResponse:
    mediaTypes = tuple(mediaType) if mediaType else (MediaType.IMAGE, MediaType.VIDEO)
    page = await service.search(
        text=query,
        mediaTypes=mediaTypes,
        providerId=providerId,
        limit=limit,
        offset=offset,
        contentCategory=contentCategory,
    )
    return ApiResponse(
        success=True,
        data=page.toDictionary(),
        message="Media search completed.",
        error=None,
    )


@router.get("/providers", response_model=ApiResponse)
def listMediaProviders(
    service: Annotated[Any, Depends(getMediaSearchService)],
) -> ApiResponse:
    providerIds = service.listProviderIds()
    return ApiResponse(
        success=True,
        data={"providers": list(providerIds)},
        message="Media providers loaded.",
        error=None,
    )


@router.post("/cache", response_model=ApiResponse)
async def cacheMedia(
    request: CacheMediaRequest,
    service: Annotated[Any, Depends(getMediaCacheService)],
) -> ApiResponse:
    cachedMedia = await service.cache(
        providerId=request.providerId,
        mediaId=request.mediaId,
        sourceUri=request.sourceUri,
        fileName=request.fileName,
    )
    return ApiResponse(
        success=True,
        data=cachedMedia.toDictionary(),
        message="Media cached.",
        error=None,
    )


@router.get("/cache", response_model=ApiResponse)
def getMediaCacheManifest(
    service: Annotated[Any, Depends(getMediaCacheService)],
) -> ApiResponse:
    manifest = service.getManifest()
    return ApiResponse(
        success=True,
        data=manifest.toDictionary(),
        message="Media cache manifest loaded.",
        error=None,
    )


@router.post("/cache/metadata/backfill", response_model=ApiResponse)
def backfillMediaMetadata(
    service: Annotated[
        Any, Depends(getMediaMetadataBackfillService)
    ],
) -> ApiResponse:
    job = service.startForActiveProject()
    return ApiResponse(
        success=True,
        data=job.toDictionary(),
        message="Video metadata backfill started.",
        error=None,
    )


@router.get("/cache/metadata/backfill/status", response_model=ApiResponse)
def getMediaMetadataBackfillStatus(
    service: Annotated[
        Any, Depends(getMediaMetadataBackfillService)
    ],
) -> ApiResponse:
    job = service.getActiveProjectJob()
    return ApiResponse(
        success=True,
        data=job.toDictionary() if job else None,
        message="Video metadata backfill status loaded.",
        error=None,
    )


@router.post("/cache/metadata/backfill/cancel", response_model=ApiResponse)
def cancelMediaMetadataBackfill(
    service: Annotated[
        Any, Depends(getMediaMetadataBackfillService)
    ],
) -> ApiResponse:
    job = service.cancelActiveProjectJob()
    return ApiResponse(
        success=True,
        data=job.toDictionary(),
        message="Video metadata backfill cancellation requested.",
        error=None,
    )


@router.post("/cache/fingerprints/backfill", response_model=ApiResponse)
def backfillMediaFingerprints(
    service: Annotated[
        Any, Depends(getMediaFingerprintBackfillService)
    ],
) -> ApiResponse:
    job = service.startForActiveProject()
    return ApiResponse(
        success=True,
        data=job.toDictionary(),
        message="Media fingerprint backfill started.",
        error=None,
    )


@router.get("/cache/fingerprints/backfill/status", response_model=ApiResponse)
def getMediaFingerprintBackfillStatus(
    service: Annotated[
        Any, Depends(getMediaFingerprintBackfillService)
    ],
) -> ApiResponse:
    job = service.getActiveProjectJob()
    return ApiResponse(
        success=True,
        data=job.toDictionary() if job else None,
        message="Media fingerprint backfill status loaded.",
        error=None,
    )


@router.post("/cache/fingerprints/backfill/cancel", response_model=ApiResponse)
def cancelMediaFingerprintBackfill(
    service: Annotated[
        Any, Depends(getMediaFingerprintBackfillService)
    ],
) -> ApiResponse:
    job = service.cancelActiveProjectJob()
    return ApiResponse(
        success=True,
        data=job.toDictionary(),
        message="Media fingerprint backfill cancellation requested.",
        error=None,
    )


@router.post("/cache/cleanup", response_model=ApiResponse)
def cleanupMediaCache(
    request: CleanupMediaCacheRequest,
    service: Annotated[Any, Depends(getMediaCacheService)],
) -> ApiResponse:
    result = service.cleanup(
        dryRun=request.dryRun,
        maxTotalSizeBytes=request.maxTotalSizeBytes,
        maxAgeDays=request.maxAgeDays,
    )
    return ApiResponse(
        success=True,
        data=result.toDictionary(),
        message=(
            "Media cache cleanup evaluated."
            if request.dryRun
            else "Media cache cleaned."
        ),
        error=None,
    )


@router.post("/cache/reconcile", response_model=ApiResponse)
def reconcileMediaCache(
    request: ReconcileMediaCacheRequest,
    service: Annotated[
        Any,
        Depends(getMediaCacheReconciliationService),
    ],
) -> ApiResponse:
    result = service.reconcile(request.dryRun)
    return ApiResponse(
        success=True,
        data=result.toDictionary(),
        message=(
            "Media cache reconciliation evaluated."
            if request.dryRun
            else "Media cache reconciled."
        ),
        error=None,
    )
