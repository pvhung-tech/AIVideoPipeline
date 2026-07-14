from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.config.dependencies import getRenderJobService, getRenderService
from app.models.api_response import ApiResponse
from app.render.models import (
    RENDER_PROFILES,
    RenderExportSettings,
    renderProfileSettings,
)

router = APIRouter(prefix="/render", tags=["render"])


class StartRenderRequest(BaseModel):
    fileName: str | None = Field(default=None, min_length=5, max_length=124)
    outputNameTemplate: str = Field(
        default="{project}-{datetime}.mp4", min_length=1, max_length=124
    )
    profileId: Literal[
        "fast_preview", "draft", "standard", "high_quality", "archive"
    ] = "standard"
    width: int | None = Field(default=None, ge=320, le=7680)
    height: int | None = Field(default=None, ge=180, le=4320)
    frameRate: int | None = Field(default=None, ge=1, le=120)
    crf: int | None = Field(default=None, ge=0, le=51)
    encoderPreset: (
        Literal[
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
        ]
        | None
    ) = None
    audioBitrateKbps: int | None = Field(default=None, ge=64, le=512)

    def toExportSettings(self) -> RenderExportSettings:
        profileSettings = renderProfileSettings(self.profileId)
        settings = RenderExportSettings(
            self.width if self.width is not None else profileSettings.width,
            self.height if self.height is not None else profileSettings.height,
            self.frameRate if self.frameRate is not None else profileSettings.frameRate,
            self.crf if self.crf is not None else profileSettings.crf,
            (
                self.encoderPreset
                if self.encoderPreset is not None
                else profileSettings.encoderPreset
            ),
            (
                self.audioBitrateKbps
                if self.audioBitrateKbps is not None
                else profileSettings.audioBitrateKbps
            ),
            self.profileId,
        )
        if settings.toDictionary() == profileSettings.toDictionary():
            return settings
        return RenderExportSettings(
            settings.width,
            settings.height,
            settings.frameRate,
            settings.crf,
            settings.encoderPreset,
            settings.audioBitrateKbps,
            "custom",
        )


class CleanupRenderJobsRequest(BaseModel):
    keepCount: int = Field(default=100, ge=0, le=1000)


class ReviewRenderJobRequest(BaseModel):
    status: Literal["accepted", "rejected"]
    note: str | None = Field(default=None, max_length=1000)


class RenderQueueReportRequest(BaseModel):
    format: Literal["csv", "json"] = "csv"
    reviewStatus: Literal["all", "accepted", "rejected", "not_reviewed"] = "all"
    jobStatus: Literal[
        "all",
        "queued",
        "running",
        "cancelling",
        "completed",
        "cancelled",
        "failed",
        "interrupted",
    ] = "all"
    dateFrom: str | None = Field(default=None, max_length=32)
    dateTo: str | None = Field(default=None, max_length=32)


class RenderBundleReviewImportRequest(BaseModel):
    manifestPath: str = Field(min_length=1, max_length=512)


class RenderBundleImportReportCompareRequest(BaseModel):
    baseReportPath: str = Field(min_length=1, max_length=512)
    compareReportPath: str = Field(min_length=1, max_length=512)


class RenderBundleImportComparisonReportRequest(RenderBundleImportReportCompareRequest):
    format: Literal["csv", "json"] = "csv"
    changeFilter: Literal["all", "changed", "added", "removed"] = "all"


class RenderBundleImportComparisonReportPreviewRequest(BaseModel):
    reportPath: str = Field(min_length=1, max_length=512)
    maxRows: int = Field(default=25, ge=1, le=100)


class RenderBundleImportComparisonReportPinRequest(BaseModel):
    reportPath: str = Field(min_length=1, max_length=512)
    pinned: bool


@router.get("/profiles", response_model=ApiResponse)
def listRenderProfiles() -> ApiResponse:
    return ApiResponse(
        success=True,
        data={
            "profiles": [profile.toDictionary() for profile in RENDER_PROFILES.values()]
        },
        message="Render profiles loaded.",
        error=None,
    )


@router.post("", response_model=ApiResponse)
def renderTimeline(
    request: StartRenderRequest,
    service: Annotated[Any, Depends(getRenderService)],
) -> ApiResponse:
    result = service.render(
        request.fileName, request.toExportSettings(), request.outputNameTemplate
    )
    return ApiResponse(
        success=True,
        data=result.toDictionary(),
        message="Timeline rendered.",
        error=None,
    )


