import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.ai.errors import AIError
from app.media.errors import MediaError
from app.models.api_response import ApiError, ApiResponse
from app.pipeline.script_errors import ScriptError
from app.project.errors import ProjectError
from app.render.errors import RenderError
from app.timeline.errors import TimelineError

logger = logging.getLogger(__name__)

ERROR_STATUS_CODES = {
    "PROJECT_NOT_FOUND": 404,
    "PROJECT_PARENT_NOT_FOUND": 404,
    "INVALID_PROJECT_FILE": 422,
    "UNSUPPORTED_PROJECT_VERSION": 422,
    "INVALID_PROJECT_NAME": 422,
    "INVALID_RECENT_PROJECT_LIMIT": 422,
    "NO_ACTIVE_PROJECT": 409,
    "PROJECT_ALREADY_EXISTS": 409,
}

SCRIPT_ERROR_STATUS_CODES = {
    "SCRIPT_FILE_NOT_FOUND": 404,
    "SCRIPT_FILE_TOO_LARGE": 413,
    "UNSUPPORTED_SCRIPT_FORMAT": 415,
    "INVALID_SCRIPT_ENCODING": 422,
    "EMPTY_SCRIPT": 422,
    "INVALID_SRT_BLOCK": 422,
    "INVALID_SRT_INDEX": 422,
    "INVALID_SRT_TIMESTAMP": 422,
    "INVALID_SRT_DURATION": 422,
    "INVALID_SRT_TEXT": 422,
    "INVALID_SRT_ORDER": 422,
    "NO_SCENES_GENERATED": 422,
    "SCENES_NOT_FOUND": 404,
    "INVALID_SCENES_FILE": 422,
    "SCENE_NOT_FOUND": 404,
    "INVALID_SCENE_TEXT": 422,
}

AI_ERROR_STATUS_CODES = {
    "SCENE_NOT_FOUND": 404,
    "AI_PROVIDER_NOT_FOUND": 404,
    "INVALID_SCENE_ANALYSIS_INPUT": 422,
    "INVALID_AI_REQUEST": 422,
    "AI_PROVIDER_UNAVAILABLE": 503,
    "AI_PROVIDER_NOT_CONFIGURED": 503,
    "AI_PROVIDER_TIMEOUT": 504,
    "AI_PROVIDER_RATE_LIMITED": 429,
    "AI_PROVIDER_AUTHENTICATION_FAILED": 401,
    "AI_PROVIDER_REQUEST_REJECTED": 422,
    "AI_MODEL_NOT_FOUND": 404,
    "AI_MODEL_NOT_CONFIGURED": 422,
    "AI_PROVIDER_REQUEST_FAILED": 502,
    "INVALID_AI_PROVIDER_RESPONSE": 502,
    "INVALID_AI_RESPONSE": 502,
    "INVALID_SCENE_ANALYSIS_FILE": 422,
}

MEDIA_ERROR_STATUS_CODES = {
    "MEDIA_PROVIDER_NOT_FOUND": 404,
    "MEDIA_LIBRARY_NOT_FOUND": 404,
    "MEDIA_LIBRARY_NOT_CONFIGURED": 503,
    "MEDIA_PROVIDER_NOT_CONFIGURED": 503,
    "MEDIA_PROVIDER_UNAVAILABLE": 503,
    "MEDIA_PROVIDER_TIMEOUT": 504,
    "MEDIA_PROVIDER_RATE_LIMITED": 429,
    "MEDIA_PROVIDER_AUTHENTICATION_FAILED": 401,
    "MEDIA_PROVIDER_REQUEST_REJECTED": 422,
    "MEDIA_PROVIDER_REQUEST_FAILED": 502,
    "INVALID_MEDIA_PROVIDER_RESPONSE": 502,
    "MEDIA_PROVIDER_NOT_CACHEABLE": 422,
    "MEDIA_SOURCE_NOT_FOUND": 404,
    "MEDIA_FILE_TOO_LARGE": 413,
    "MEDIA_DOWNLOAD_TIMEOUT": 504,
    "MEDIA_DOWNLOAD_FAILED": 502,
    "MEDIA_CACHE_WRITE_FAILED": 500,
    "MEDIA_CACHE_MANIFEST_WRITE_FAILED": 500,
    "MEDIA_CACHE_CLEANUP_FAILED": 500,
    "MEDIA_CACHE_RECONCILIATION_FAILED": 500,
    "INVALID_MEDIA_CACHE_MANIFEST": 422,
    "INVALID_MEDIA_CACHE_POLICY": 422,
    "NO_ACTIVE_PROJECT": 409,
    "INVALID_MEDIA_PROVIDER_ID": 422,
    "INVALID_MEDIA_QUERY": 422,
    "INVALID_MEDIA_TYPES": 422,
    "INVALID_MEDIA_LIMIT": 422,
    "INVALID_MEDIA_OFFSET": 422,
    "INVALID_MEDIA_ID": 422,
    "INVALID_MEDIA_SOURCE": 422,
}

