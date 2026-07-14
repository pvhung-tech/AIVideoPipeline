from typing import Annotated

from fastapi import APIRouter, Depends

from app.models.api_response import ApiResponse
from app.services.health_service import HealthService, getHealthService

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=ApiResponse)
def getHealth(
    healthService: Annotated[HealthService, Depends(getHealthService)],
) -> ApiResponse:
    return ApiResponse(
        success=True,
        data=healthService.getStatus(),
        message="Backend is healthy.",
        error=None,
    )
