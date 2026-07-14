from pathlib import Path

from app.repositories.json_search_cache_repository import JsonSearchCacheRepository


class WikimediaSearchCacheRepository(JsonSearchCacheRepository):
    def __init__(self, cacheDirectory: Path) -> None:
        super().__init__(cacheDirectory, "Wikimedia")

    def makeKey(self, endpoint: str, text: str, offset: int, batchSize: int) -> str:
        return self.hashKey(
            {
                "endpoint": endpoint,
                "query": text,
                "offset": offset,
                "batchSize": batchSize,
                "namespace": 6,
                "metadataVersion": 1,
            }
        )