@router.post("/preflight", response_model=ApiResponse)
def checkRenderPreflight(
    request: StartRenderRequest,
    service: Annotated[Any, Depends(getRenderService)],
) -> ApiResponse:
    report = service.checkRenderPreflight(
        request.fileName, request.toExportSettings(), request.outputNameTemplate
    )
    return ApiResponse(
        success=True,
        data=report.toDictionary(),
        message="Render preflight checked.",
        error=None,
    )


@router.post("/jobs", response_model=ApiResponse)
def startRenderJob(
    request: StartRenderRequest,
    service: Annotated[Any, Depends(getRenderJobService)],
) -> ApiResponse:
    job = service.startRender(
        request.fileName, request.toExportSettings(), request.outputNameTemplate
    )
    return ApiResponse(
        success=True,
        data=job.toDictionary(),
        message="Render job started.",
        error=None,
    )


@router.get("/jobs", response_model=ApiResponse)
def listRenderJobs(
    service: Annotated[Any, Depends(getRenderJobService)],
) -> ApiResponse:
    queue = service.listJobs()
    return ApiResponse(
        success=True,
        data=queue.toDictionary(),
        message="Render jobs loaded.",
        error=None,
    )


@router.post("/jobs/report", response_model=ApiResponse)
def exportRenderQueueReport(
    request: RenderQueueReportRequest,
    service: Annotated[Any, Depends(getRenderJobService)],
) -> ApiResponse:
    report = service.exportQueueReport(
        request.format,
        request.reviewStatus,
        request.jobStatus,
        request.dateFrom,
        request.dateTo,
    )
    return ApiResponse(
        success=True,
        data=report,
        message="Render queue report exported.",
        error=None,
    )


@router.post("/jobs/report/bundle", response_model=ApiResponse)
def exportRenderQueueHandoffBundle(
    request: RenderQueueReportRequest,
    service: Annotated[Any, Depends(getRenderJobService)],
) -> ApiResponse:
    bundle = service.exportQueueHandoffBundle(
        request.reviewStatus,
        request.jobStatus,
        request.dateFrom,
        request.dateTo,
    )
    return ApiResponse(
        success=True,
        data=bundle,
        message="Render queue handoff bundle exported.",
        error=None,
    )


@router.post("/jobs/report/bundle/import-review", response_model=ApiResponse)
def importRenderQueueHandoffBundleReviews(
    request: RenderBundleReviewImportRequest,
    service: Annotated[Any, Depends(getRenderJobService)],
) -> ApiResponse:
    result = service.importBundleReviews(request.manifestPath)
    return ApiResponse(
        success=True,
        data=result,
        message="Render bundle reviews imported.",
        error=None,
    )


@router.get("/jobs/report/bundle/imports", response_model=ApiResponse)
def listRenderQueueHandoffBundleImportReports(
    service: Annotated[Any, Depends(getRenderJobService)],
) -> ApiResponse:
    reports = service.listBundleImportReports()
    return ApiResponse(
        success=True,
        data=reports,
        message="Render bundle import reports loaded.",
        error=None,
    )


@router.post("/jobs/report/bundle/imports/compare", response_model=ApiResponse)
def compareRenderQueueHandoffBundleImportReports(
    request: RenderBundleImportReportCompareRequest,
    service: Annotated[Any, Depends(getRenderJobService)],
) -> ApiResponse:
    comparison = service.compareBundleImportReports(
        request.baseReportPath, request.compareReportPath
    )
    return ApiResponse(
        success=True,
        data=comparison,
        message="Render bundle import reports compared.",
        error=None,
    )


@router.post("/jobs/report/bundle/imports/compare/report", response_model=ApiResponse)
def exportRenderQueueHandoffBundleImportComparisonReport(
    request: RenderBundleImportComparisonReportRequest,
    service: Annotated[Any, Depends(getRenderJobService)],
) -> ApiResponse:
    report = service.exportBundleImportComparisonReport(
        request.baseReportPath,
        request.compareReportPath,
        request.format,
        request.changeFilter,
    )
    return ApiResponse(
        success=True,
        data=report,
        message="Render bundle import comparison report exported.",
        error=None,
    )


