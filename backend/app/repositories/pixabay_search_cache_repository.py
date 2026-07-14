from pathlib import Path

from app.repositories.json_search_cache_repository import JsonSearchCacheRepository


class PixabaySearchCacheRepository(JsonSearchCacheRepository):
    def __init__(self, cacheDirectory: Path) -> None:
        super().__init__(cacheDirectory, "Pixabay")

    def makeKey(self, endpoint: str, text: str, page: int, pageSize: int) -> str:
        return self.hashKey(
            {
                "endpoint": endpoint,
                "query": text,
                "page": page,
                "perPage": pageSize,
                "safeSearch": True,
            }
        )
