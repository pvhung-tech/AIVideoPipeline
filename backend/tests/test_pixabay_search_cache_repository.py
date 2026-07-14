from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.repositories.pixabay_search_cache_repository import (
    PixabaySearchCacheRepository,
)


def testPixabaySearchCachePersistsAndExpiresResponses(tmp_path: Path) -> None:
    repository = PixabaySearchCacheRepository(tmp_path)
    key = repository.makeKey("/api/", "city", 1, 20)
    timestamp = datetime.now(UTC)
    response = {"totalHits": 1, "hits": [{"id": 1}]}

    repository.set(key, response, timestamp)

    restarted = PixabaySearchCacheRepository(tmp_path)
    assert restarted.get(key, timestamp + timedelta(hours=1), 86400) == response
    assert restarted.get(key, timestamp + timedelta(days=1), 86400) is None
    assert not (tmp_path / f"{key}.json").exists()


def testPixabaySearchCacheKeyExcludesApiCredentials(tmp_path: Path) -> None:
    repository = PixabaySearchCacheRepository(tmp_path)

    key = repository.makeKey("/api/videos/", "ocean", 2, 40)

    assert len(key) == 64
    assert "ocean" not in key


def testPixabaySearchCachePrunesExpiredEntries(tmp_path: Path) -> None:
    repository = PixabaySearchCacheRepository(tmp_path)
    key = repository.makeKey("https://pixabay.com/api/", "old", 1, 20)
    timestamp = datetime.now(UTC)
    repository.set(key, {"totalHits": 0, "hits": []}, timestamp)

    repository.pruneExpired(timestamp + timedelta(days=2), 86400)

    assert not (tmp_path / f"{key}.json").exists()
