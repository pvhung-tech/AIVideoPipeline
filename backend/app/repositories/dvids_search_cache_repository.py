from pathlib import Path
from typing import Any

from app.repositories.json_search_cache_repository import JsonSearchCacheRepository


class DvidsSearchCacheRepository(JsonSearchCacheRepository):
    def __init__(self, cacheDirectory: Path) -> None:
        super().__init__(cacheDirectory, "DVIDS")

    def makeKey(self, endpoint: str, params: dict[str, Any]) -> str:
        safeParams = {
            key: value for key, value in params.items() if key.lower() != "api_key"
        }
        return self.hashKey(
            {
                "endpoint": endpoint,
                "params": safeParams,
                "responseSchemaVersion": 1,
            }
        )
