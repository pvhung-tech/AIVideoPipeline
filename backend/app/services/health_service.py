from app.config.settings import AppSettings, getSettings


class HealthService:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def getStatus(self) -> dict[str, str]:
        return {
            "appName": self._settings.appName,
            "environment": self._settings.environment,
            "status": "ok",
        }


def getHealthService() -> HealthService:
    return HealthService(getSettings())
