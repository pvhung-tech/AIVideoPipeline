from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.config.dependencies import (
    getMediaCacheReconciliationService,
    getMediaCacheService,
    getMediaFingerprintBackfillService,
    getMediaMetadataBackfillService,
    getMediaSearchService,
)
from app.main import createApp
from app.media.cache_manifest import (
    MediaCacheCleanupResult,
    MediaCacheEntry,
    MediaCacheManifest,
    MediaCacheReconciliationResult,
    OrphanCacheFile,
)
from app.media.cache_models import CachedMedia, MediaCacheDiagnostics
from app.media.fingerprint_backfill_models import MediaFingerprintBackfillJob
from app.media.metadata_backfill_models import MediaMetadataBackfillJob
from app.media.models import (
    MediaDeduplicationStatistics,
    MediaProviderError,
    MediaSearchItem,
    MediaSearchPage,
    MediaType,
)


class FakeMediaSearchService:
    async def search(
        self,
        text: str,
        mediaTypes: tuple[MediaType, ...],
        providerId: str | None = None,
        limit: int = 50,
        offset: int = 0,
        contentCategory: str | None = None,
    ) -> MediaSearchPage:
        del mediaTypes, contentCategory
        item = MediaSearchItem(
            id="local-1",
            providerId="local",
            mediaType=MediaType.IMAGE,
            title="City Skyline",
            sourceUri="file:///library/city.jpg",
            previewUri="file:///library/city.jpg",
            fileSizeBytes=100,
            modifiedAt=datetime.now(UTC),
            score=1.0,
            license="local",
        )
        selectedProvider = providerId or "local"
        errors = (
            (MediaProviderError("pixabay", "MEDIA_PROVIDER_FAILED", "failed"),)
            if selectedProvider == "all"
            else ()
        )
        return MediaSearchPage(
            selectedProvider,
            text,
            1,
            offset,
            limit,
            bool(errors),
            (item,),
            errors,
            (
                MediaDeduplicationStatistics(1, 1, 1, 0, 0, 0, 8, 8)
                if selectedProvider == "all"
                else None
            ),
        )

    def listProviderIds(self) -> tuple[str, ...]:
        return ("local",)


class FakeMediaCacheService:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def cache(
        self, providerId: str, mediaId: str, sourceUri: str, fileName: str | None
    ) -> CachedMedia:
        del sourceUri, fileName
        diagnostics = MediaCacheDiagnostics(
            providerId,
            False,
            100,
            0.1,
            0.01,
            0.02,
            0.03,
            0.04,
            0.05,
            0.06,
            0.31,
        )
        return CachedMedia(
            mediaId, providerId, "a" * 64, self.path, 100, False, diagnostics
        )

    def getManifest(self) -> MediaCacheManifest:
        timestamp = datetime.now(UTC)
        return MediaCacheManifest(
            (
                MediaCacheEntry(
                    "a" * 64,
                    "aa/cached.jpg",
                    100,
                    timestamp,
                    timestamp,
                    (),
                ),
            )
        )

    def cleanup(
        self,
        dryRun: bool = True,
        maxTotalSizeBytes: int | None = None,
        maxAgeDays: int | None = None,
    ) -> MediaCacheCleanupResult:
        del maxTotalSizeBytes, maxAgeDays
        entry = self.getManifest().entries[0]
        return MediaCacheCleanupResult(dryRun, (entry,), 0, 0)


class FakeMediaCacheReconciliationService:
    def reconcile(self, dryRun: bool = True) -> MediaCacheReconciliationResult:
        return MediaCacheReconciliationResult(
            dryRun,
            (OrphanCacheFile("aa/orphan.jpg", 25),),
            (),
        )


class FakeMetadataBackfillService:
    def __init__(self) -> None:
        self.job = MediaMetadataBackfillJob("job-1", "project-1", "running", 2, 1, 1, 0)

    def startForActiveProject(self) -> MediaMetadataBackfillJob:
        return self.job

    def getActiveProjectJob(self) -> MediaMetadataBackfillJob:
        return self.job

    def cancelActiveProjectJob(self) -> MediaMetadataBackfillJob:
        return self.job


class FakeFingerprintBackfillService:
    def __init__(self) -> None:
        self.job = MediaFingerprintBackfillJob(
            "fingerprint-job-1",
            "project-1",
            "running",
            3,
            1,
            1,
            0,
        )

    def startForActiveProject(self) -> MediaFingerprintBackfillJob:
        return self.job

    def getActiveProjectJob(self) -> MediaFingerprintBackfillJob:
        return self.job

    def cancelActiveProjectJob(self) -> MediaFingerprintBackfillJob:
        return self.job


