import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

DEFAULT_PROVIDERS = ("pexels", "pixabay", "dvids")
DEFAULT_MEDIA_TYPES = ("image", "video")
DEFAULT_WORKSPACE_ASSET_WINDOW = 100


def main() -> None:
    query = os.environ.get("PHASE9_MEDIA_LIVE_QUERY", "city documentary")
    limit = int(os.environ.get("PHASE9_MEDIA_LIVE_LIMIT", "10"))
    largeLimit = int(os.environ.get("PHASE9_MEDIA_LIVE_LARGE_LIMIT", "40"))
    cacheSelectionLimit = int(os.environ.get("PHASE9_MEDIA_LIVE_CACHE_ITEMS", "3"))
    largeCacheEntries = int(os.environ.get("PHASE9_MEDIA_LIVE_CACHE_ENTRIES", "250"))
    refreshCacheSizes = parseCacheSizes(
        os.environ.get("PHASE9_MEDIA_LIVE_REFRESH_CACHE_SIZES", "250,1000,2500")
    )
    providers = tuple(
        provider.strip().lower()
        for provider in os.environ.get(
            "PHASE9_MEDIA_LIVE_PROVIDERS", ",".join(DEFAULT_PROVIDERS)
        ).split(",")
        if provider.strip()
    )
    outputPath = Path(
        os.environ.get(
            "PHASE9_MEDIA_LIVE_OUTPUT",
            str(Path("..") / ".tmp" / "phase9-media-live-search-cache.json"),
        )
    )
    outputPath.parent.mkdir(parents=True, exist_ok=True)
    result = runProbe(
        query,
        limit,
        largeLimit,
        cacheSelectionLimit,
        largeCacheEntries,
        refreshCacheSizes,
        providers,
        outputPath.parent,
    )
    result["benchmarkReportPath"] = str(outputPath)
    outputPath.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


def runProbe(
    query: str,
    limit: int,
    largeLimit: int,
    cacheSelectionLimit: int,
    largeCacheEntries: int,
    refreshCacheSizes: tuple[int, ...],
    providers: tuple[str, ...],
    outputDirectory: Path,
) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from app.main import createApp

    startedAt = time.time()
    with tempfile.TemporaryDirectory(
        prefix="phase9-media-live-", dir=outputDirectory, ignore_cleanup_errors=True
    ) as workspace:
        workspacePath = Path(workspace)
        previousEnvironment = captureEnvironment()
        os.environ["APP_DATA_DIR"] = str(workspacePath / "app-data")
        try:
            app = createApp()
            with TestClient(app) as client:
                project = createProject(client, workspacePath)
                providerRuns = [
                    measureRepeatedProvider(client, query, provider, limit)
                    for provider in providers
                ]
                mixedRuns = (
                    measureSearch(client, query, "all", limit),
                    measureSearch(client, query, "all", limit),
                )
                cacheRuns = measureSelectedItemCache(client, mixedRuns[1])
                manifestRefresh = measureManifestRefresh(client)
                cachedSelection = measureCachedSelectionUx(
                    client, mixedRuns[1], cacheSelectionLimit
                )
                refreshSeries = measureManifestRefreshSeries(client, 5)
                largeCacheSeed = seedLargeCacheManifest(
                    Path(project["path"]),
                    largeCacheEntries,
                    mixedRuns[1].get("sampleItems") or [],
                )
                largeCacheRefreshSeries = measureManifestRefreshSeries(client, 5)
                largeMixedRuns = (
                    measureSearch(client, query, "all", largeLimit),
                    measureSearch(client, query, "all", largeLimit),
                )
                syntheticRanking = measureSyntheticRankingMerge(
                    mixedRuns[1].get("sampleItems") or [],
                    largeCacheEntries,
                    max(largeLimit * len(providers), 120),
                )
                workspaceRefreshByCacheSize = measureWorkspaceRefreshByCacheSize(
                    client,
                    Path(project["path"]),
                    refreshCacheSizes,
                    mixedRuns[1].get("sampleItems") or [],
                )
        finally:
            restoreEnvironment(previousEnvironment)
        warmProviderSeconds = [
            run["warm"]["elapsedSeconds"]
            for run in providerRuns
            if run["warm"]["ok"] and run["warm"]["elapsedSeconds"] is not None
        ]
        mixedWarmSeconds = mixedRuns[1]["elapsedSeconds"]
        return {
            "probe": "phase9_media_live_search_cache",
            "query": query,
            "limit": limit,
            "mediaTypes": list(DEFAULT_MEDIA_TYPES),
            "providers": list(providers),
            "startedAtEpochSeconds": startedAt,
            "durationSeconds": round(time.time() - startedAt, 3),
            "projectCreated": project,
            "providerRepeatedSearches": providerRuns,
            "mixedProviderSearches": {
                "cold": mixedRuns[0],
                "warm": mixedRuns[1],
                "estimatedMergeRankOverheadSeconds": estimateMergeRankOverhead(
                    mixedWarmSeconds, warmProviderSeconds
                ),
            },
            "selectedItemCache": cacheRuns,
            "cachedSelectionUx": cachedSelection,
            "manifestRefresh": manifestRefresh,
            "manifestRefreshSeries": refreshSeries,
            "largeCacheProbe": {
                "targetEntries": largeCacheEntries,
                "seed": largeCacheSeed,
                "refreshSeries": largeCacheRefreshSeries,
                "mixedProviderSearches": {
                    "limit": largeLimit,
                    "cold": largeMixedRuns[0],
                    "warm": largeMixedRuns[1],
                },
                "syntheticRankingMerge": syntheticRanking,
            },
            "workspaceRefreshByCacheSize": workspaceRefreshByCacheSize,
            "workspaceSummary": {"artifactsRetained": False},
        }


