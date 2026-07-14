from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.config.dependencies import (
    getMediaFingerprintBackfillService,
    getMediaMetadataBackfillService,
    getProjectService,
)
from app.models.api_response import ApiResponse
from app.project.project_model import Project

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parentDirectory: str = Field(min_length=1)


class OpenProjectRequest(BaseModel):
    path: str = Field(min_length=1)


class SaveProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)


@router.post("", response_model=ApiResponse, status_code=201)
def createProject(
    request: CreateProjectRequest,
    service: Annotated[Any, Depends(getProjectService)],
) -> ApiResponse:
    project = service.createProject(request.name, Path(request.parentDirectory))
    return projectResponse(project, "Project created.")


@router.post("/open", response_model=ApiResponse)
def openProject(
    request: OpenProjectRequest,
    service: Annotated[Any, Depends(getProjectService)],
    backfillService: Annotated[
        Any, Depends(getMediaMetadataBackfillService)
    ],
    fingerprintBackfillService: Annotated[
        Any, Depends(getMediaFingerprintBackfillService)
    ],
) -> ApiResponse:
    project = service.openProject(Path(request.path))
    backfillService.startForProject(project)
    fingerprintBackfillService.startForProject(project)
    return projectResponse(project, "Project opened.")


@router.get("/current", response_model=ApiResponse)
def getCurrentProject(
    service: Annotated[Any, Depends(getProjectService)],
) -> ApiResponse:
    project = service.getCurrentProject()
    return ApiResponse(
        success=True,
        data=project.toDictionary() if project else None,
        message="Current project loaded." if project else "No project is open.",
        error=None,
    )


@router.put("/current", response_model=ApiResponse)
def saveCurrentProject(
    request: SaveProjectRequest,
    service: Annotated[Any, Depends(getProjectService)],
) -> ApiResponse:
    project = service.saveCurrentProject(request.name)
    return projectResponse(project, "Project saved.")


@router.post("/close", response_model=ApiResponse)
def closeProject(
    service: Annotated[Any, Depends(getProjectService)],
) -> ApiResponse:
    project = service.closeProject()
    return projectResponse(project, "Project closed.")


@router.get("/recent", response_model=ApiResponse)
def listRecentProjects(
    service: Annotated[Any, Depends(getProjectService)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> ApiResponse:
    projects = service.listRecentProjects(limit)
    return ApiResponse(
        success=True,
        data={"projects": [project.toDictionary() for project in projects]},
        message="Recent projects loaded.",
        error=None,
    )


def projectResponse(project: Project, message: str) -> ApiResponse:
    return ApiResponse(
        success=True,
        data=project.toDictionary(),
        message=message,
        error=None,
    )
