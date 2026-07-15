from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.logging_config import configureLogging
from app.config.settings import getSettings


def createApp() -> FastAPI:
    from app.api.ai import router as aiRouter
    from app.api.error_handlers import registerErrorHandlers
    from app.api.health import router as healthRouter
    from app.api.media import router as mediaRouter
    from app.api.projects import router as projectsRouter
    from app.api.render import router as renderRouter
    from app.api.scripts import router as scriptsRouter
    from app.api.setup import router as setupRouter
    from app.api.timeline import router as timelineRouter

    settings = getSettings()
    configureLogging(settings)

    app = FastAPI(title=settings.appName)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://tauri.localhost",
            "tauri://localhost",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["*"],
    )
    registerErrorHandlers(app)
    app.include_router(healthRouter, prefix="/api")
    app.include_router(projectsRouter, prefix="/api")
    app.include_router(scriptsRouter, prefix="/api")
    app.include_router(aiRouter, prefix="/api")
    app.include_router(setupRouter, prefix="/api")
    app.include_router(mediaRouter, prefix="/api")
    app.include_router(timelineRouter, prefix="/api")
    app.include_router(renderRouter, prefix="/api")
    return app
