from pathlib import Path

from app.repositories.wikimedia_search_cache_repository import (
    WikimediaSearchCacheRepository,
)


def testWikimediaCacheKeySeparatesQueryAndOffset(tmp_path: Path) -> None:
    repository = WikimediaSearchCacheRepository(tmp_path)

    first = repository.makeKey("https://commons.test/w/api.php", "city", 0, 50)
    repeated = repository.makeKey("https://commons.test/w/api.php", "city", 0, 50)
    nextPage = repository.makeKey("https://commons.test/w/api.php", "city", 50, 50)
    otherQuery = repository.makeKey("https://commons.test/w/api.php", "forest", 0, 50)

    assert first == repeated
    assert len({first, nextPage, otherQuery}) == 3
