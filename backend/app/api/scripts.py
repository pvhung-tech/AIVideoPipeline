from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.config.dependencies import getSceneService, getScriptService
from app.models.api_response import ApiResponse

router = APIRouter(prefix="/scripts", tags=["scripts"])


class ImportScriptRequest(BaseModel):
    path: str = Field(min_length=1)


class UpdateSceneRequest(BaseModel):
    text: str


@router.post("/import", response_model=ApiResponse)
def importScript(
    request: ImportScriptRequest,
    service: Annotated[Any, Depends(getScriptService)],
) -> ApiResponse:
    document = service.importScript(Path(request.path))
    return ApiResponse(
        success=True,
        data=document.toDictionary(),
        message="Script imported and validated.",
        error=None,
    )


@router.get("/scenes", response_model=ApiResponse)
def listScenes(
    service: Annotated[Any, Depends(getSceneService)],
) -> ApiResponse:
    collection = service.listScenes()
    return ApiResponse(
        success=True,
        data=collection.toDictionary(),
        message="Scenes loaded.",
        error=None,
    )


@router.put("/scenes/{sceneId}", response_model=ApiResponse)
def updateScene(
    sceneId: str,
    request: UpdateSceneRequest,
    service: Annotated[Any, Depends(getSceneService)],
) -> ApiResponse:
    collection = service.updateScene(sceneId, request.text)
    return ApiResponse(
        success=True,
        data=collection.toDictionary(),
        message="Scene updated.",
        error=None,
    )
