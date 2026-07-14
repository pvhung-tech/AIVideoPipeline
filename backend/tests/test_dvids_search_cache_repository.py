from pathlib import Path

from app.repositories.dvids_search_cache_repository import DvidsSearchCacheRepository


def testDvidsCacheKeyExcludesApiKeyAndSeparatesEndpoints(tmp_path: Path) -> None:
    repository = DvidsSearchCacheRepository(tmp_path)
    firstParams = {"q": "tank", "type": "video", "api_key": "key-first"}
    secondParams = {"q": "tank", "type": "video", "api_key": "key-second"}

    first = repository.makeKey("https://api.dvidshub.net/search", firstParams)
    repeated = repository.makeKey("https://api.dvidshub.net/search", secondParams)
    asset = repository.makeKey(
        "https://api.dvidshub.net/asset",
        {"id": "video:20", "api_key": "key-first"},
    )

    assert first == repeated
    assert first != asset