TIMELINE_ERROR_STATUS_CODES = {
    "CACHED_MEDIA_NOT_FOUND": 404,
    "TIMELINE_NOT_FOUND": 404,
    "TIMELINE_SCENE_NOT_FOUND": 404,
    "UNSUPPORTED_CACHED_MEDIA": 422,
    "VIDEO_SOURCE_TOO_SHORT": 422,
    "VIDEO_DURATION_UNAVAILABLE": 422,
    "INVALID_VIDEO_TRIM": 422,
    "TIMELINE_VIDEO_NOT_FOUND": 404,
    "INVALID_TIMELINE": 422,
    "INVALID_TIMELINE_FILE": 422,
    "TIMELINE_SAVE_FAILED": 500,
    "TIMELINE_READ_FAILED": 500,
}

RENDER_ERROR_STATUS_CODES = {
    "NO_ACTIVE_PROJECT": 409,
    "RENDER_ASSET_NOT_FOUND": 404,
    "RENDER_JOB_NOT_FOUND": 404,
    "INVALID_RENDER_FILE_NAME": 422,
    "INVALID_RENDER_OUTPUT_TEMPLATE": 422,
    "INVALID_RENDER_SETTINGS": 422,
    "RENDER_JOB_ALREADY_RUNNING": 409,
    "RENDER_JOB_NOT_RESUMABLE": 409,
    "RENDER_CANCELLED": 409,
    "RENDER_INTERRUPTED": 409,
    "FFMPEG_NOT_FOUND": 503,
    "FFPROBE_NOT_FOUND": 503,
    "INVALID_RENDER_TIMELINE": 422,
    "RENDER_PROCESS_START_FAILED": 500,
    "RENDER_FAILED": 500,
    "RENDER_OUTPUT_NOT_WRITABLE": 500,
    "RENDER_OUTPUT_WRITE_FAILED": 500,
    "RENDER_QUEUE_SAVE_FAILED": 500,
    "RENDER_QUEUE_READ_FAILED": 500,
    "INVALID_RENDER_QUEUE_FILE": 422,
}


def registerErrorHandlers(app: FastAPI) -> None:
    @app.exception_handler(ProjectError)
    async def handleProjectError(
        _request: Request, error: ProjectError
    ) -> JSONResponse:
        statusCode = ERROR_STATUS_CODES.get(error.code, 500)
        if statusCode >= 500:
            logger.error("Project operation failed: %s %s", error.code, error.message)
        return JSONResponse(
            status_code=statusCode,
            content=ApiResponse(
                success=False,
                data=None,
                message="",
                error=ApiError(code=error.code, message=error.message),
            ).model_dump(),
        )

    @app.exception_handler(ScriptError)
    async def handleScriptError(_request: Request, error: ScriptError) -> JSONResponse:
        statusCode = SCRIPT_ERROR_STATUS_CODES.get(error.code, 500)
        if statusCode >= 500:
            logger.error("Script operation failed: %s %s", error.code, error.message)
        return JSONResponse(
            status_code=statusCode,
            content=ApiResponse(
                success=False,
                data=None,
                message="",
                error=ApiError(code=error.code, message=error.message),
            ).model_dump(),
        )

    @app.exception_handler(AIError)
    async def handleAIError(_request: Request, error: AIError) -> JSONResponse:
        statusCode = AI_ERROR_STATUS_CODES.get(error.code, 500)
        if statusCode >= 500:
            logger.error("AI operation failed: %s %s", error.code, error.message)
        return JSONResponse(
            status_code=statusCode,
            content=ApiResponse(
                success=False,
                data=None,
                message="",
                error=ApiError(code=error.code, message=error.message),
            ).model_dump(),
        )

    @app.exception_handler(MediaError)
    async def handleMediaError(_request: Request, error: MediaError) -> JSONResponse:
        statusCode = MEDIA_ERROR_STATUS_CODES.get(error.code, 500)
        if statusCode >= 500:
            logger.error("Media operation failed: %s %s", error.code, error.message)
        return JSONResponse(
            status_code=statusCode,
            content=ApiResponse(
                success=False,
                data=None,
                message="",
                error=ApiError(code=error.code, message=error.message),
            ).model_dump(),
        )

    @app.exception_handler(TimelineError)
    async def handleTimelineError(
        _request: Request, error: TimelineError
    ) -> JSONResponse:
        statusCode = TIMELINE_ERROR_STATUS_CODES.get(error.code, 500)
        if statusCode >= 500:
            logger.error("Timeline operation failed: %s %s", error.code, error.message)
        return JSONResponse(
            status_code=statusCode,
            content=ApiResponse(
                success=False,
                data=None,
                message="",
                error=ApiError(code=error.code, message=error.message),
            ).model_dump(),
        )

    @app.exception_handler(RenderError)
    async def handleRenderError(_request: Request, error: RenderError) -> JSONResponse:
        statusCode = RENDER_ERROR_STATUS_CODES.get(error.code, 500)
        if statusCode >= 500:
            logger.error("Render operation failed: %s %s", error.code, error.message)
        return JSONResponse(
            status_code=statusCode,
            content=ApiResponse(
                success=False,
                data=None,
                message="",
                error=ApiError(code=error.code, message=error.message),
            ).model_dump(),
        )