def createProject(client: Any, workspacePath: Path) -> dict[str, Any]:
    parent = workspacePath / "projects"
    parent.mkdir(parents=True, exist_ok=True)
    response = client.post(
        "/api/projects",
        json={"name": "Phase 9 Media Live Probe", "parentDirectory": str(parent)},
    )
    payload = response.json()
    return {
        "ok": response.status_code < 400 and payload.get("success") is True,
        "statusCode": response.status_code,
        "errorCode": (payload.get("error") or {}).get("code"),
        "path": (payload.get("data") or {}).get("path"),
    }


def measureRepeatedProvider(
    client: Any, query: str, providerId: str, limit: int
) -> dict[str, Any]:
    cold = measureSearch(client, query, providerId, limit)
    warm = measureSearch(client, query, providerId, limit)
    improvement = None
    if cold["elapsedSeconds"] is not None and warm["elapsedSeconds"] is not None:
        improvement = round(cold["elapsedSeconds"] - warm["elapsedSeconds"], 4)
    return {
        "providerId": providerId,
        "cold": cold,
        "warm": warm,
        "warmMinusColdSeconds": improvement,
    }


def measureSearch(
    client: Any, query: str, providerId: str, limit: int
) -> dict[str, Any]:
    started = time.perf_counter()
    response = client.get(
        "/api/media/search",
        params=[
            ("query", query),
            ("providerId", providerId),
            ("limit", str(limit)),
            *[("mediaType", mediaType) for mediaType in DEFAULT_MEDIA_TYPES],
        ],
    )
    elapsed = round(time.perf_counter() - started, 4)
    payload = response.json()
    data = payload.get("data") or {}
    items = data.get("items") or []
    errors = data.get("providerErrors") or []
    return {
        "ok": response.status_code < 400 and payload.get("success") is True,
        "statusCode": response.status_code,
        "elapsedSeconds": elapsed,
        "itemCount": len(items),
        "totalResults": data.get("totalResults"),
        "truncated": data.get("truncated"),
        "providerErrors": errors,
        "deduplication": data.get("deduplication"),
        "firstItem": sanitizeItem(items[0]) if items else None,
        "sampleItems": [sanitizeItem(item) for item in items[: min(10, len(items))]],
        "errorCode": (payload.get("error") or {}).get("code"),
        "errorMessage": (payload.get("error") or {}).get("message"),
    }


def measureSelectedItemCache(
    client: Any, searchRun: dict[str, Any]
) -> dict[str, Any] | None:
    item = searchRun.get("firstItem")
    if not item:
        return None
    first = measureCache(client, item)
    duplicate = measureCache(client, item)
    return {"item": item, "first": first, "duplicate": duplicate}


def measureCachedSelectionUx(
    client: Any, searchRun: dict[str, Any], selectionLimit: int
) -> dict[str, Any]:
    items = (searchRun.get("sampleItems") or [])[:selectionLimit]
    runs = []
    for item in items:
        first = measureCache(client, item)
        reselect = measureCache(client, item)
        runs.append({"item": item, "first": first, "reselect": reselect})
    reselectSeconds = [
        run["reselect"]["elapsedSeconds"]
        for run in runs
        if run["reselect"]["elapsedSeconds"] is not None
    ]
    return {
        "requestedItems": selectionLimit,
        "measuredItems": len(runs),
        "runs": runs,
        "averageReselectSeconds": average(reselectSeconds),
        "maxReselectSeconds": max(reselectSeconds) if reselectSeconds else None,
    }