@router.get("/jobs/report/bundle/imports/compare/reports", response_model=ApiResponse)
def listRenderQueueHandoffBundleImportComparisonReports(
    service: Annotated[Any, Depends(getRenderJobService)],
) -> ApiResponse:
    reports = service.listBundleImportComparisonReports()
    return ApiResponse(
        success=True,
        data=reports,
        message="Render bundle import comparison reports loaded.",
        error=None,
    )


@router.post(
    "/jobs/report/bundle/imports/compare/reports/preview",
    response_model=ApiResponse,
)
def previewRenderQueueHandoffBundleImportComparisonReport(
    request: RenderBundleImportComparisonReportPreviewRequest,
    service: Annotated[Any, Depends(getRenderJobService)],
) -> ApiResponse:
    preview = service.previewBundleImportComparisonReport(
        request.reportPath, request.maxRows
    )
    return ApiResponse(
        success=True,
        data=preview,
        message="Render bundle import comparison report preview loaded.",
        error=None,
    )


@router.post(
    "/jobs/report/bundle/imports/compare/reports/pin",
    response_model=ApiResponse,
)
def pinRenderQueueHandoffBundleImportComparisonReport(
    request: RenderBundleImportComparisonReportPinRequest,
    service: Annotated[Any, Depends(getRenderJobService)],
) -> ApiResponse:
    result = service.setBundleImportComparisonReportPinned(
        request.reportPath, request.pinned
    )
    return ApiResponse(
        success=True,
        data=result,
        message="Render bundle import comparison report pin updated.",
        error=None,
    )


@router.get("/jobs/{jobId}", response_model=ApiResponse)
def getRenderJob(
    jobId: str,
    service: Annotated[Any, Depends(getRenderJobService)],
) -> ApiResponse:
    job = service.getJob(jobId)
    return ApiResponse(
        success=True,
        data=job.toDictionary(),
        message="Render job loaded.",
        error=None,
    )


@router.post("/jobs/{jobId}/resume", response_model=ApiResponse)
def resumeRenderJob(
    jobId: str,
    service: Annotated[Any, Depends(getRenderJobService)],
) -> ApiResponse:
    job = service.resumeJob(jobId)
    return ApiResponse(
        success=True,
        data=job.toDictionary(),
        message="Render job resumed.",
        error=None,
    )


@router.post("/jobs/{jobId}/retry", response_model=ApiResponse)
def retryRenderJob(
    jobId: str,
    service: Annotated[Any, Depends(getRenderJobService)],
) -> ApiResponse:
    job = service.retryJob(jobId)
    return ApiResponse(
        success=True,
        data=job.toDictionary(),
        message="Render job retried.",
        error=None,
    )


@router.post("/jobs/{jobId}/cancel", response_model=ApiResponse)
def cancelRenderJob(
    jobId: str,
    service: Annotated[Any, Depends(getRenderJobService)],
) -> ApiResponse:
    job = service.cancelJob(jobId)
    return ApiResponse(
        success=True,
        data=job.toDictionary(),
        message="Render job cancellation requested.",
        error=None,
    )


@router.post("/jobs/{jobId}/review", response_model=ApiResponse)
def reviewRenderJob(
    jobId: str,
    request: ReviewRenderJobRequest,
    service: Annotated[Any, Depends(getRenderJobService)],
) -> ApiResponse:
    job = service.reviewJob(jobId, request.status, request.note)
    return ApiResponse(
        success=True,
        data=job.toDictionary(),
        message="Render job review saved.",
        error=None,
    )


@router.delete("/jobs/{jobId}/review", response_model=ApiResponse)
def clearRenderJobReview(
    jobId: str,
    service: Annotated[Any, Depends(getRenderJobService)],
) -> ApiResponse:
    job = service.clearReviewJob(jobId)
    return ApiResponse(
        success=True,
        data=job.toDictionary(),
        message="Render job review cleared.",
        error=None,
    )


@router.post("/jobs/cleanup", response_model=ApiResponse)
def cleanupRenderJobs(
    request: CleanupRenderJobsRequest,
    service: Annotated[Any, Depends(getRenderJobService)],
) -> ApiResponse:
    queue = service.cleanupHistory(request.keepCount)
    return ApiResponse(
        success=True,
        data=queue.toDictionary(),
        message="Render job history cleaned.",
        error=None,
    )
