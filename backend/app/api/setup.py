from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.config.dependencies import getSetupService
from app.models.api_response import ApiResponse

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status", response_model=ApiResponse)
async def getSetupStatus(
    service: Annotated[Any, Depends(getSetupService)],
) -> ApiResponse:
    status = await service.getStatus()
    return ApiResponse(
        success=True,
        data=status.toDictionary(),
        message="Setup status loaded.",
        error=None,
    )