def measureCache(client: Any, item: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    response = client.post(
        "/api/media/cache",
        json={
            "providerId": item["providerId"],
            "mediaId": item["id"],
            "sourceUri": item["sourceUri"],
            "fileName": suggestedFileName(item),
        },
    )
    elapsed = round(time.perf_counter() - started, 4)
    payload = response.json()
    data = payload.get("data") or {}
    diagnostics = data.get("diagnostics") or {}
    return {
        "ok": response.status_code < 400 and payload.get("success") is True,
        "statusCode": response.status_code,
        "elapsedSeconds": elapsed,
        "duplicate": data.get("duplicate"),
        "sizeBytes": data.get("sizeBytes"),
        "diagnostics": {
            key: diagnostics.get(key)
            for key in (
                "providerId",
                "sourceTransferSeconds",
                "sourceHashSeconds",
                "sourceFileWriteSeconds",
                "duplicateCheckSeconds",
                "fingerprintSeconds",
                "metadataSeconds",
                "manifestSeconds",
                "totalSeconds",
                "fingerprintDeferred",
            )
        },
        "errorCode": (payload.get("error") or {}).get("code"),
        "errorMessage": (payload.get("error") or {}).get("message"),
    }


def measureManifestRefreshSeries(client: Any, count: int) -> dict[str, Any]:
    runs = [measureManifestRefresh(client) for _ in range(count)]
    seconds = [
        run["elapsedSeconds"] for run in runs if run.get("elapsedSeconds") is not None
    ]
    return {
        "count": count,
        "runs": runs,
        "averageSeconds": average(seconds),
        "maxSeconds": max(seconds) if seconds else None,
    }


def measureWorkspaceRefreshByCacheSize(
    client: Any,
    projectPath: Path,
    cacheSizes: tuple[int, ...],
    sourceItems: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    probes = []
    for cacheSize in cacheSizes:
        seed = seedLargeCacheManifest(projectPath, cacheSize, sourceItems)
        refresh = measureMediaWorkspaceRefreshSeries(client, 5)
        probes.append(
            {
                "targetEntries": cacheSize,
                "seed": seed,
                "refreshSeries": refresh,
            }
        )
    return probes


def measureMediaWorkspaceRefreshSeries(client: Any, count: int) -> dict[str, Any]:
    runs = [measureMediaWorkspaceRefresh(client) for _ in range(count)]
    seconds = [
        run["elapsedSeconds"] for run in runs if run.get("elapsedSeconds") is not None
    ]
    manifestSeconds = [
        run["manifestSeconds"] for run in runs if run.get("manifestSeconds") is not None
    ]
    timelineAssetsSeconds = [
        run["timelineAssetsSeconds"]
        for run in runs
        if run.get("timelineAssetsSeconds") is not None
    ]
    uiProjectionSeconds = [
        run["uiProjectionSeconds"]
        for run in runs
        if run.get("uiProjectionSeconds") is not None
    ]
    return {
        "count": count,
        "runs": runs,
        "averageSeconds": average(seconds),
        "maxSeconds": max(seconds) if seconds else None,
        "averageManifestSeconds": average(manifestSeconds),
        "averageTimelineAssetsSeconds": average(timelineAssetsSeconds),
        "averageUiProjectionSeconds": average(uiProjectionSeconds),
    }


def measureMediaWorkspaceRefresh(client: Any) -> dict[str, Any]:
    started = time.perf_counter()
    manifestStarted = time.perf_counter()
    manifestResponse = client.get("/api/media/cache")
    manifestSeconds = round(time.perf_counter() - manifestStarted, 4)
    manifestPayload = manifestResponse.json()
    manifestData = manifestPayload.get("data") or {}

    assetsStarted = time.perf_counter()
    assetsResponse = client.get(
        "/api/timeline/media-assets",
        params={
            "offset": "0",
            "limit": str(DEFAULT_WORKSPACE_ASSET_WINDOW),
        },
    )
    timelineAssetsSeconds = round(time.perf_counter() - assetsStarted, 4)
    assetsPayload = assetsResponse.json()
    assetsData = assetsPayload.get("data") or {}
    assets = assetsData.get("assets") or []

    uiProjectionStarted = time.perf_counter()
    visualAssets = [
        {
            "contentHash": asset.get("contentHash"),
            "fileName": asset.get("fileName"),
            "sizeBytes": asset.get("sizeBytes"),
            "providerIds": asset.get("providerIds") or [],
        }
        for asset in assets
        if asset.get("mediaType") != "audio"
    ]
    selectedHash = visualAssets[0]["contentHash"] if visualAssets else None
    uiProjectionSeconds = round(time.perf_counter() - uiProjectionStarted, 4)

    return {
        "ok": (
            manifestResponse.status_code < 400
            and manifestPayload.get("success") is True
            and assetsResponse.status_code < 400
            and assetsPayload.get("success") is True
        ),
        "elapsedSeconds": round(time.perf_counter() - started, 4),
        "manifestSeconds": manifestSeconds,
        "timelineAssetsSeconds": timelineAssetsSeconds,
        "uiProjectionSeconds": uiProjectionSeconds,
        "cacheEntryCount": len(manifestData.get("entries") or []),
        "assetCount": len(assets),
        "visualAssetCount": len(visualAssets),
        "assetWindowLimit": assetsData.get("limit"),
        "assetTotalEntries": assetsData.get("totalEntries"),
        "assetHasMore": assetsData.get("hasMore"),
        "selectedHash": selectedHash,
        "manifestErrorCode": (manifestPayload.get("error") or {}).get("code"),
        "timelineAssetsErrorCode": (assetsPayload.get("error") or {}).get("code"),
    }


def measureManifestRefresh(client: Any) -> dict[str, Any]:
    started = time.perf_counter()
    response = client.get("/api/media/cache")
    elapsed = round(time.perf_counter() - started, 4)
    payload = response.json()
    data = payload.get("data") or {}
    return {
        "ok": response.status_code < 400 and payload.get("success") is True,
        "elapsedSeconds": elapsed,
        "entryCount": len(data.get("entries") or []),
        "totalSizeBytes": data.get("totalSizeBytes"),
        "errorCode": (payload.get("error") or {}).get("code"),
    }


def seedLargeCacheManifest(
    projectPath: Path, targetEntries: int, sourceItems: list[dict[str, Any]]
) -> dict[str, Any]:
    from datetime import UTC, datetime
    from hashlib import sha256

    from app.media.cache_manifest import (
        MediaCacheEntry,
        MediaCacheManifest,
    )
    from app.repositories.file_media_cache_repository import FileMediaCacheRepository

    cacheRoot = projectPath / "cache"
    cacheRoot.mkdir(parents=True, exist_ok=True)
    repository = FileMediaCacheRepository()
    manifest = repository.load(cacheRoot)
    entries = list(manifest.entries)
    created = datetime.now(UTC)
    existingCount = len(entries)
    for offset in range(max(0, targetEntries - existingCount)):
        index = existingCount + offset
        seed = f"phase9-live-cache-seed-{index}".encode()
        digest = sha256(seed).hexdigest()
        relativePath = f"phase9-seed/{digest}.jpg"
        path = cacheRoot / relativePath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(seed)
        source = syntheticSource(index, sourceItems)
        entries.append(
            MediaCacheEntry(
                digest,
                relativePath,
                len(seed),
                created,
                created,
                (source,),
                perceptualHash=f"dhash64-v1:{index % 65536:016x}",
            )
        )
    keptEntries = entries[: max(targetEntries, existingCount)]
    repository.save(cacheRoot, MediaCacheManifest(tuple(keptEntries)))
    return {
        "previousEntries": existingCount,
        "targetEntries": targetEntries,
        "actualEntries": len(repository.load(cacheRoot).entries),
    }


def syntheticSource(index: int, sourceItems: list[dict[str, Any]]) -> Any:
    from app.media.cache_manifest import MediaCacheSource

    if sourceItems:
        item = sourceItems[index % len(sourceItems)]
        return MediaCacheSource(
            str(item.get("providerId")),
            f"{item.get('id')}-seed-{index}",
            f"{item.get('sourceUri')}#phase9-seed-{index}",
        )
    return MediaCacheSource(
        "phase9",
        f"seed-{index}",
        f"https://phase9.local/media/{index}.jpg",
    )


def measureSyntheticRankingMerge(
    sourceItems: list[dict[str, Any]], cacheEntries: int, candidateCount: int
) -> dict[str, Any]:
    from datetime import UTC, datetime
    from hashlib import sha256

    from app.media.cache_manifest import (
        MediaCacheEntry,
        MediaCacheManifest,
        MediaCacheSource,
    )
    from app.media.media_result_ranker import MediaResultRanker
    from app.media.models import MediaSearchPage

    items = syntheticSearchItems(sourceItems, candidateCount)
    pages = tuple(
        MediaSearchPage(
            providerId,
            "phase9 synthetic",
            len(providerItems),
            0,
            len(providerItems),
            False,
            tuple(providerItems),
        )
        for providerId, providerItems in groupItemsByProvider(items).items()
    )
    created = datetime.now(UTC)
    entries = []
    for index in range(cacheEntries):
        item = items[index % len(items)]
        digest = sha256(f"phase9-ranking-{index}".encode()).hexdigest()
        entries.append(
            MediaCacheEntry(
                digest,
                f"phase9-ranking/{digest}.jpg",
                1,
                created,
                created,
                (
                    MediaCacheSource(
                        item.providerId,
                        item.id,
                        item.sourceUri,
                    ),
                ),
                perceptualHash=f"dhash64-v1:{index % 65536:016x}",
            )
        )
    started = time.perf_counter()
    ranking = MediaResultRanker().rankWithStatistics(
        pages, MediaCacheManifest(tuple(entries))
    )
    elapsed = round(time.perf_counter() - started, 4)
    return {
        "candidateCount": candidateCount,
        "cacheEntries": cacheEntries,
        "pageCount": len(pages),
        "elapsedSeconds": elapsed,
        "retainedItems": len(ranking.items),
        "deduplication": ranking.statistics.toDictionary(),
    }


def syntheticSearchItems(
    sourceItems: list[dict[str, Any]], candidateCount: int
) -> list[Any]:
    from app.media.models import MediaSearchItem, MediaType

    baseItems = sourceItems or [
        {
            "id": "seed",
            "providerId": "pexels",
            "mediaType": "image",
            "title": "Phase 9 seed",
            "sourceUri": "https://phase9.local/seed.jpg",
            "fileSizeBytes": None,
            "score": 1.0,
        }
    ]
    items = []
    for index in range(candidateCount):
        base = baseItems[index % len(baseItems)]
        mediaType = MediaType(str(base.get("mediaType") or "image"))
        providerId = str(base.get("providerId") or "phase9")
        items.append(
            MediaSearchItem(
                id=f"{base.get('id')}-synthetic-{index}",
                providerId=providerId,
                mediaType=mediaType,
                title=f"{base.get('title') or 'Phase 9 synthetic'} {index}",
                sourceUri=f"{base.get('sourceUri')}?phase9_candidate={index}",
                previewUri=None,
                fileSizeBytes=base.get("fileSizeBytes"),
                modifiedAt=None,
                score=max(0.1, 1.0 - (index % 100) / 100),
            )
        )
    return items


def groupItemsByProvider(items: list[Any]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for item in items:
        grouped.setdefault(item.providerId, []).append(item)
    return grouped


def sanitizeItem(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "providerId": item.get("providerId"),
        "mediaType": item.get("mediaType"),
        "title": item.get("title"),
        "sourceUri": item.get("sourceUri"),
        "fileSizeBytes": item.get("fileSizeBytes"),
        "score": item.get("score"),
    }


def suggestedFileName(item: dict[str, Any]) -> str:
    extension = "jpg" if item.get("mediaType") == "image" else "mp4"
    raw = f"{item.get('providerId')}-{item.get('id')}.{extension}"
    return "".join(
        character if character.isalnum() or character in ".-" else "-"
        for character in raw
    )


def estimateMergeRankOverhead(
    mixedWarmSeconds: float | None, warmProviderSeconds: list[float]
) -> float | None:
    if mixedWarmSeconds is None or not warmProviderSeconds:
        return None
    return round(max(0.0, mixedWarmSeconds - max(warmProviderSeconds)), 4)


def average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def parseCacheSizes(rawValue: str) -> tuple[int, ...]:
    sizes = []
    for item in rawValue.split(","):
        item = item.strip()
        if not item:
            continue
        size = int(item)
        if size > 0:
            sizes.append(size)
    return tuple(dict.fromkeys(sizes))


def captureEnvironment() -> dict[str, str | None]:
    return {"APP_DATA_DIR": os.environ.get("APP_DATA_DIR")}


def restoreEnvironment(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


if __name__ == "__main__":
    main()
