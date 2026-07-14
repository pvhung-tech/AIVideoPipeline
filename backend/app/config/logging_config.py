import logging

from app.config.settings import AppSettings


def configureLogging(settings: AppSettings) -> None:
    logging.basicConfig(
        level=settings.logLevel,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
