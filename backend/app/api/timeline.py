from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.config.dependencies import getTimelineMediaService, getTimelineService
from app.models.api_response import ApiResponse
from app.timeline.models import (
    AudioClip,
    MediaClip,
    SubtitleClip,
    Timeline,
    TimelineMediaType,
    TimelineScene,
    VisualClipRole,
)

router = APIRouter(prefix="/timeline", tags=["timeline"])


class MediaClipRequest(BaseModel):
    id: str = Field(min_length=1)
    contentHash: str
    mediaType: TimelineMediaType
    startMilliseconds: int
    endMilliseconds: int
    layer: int = 0
    sourceStartMilliseconds: int | None = None
    sourceEndMilliseconds: int | None = None
    role: VisualClipRole = VisualClipRole.BROLL


class AudioClipRequest(BaseModel):
    id: str = Field(min_length=1)
    contentHash: str
    startMilliseconds: int
    endMilliseconds: int
    sourceStartMilliseconds: int
    sourceEndMilliseconds: int
    volume: float = Field(default=0.2, ge=0, le=1)
    loop: bool = True
    layer: int = 0


class SubtitleClipRequest(BaseModel):
    id: str = Field(min_length=1)
    text: str
    startMilliseconds: int
    endMilliseconds: int
    layer: int = 0


class TimelineSceneRequest(BaseModel):
    sceneId: str = Field(min_length=1)
    order: int
    startMilliseconds: int
    endMilliseconds: int
    mediaClips: list[MediaClipRequest] = Field(default_factory=list)
    subtitleClips: list[SubtitleClipRequest] = Field(default_factory=list)


class SaveTimelineRequest(BaseModel):
    schemaVersion: int
    id: str = Field(min_length=1)
    createdAt: datetime
    updatedAt: datetime
    scenes: list[TimelineSceneRequest] = Field(min_length=1)
    audioClips: list[AudioClipRequest] = Field(default_factory=list)

    def toTimeline(self) -> Timeline:
        return Timeline(
            id=self.id,
            scenes=tuple(self._toScene(scene) for scene in self.scenes),
            createdAt=self.createdAt,
            updatedAt=self.updatedAt,
            schemaVersion=self.schemaVersion,
            audioClips=tuple(
                AudioClip(**clip.model_dump()) for clip in self.audioClips
            ),
        )

    def _toScene(self, scene: TimelineSceneRequest) -> TimelineScene:
        return TimelineScene(
            sceneId=scene.sceneId,
            order=scene.order,
            startMilliseconds=scene.startMilliseconds,
            endMilliseconds=scene.endMilliseconds,
            mediaClips=tuple(
                MediaClip(**clip.model_dump()) for clip in scene.mediaClips
            ),
            subtitleClips=tuple(
                SubtitleClip(**clip.model_dump()) for clip in scene.subtitleClips
            ),
        )


class AssignMediaRequest(BaseModel):
    contentHash: str | None = Field(default=None, min_length=64, max_length=64)
    role: VisualClipRole = VisualClipRole.BROLL


class AssignMediaBatchItem(BaseModel):
    sceneId: str = Field(min_length=1)
    contentHash: str | None = Field(default=None, min_length=64, max_length=64)
    role: VisualClipRole = VisualClipRole.BROLL


class AssignMediaBatchRequest(BaseModel):
    assignments: list[AssignMediaBatchItem] = Field(min_length=1)


class TrimVideoRequest(BaseModel):
    sourceStartMilliseconds: int
    sourceEndMilliseconds: int
    role: VisualClipRole = VisualClipRole.BROLL


class AssignMusicRequest(BaseModel):
    contentHash: str | None = Field(default=None, min_length=64, max_length=64)
    volume: float = Field(default=0.2, ge=0, le=1)


@router.get("", response_model=ApiResponse)
def getTimeline(
    service: Annotated[Any, Depends(getTimelineService)],
) -> ApiResponse:
    return timelineResponse(service.getTimeline(), "Timeline loaded.")


@router.post("/generate", response_model=ApiResponse, status_code=201)
def generateTimeline(
    service: Annotated[Any, Depends(getTimelineService)],
) -> ApiResponse:
    return timelineResponse(service.createInitialTimeline(), "Timeline generated.")


@router.put("", response_model=ApiResponse)
def saveTimeline(
    request: SaveTimelineRequest,
    service: Annotated[Any, Depends(getTimelineService)],
) -> ApiResponse:
    return timelineResponse(
        service.saveTimeline(request.toTimeline()), "Timeline saved."
    )


@router.get("/media-assets", response_model=ApiResponse)
def listMediaAssets(
    service: Annotated[Any, Depends(getTimelineMediaService)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int | None, Query(ge=1, le=250)] = None,
) -> ApiResponse:
    assetPage = service.listAssetPage(offset, limit)
    return ApiResponse(
        success=True,
        data=assetPage.toDictionary(),
        message="Cached timeline media loaded.",
        error=None,
    )


@router.put("/scenes/{sceneId}/media", response_model=ApiResponse)
def assignSceneMedia(
    sceneId: str,
    request: AssignMediaRequest,
    service: Annotated[Any, Depends(getTimelineMediaService)],
) -> ApiResponse:
    timeline = service.assignVisualMedia(sceneId, request.role, request.contentHash)
    return timelineResponse(timeline, "Scene media updated.")


@router.put("/media-assignments", response_model=ApiResponse)
def assignSceneMediaBatch(
    request: AssignMediaBatchRequest,
    service: Annotated[Any, Depends(getTimelineMediaService)],
) -> ApiResponse:
    from app.services.timeline_media_service import VisualMediaAssignment

    timeline = service.assignVisualMediaBatch(
        tuple(
            VisualMediaAssignment(
                item.sceneId,
                item.role,
                item.contentHash,
            )
            for item in request.assignments
        )
    )
    return timelineResponse(timeline, "Scene media assignments updated.")


@router.put("/scenes/{sceneId}/media-trim", response_model=ApiResponse)
def trimSceneMedia(
    sceneId: str,
    request: TrimVideoRequest,
    service: Annotated[Any, Depends(getTimelineMediaService)],
) -> ApiResponse:
    timeline = service.trimVisualVideo(
        sceneId,
        request.role,
        request.sourceStartMilliseconds,
        request.sourceEndMilliseconds,
    )
    return timelineResponse(timeline, "Video source range updated.")


@router.put("/music", response_model=ApiResponse)
def assignMusic(
    request: AssignMusicRequest,
    service: Annotated[Any, Depends(getTimelineMediaService)],
) -> ApiResponse:
    timeline = service.assignMusic(request.contentHash, request.volume)
    return timelineResponse(timeline, "Timeline music updated.")


def timelineResponse(timeline: Timeline, message: str) -> ApiResponse:
    return ApiResponse(
        success=True, data=timeline.toDictionary(), message=message, error=None
    )
