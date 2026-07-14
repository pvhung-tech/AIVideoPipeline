import argparse
import logging
import os
import time
from collections.abc import Sequence

logger = logging.getLogger(__name__)


def buildParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FastAPI desktop sidecar")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    return parser


def runSidecar(arguments: Sequence[str] | None = None) -> None:
    startedAt = time.perf_counter()
    options = buildParser().parse_args(arguments)

    from app.main import createApp

    app = createApp()
    import uvicorn

    startupImportSeconds = time.perf_counter() - startedAt
    logger.info("Starting FastAPI desktop sidecar")
    logger.info("SIDECAR_PROCESS_ID=%s", os.getpid())
    logger.info("SIDECAR_STARTUP_IMPORT_SECONDS=%.4f", startupImportSeconds)
    uvicorn.run(
        app,
        host=options.host,
        port=options.port,
        http="h11",
        ws="none",
        loop="asyncio",
        lifespan="on",
        access_log=False,
    )


if __name__ == "__main__":
    runSidecar()
