from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.config.dependencies import getSceneAnalysisService
from app.models.api_response import ApiResponse

router = APIRouter(prefix="/ai", tags=["ai"])


class AnalyzeSceneRequest(BaseModel):
    contentType: str = Field(default="general", min_length=1, max_length=100)
    language: str = Field(default="English", min_length=1, max_length=100)
    providerId: str | None = Field(default=None, min_length=1, max_length=100)
    model: str | None = Field(default=None, min_length=1, max_length=200)


class AnalyzeSceneBatchRequest(AnalyzeSceneRequest):
    reanalyze: bool = False


@router.post("/scenes/{sceneId}/analyze", response_model=ApiResponse)
async def analyzeScene(
    sceneId: str,
    request: AnalyzeSceneRequest,
    service: Annotated[Any, Depends(getSceneAnalysisService)],
) -> ApiResponse:
    result = await service.analyzeScene(
        sceneId=sceneId,
        contentType=request.contentType,
        language=request.language,
        providerId=request.providerId,
        model=request.model,
    )
    return ApiResponse(
        success=True,
        data=result.toDictionary(),
        message="Scene analyzed.",
        error=None,
    )


@router.get("/scenes/analysis", response_model=ApiResponse)
def listSceneAnalyses(
    service: Annotated[Any, Depends(getSceneAnalysisService)],
) -> ApiResponse:
    collection = service.listAnalyses()
    return ApiResponse(
        success=True,
        data=collection.toDictionary(),
        message="Scene analyses loaded.",
        error=None,
    )


@router.post("/scenes/analyze", response_model=ApiResponse)
async def analyzeAllScenes(
    request: AnalyzeSceneBatchRequest,
    service: Annotated[Any, Depends(getSceneAnalysisService)],
) -> ApiResponse:
    result = await service.analyzeAllScenes(
        contentType=request.contentType,
        language=request.language,
        providerId=request.providerId,
        model=request.model,
        reanalyze=request.reanalyze,
    )
    return ApiResponse(
        success=True,
        data=result.toDictionary(),
        message="Scene batch analysis completed.",
        error=None,
    )