def testMediaApiSearchesAndListsProviders() -> None:
    app = createApp()
    app.dependency_overrides[getMediaSearchService] = FakeMediaSearchService
    client = TestClient(app)

    searchResponse = client.get(
        "/api/media/search",
        params=[("query", "city"), ("mediaType", "image"), ("limit", "10")],
    )
    providersResponse = client.get("/api/media/providers")

    assert searchResponse.status_code == 200
    assert searchResponse.json()["data"]["items"][0]["title"] == "City Skyline"
    assert providersResponse.json()["data"]["providers"] == ["local"]


def testMediaApiSerializesAggregateProviderErrors() -> None:
    app = createApp()
    app.dependency_overrides[getMediaSearchService] = FakeMediaSearchService
    client = TestClient(app)

    response = client.get(
        "/api/media/search",
        params={"query": "city", "providerId": "all", "limit": 10},
    )

    assert response.status_code == 200
    assert response.json()["data"]["providerId"] == "all"
    assert response.json()["data"]["providerErrors"][0]["providerId"] == "pixabay"
    assert response.json()["data"]["deduplication"]["totalCandidates"] == 1


def testMediaApiCachesMedia(tmp_path: Path) -> None:
    cachedPath = tmp_path / "cached.jpg"
    cachedPath.write_bytes(b"cached")
    app = createApp()
    app.dependency_overrides[getMediaCacheService] = lambda: FakeMediaCacheService(
        cachedPath
    )
    client = TestClient(app)

    response = client.post(
        "/api/media/cache",
        json={
            "providerId": "pexels",
            "mediaId": "pexels-photo-1",
            "sourceUri": "https://images.pexels.com/photos/1/photo.jpg",
            "fileName": "photo.jpg",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["contentHash"] == "a" * 64
    assert response.json()["data"]["duplicate"] is False
    assert response.json()["data"]["diagnostics"]["sourceTransferSeconds"] == 0.1


def testMediaApiListsAndCleansCache(tmp_path: Path) -> None:
    cachedPath = tmp_path / "cached.jpg"
    cachedPath.write_bytes(b"cached")
    app = createApp()
    app.dependency_overrides[getMediaCacheService] = lambda: FakeMediaCacheService(
        cachedPath
    )
    app.dependency_overrides[getMediaMetadataBackfillService] = (
        FakeMetadataBackfillService
    )
    app.dependency_overrides[getMediaFingerprintBackfillService] = (
        FakeFingerprintBackfillService
    )
    client = TestClient(app)

    manifestResponse = client.get("/api/media/cache")
    cleanupResponse = client.post(
        "/api/media/cache/cleanup",
        json={"dryRun": True, "maxTotalSizeBytes": 0, "maxAgeDays": 30},
    )

    assert manifestResponse.status_code == 200
    assert manifestResponse.json()["data"]["totalSizeBytes"] == 100
    assert cleanupResponse.status_code == 200
    assert cleanupResponse.json()["data"]["removedCount"] == 1
    assert cleanupResponse.json()["data"]["dryRun"] is True

    backfillResponse = client.post("/api/media/cache/metadata/backfill")
    assert backfillResponse.status_code == 200
    assert backfillResponse.json()["data"]["updatedVideos"] == 1
    assert client.get("/api/media/cache/metadata/backfill/status").status_code == 200
    assert client.post("/api/media/cache/metadata/backfill/cancel").status_code == 200

    fingerprintResponse = client.post("/api/media/cache/fingerprints/backfill")
    assert fingerprintResponse.status_code == 200
    assert fingerprintResponse.json()["data"]["updatedMedia"] == 1
    assert (
        client.get("/api/media/cache/fingerprints/backfill/status").status_code == 200
    )
    assert (
        client.post("/api/media/cache/fingerprints/backfill/cancel").status_code
        == 200
    )


def testMediaApiReconcilesCache() -> None:
    app = createApp()
    app.dependency_overrides[getMediaCacheReconciliationService] = (
        FakeMediaCacheReconciliationService
    )
    client = TestClient(app)

    response = client.post("/api/media/cache/reconcile", json={"dryRun": True})

    assert response.status_code == 200
    assert response.json()["data"]["orphanCount"] == 1
    assert response.json()["data"]["orphanSizeBytes"] == 25
    assert response.json()["data"]["dryRun"] is True
