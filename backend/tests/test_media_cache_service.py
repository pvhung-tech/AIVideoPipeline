import asyncio
import hashlib
import threading
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.media.cache_manifest import MediaCacheEntry, MediaCacheManifest
from app.media.errors import MediaError
from app.media.media_fingerprint_service import (
    MediaFingerprints,
    MediaFingerprintService,
)
from app.media.media_metadata_service import MediaMetadataService
from app.project.project_model import Project
from app.services.media_cache_service import MediaCacheService
from app.services.project_service import ProjectService


class FakeProjectRepository:
    def createProject(self, project: Project) -> Project:
        return project

    def saveProject(self, project: Project) -> Project:
        return project

    def openProject(self, projectPath: Path) -> Project:
        raise NotImplementedError

    def listRecentProjects(self, limit: int) -> list[Project]:
        return []


def createProjectService(projectPath: Path) -> ProjectService:
    projectPath.mkdir(parents=True)
    service = ProjectService(FakeProjectRepository())
    service.activeProject = Project(
        id="project-id",
        name="Project",
        path=projectPath,
        createdAt=datetime.now(UTC),
        updatedAt=datetime.now(UTC),
    )
    return service


class StubMetadataService(MediaMetadataService):
    def __init__(self) -> None:
        pass

    def probeDurationMilliseconds(self, path: Path) -> int:
        assert path.is_file()
        return 12_500


class StubFingerprintService(MediaFingerprintService):
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.completed = threading.Event()
        self.calls: list[Path] = []

    def fingerprint(
        self, path: Path, extensionHint: str | None = None
    ) -> MediaFingerprints:
        del extensionHint
        assert path.is_file()
        self.calls.append(path)
        self.started.set()
        assert self.release.wait(timeout=2)
        self.completed.set()
        return MediaFingerprints(perceptualHash="dhash64-v1:1111111111111111")


class ImmediateFingerprintService(MediaFingerprintService):
    def __init__(self) -> None:
        self.calls = 0

    def fingerprint(
        self, path: Path, extensionHint: str | None = None
    ) -> MediaFingerprints:
        self.calls += 1
        if (extensionHint or path.suffix).lower() == ".mp4":
            return MediaFingerprints(
                videoFingerprint="dhash64-sequence-v1:1111111111111111"
            )
        return MediaFingerprints(perceptualHash="dhash64-v1:2222222222222222")


class StubDvidsSourceResolver:
    def __init__(self, resolvedUri: str) -> None:
        self.resolvedUri = resolvedUri
        self.requests: list[str] = []

    async def resolveAssetSource(self, sourceUri: str) -> str:
        self.requests.append(sourceUri)
        return self.resolvedUri


def testBackfillsMissingVideoDuration(tmp_path: Path) -> None:
    projectPath = tmp_path / "project"
    service = MediaCacheService(
        createProjectService(projectPath),
        (),
        1000,
        5,
        metadataService=StubMetadataService(),
    )
    timestamp = datetime.now(UTC)
    cacheRoot = projectPath / "cache"
    video = cacheRoot / "aa" / "asset.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"video")
    entry = MediaCacheEntry("a" * 64, "aa/asset.mp4", 5, timestamp, timestamp, ())
    service.repository.save(cacheRoot, MediaCacheManifest((entry,)))

    first = service.backfillVideoMetadata()
    second = service.backfillVideoMetadata()

    assert first.updatedVideos == 1
    assert second.skippedVideos == 1
    assert service.getManifest().entries[0].durationMilliseconds == 12_500


def testMediaCacheHashesAndDeduplicatesLocalContent(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    first = library / "first.jpg"
    second = library / "second.png"
    content = b"same-media-content"
    first.write_bytes(content)
    second.write_bytes(content)
    service = MediaCacheService(
        createProjectService(tmp_path / "project"), (library,), 1000, 5
    )

    cachedFirst = asyncio.run(service.cache("local", "one", first.as_uri(), None))
    cachedSecond = asyncio.run(service.cache("local", "two", second.as_uri(), None))

    assert cachedFirst.contentHash == hashlib.sha256(content).hexdigest()
    assert cachedFirst.path.read_bytes() == content
    assert cachedFirst.duplicate is False
    assert cachedFirst.diagnostics is not None
    assert cachedFirst.diagnostics.providerId == "local"
    assert cachedFirst.diagnostics.totalSeconds >= 0
    assert cachedFirst.diagnostics.sourceTransferSeconds >= 0
    assert cachedFirst.diagnostics.manifestSeconds >= 0
    assert cachedSecond.path == cachedFirst.path
    assert cachedSecond.duplicate is True
    manifest = service.getManifest()
    assert manifest.totalSizeBytes == len(content)
    assert len(manifest.entries) == 1
    assert len(manifest.entries[0].sources) == 2


def testMediaCacheProbesLocalAudioDuration(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    source = library / "theme.mp3"
    source.write_bytes(b"audio")
    service = MediaCacheService(
        createProjectService(tmp_path / "project"),
        (library,),
        1_000,
        5,
        metadataService=StubMetadataService(),
    )

    asyncio.run(service.cache("local", "theme", source.as_uri(), source.name))

    assert service.getManifest().entries[0].durationMilliseconds == 12_500


def testMediaCachePersistsAndBackfillsImagePerceptualHash(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    source = library / "gradient.png"
    image = Image.new("L", (9, 8))
    image.putdata([column * 28 for _row in range(8) for column in range(9)])
    image.save(source)
    projectPath = tmp_path / "project"
    service = MediaCacheService(createProjectService(projectPath), (library,), 10000, 5)

    asyncio.run(service.cache("local", "gradient", source.as_uri(), None))
    manifest = service.getManifest()
    entry = manifest.entries[0]
    assert entry.perceptualHash == "dhash64-v1:0000000000000000"

    service.repository.save(
        projectPath / "cache",
        type(manifest)((replace(entry, perceptualHash=None),)),
    )
    asyncio.run(service.cache("local", "gradient-again", source.as_uri(), None))

    assert service.getManifest().entries[0].perceptualHash == (
        "dhash64-v1:0000000000000000"
    )


def testMediaCacheStreamsPexelsDownload(tmp_path: Path) -> None:
    content = b"remote-video"

    def handleRequest(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "videos.pexels.com"
        return httpx.Response(200, content=content)

    service = MediaCacheService(
        createProjectService(tmp_path / "project"),
        (),
        1000,
        5,
        httpx.MockTransport(handleRequest),
    )

    cached = asyncio.run(
        service.cache(
            "pexels",
            "pexels-video-1",
            "https://videos.pexels.com/video-files/1.mp4",
            "clip.mp4",
        )
    )

    assert cached.path.suffix == ".mp4"
    assert cached.path.read_bytes() == content


def testMediaCacheReturnsRemoteSourceHitWithoutDownloadingAgain(
    tmp_path: Path,
) -> None:
    content = b"remote-video"
    requests = 0

    def handleRequest(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, content=content)

    service = MediaCacheService(
        createProjectService(tmp_path / "project"),
        (),
        1000,
        5,
        httpx.MockTransport(handleRequest),
    )
    sourceUri = "https://videos.pexels.com/video-files/1.mp4"

    first = asyncio.run(
        service.cache("pexels", "pexels-video-1", sourceUri, "clip.mp4")
    )
    originalAccessedAt = service.getManifest().entries[0].lastAccessedAt
    second = asyncio.run(
        service.cache("pexels", "pexels-video-1", sourceUri, "clip.mp4")
    )
    refreshedAccessedAt = service.getManifest().entries[0].lastAccessedAt

    assert requests == 1
    assert second.duplicate is True
    assert second.contentHash == first.contentHash
    assert second.path == first.path
    assert refreshedAccessedAt >= originalAccessedAt
    assert first.diagnostics is not None
    assert second.diagnostics is not None
    assert second.diagnostics.sourceTransferSeconds == 0.0
    assert second.diagnostics.totalSeconds < first.diagnostics.totalSeconds


def testMediaCacheDefersProviderFingerprintBackfill(tmp_path: Path) -> None:
    content = b"remote-image"
    fingerprintService = StubFingerprintService()
    service = MediaCacheService(
        createProjectService(tmp_path / "project"),
        (),
        1000,
        5,
        httpx.MockTransport(lambda _request: httpx.Response(200, content=content)),
        fingerprintService=fingerprintService,
    )

    cached = asyncio.run(
        service.cache(
            "pexels",
            "pexels-photo-1",
            "https://images.pexels.com/photos/1/photo.jpg",
            "photo.jpg",
        )
    )
    initialEntry = service.getManifest().entries[0]

    assert cached.diagnostics is not None
    assert cached.diagnostics.fingerprintDeferred is True
    assert cached.diagnostics.fingerprintSeconds < 0.05
    assert initialEntry.perceptualHash is None
    assert fingerprintService.started.wait(timeout=2)
    fingerprintService.release.set()
    assert fingerprintService.completed.wait(timeout=2)
    assert service.getManifest().entries[0].perceptualHash == (
        "dhash64-v1:1111111111111111"
    )


def testMediaCacheBackfillsMissingFingerprints(tmp_path: Path) -> None:
    projectPath = tmp_path / "project"
    projectService = createProjectService(projectPath)
    cacheRoot = projectPath / "cache"
    timestamp = datetime.now(UTC)
    image = cacheRoot / "aa" / "image.jpg"
    video = cacheRoot / "bb" / "video.mp4"
    image.parent.mkdir(parents=True)
    video.parent.mkdir(parents=True)
    image.write_bytes(b"image")
    video.write_bytes(b"video")
    entries = (
        MediaCacheEntry("a" * 64, "aa/image.jpg", 5, timestamp, timestamp, ()),
        MediaCacheEntry("b" * 64, "bb/video.mp4", 5, timestamp, timestamp, ()),
    )
    fingerprintService = ImmediateFingerprintService()
    service = MediaCacheService(
        projectService,
        (),
        1000,
        5,
        fingerprintService=fingerprintService,
    )
    service.repository.save(cacheRoot, MediaCacheManifest(entries))

    result = service.backfillMissingFingerprints()
    manifest = service.getManifest()

    assert result.scannedMedia == 2
    assert result.updatedMedia == 2
    assert fingerprintService.calls == 2
    assert manifest.entries[0].perceptualHash == "dhash64-v1:2222222222222222"
    assert manifest.entries[1].videoFingerprint == (
        "dhash64-sequence-v1:1111111111111111"
    )


def testMediaCacheStreamsPixabayDownload(tmp_path: Path) -> None:
    content = b"pixabay-image"
    service = MediaCacheService(
        createProjectService(tmp_path / "project"),
        (),
        1000,
        5,
        httpx.MockTransport(lambda _request: httpx.Response(200, content=content)),
    )

    cached = asyncio.run(
        service.cache(
            "pixabay",
            "pixabay-image-1",
            "https://cdn.pixabay.com/photo/1.jpg",
            "image.jpg",
        )
    )

    assert cached.path.read_bytes() == content


def testMediaCacheStreamsWikimediaDownload(tmp_path: Path) -> None:
    content = b"wikimedia-image"
    service = MediaCacheService(
        createProjectService(tmp_path / "project"),
        (),
        1000,
        5,
        httpx.MockTransport(lambda _request: httpx.Response(200, content=content)),
    )

    cached = asyncio.run(
        service.cache(
            "wikimedia",
            "wikimedia-file-1",
            "https://upload.wikimedia.org/wikipedia/commons/1/image.jpg",
            "image.jpg",
        )
    )

    assert cached.path.read_bytes() == content


def testMediaCacheStreamsDvidsDownload(tmp_path: Path) -> None:
    content = b"dvids-video"
    service = MediaCacheService(
        createProjectService(tmp_path / "project"),
        (),
        1000,
        5,
        httpx.MockTransport(lambda _request: httpx.Response(200, content=content)),
    )

    cached = asyncio.run(
        service.cache(
            "dvids",
            "dvids-video-20",
            "https://d34w7g4gy10iej.cloudfront.net/video/20.mp4",
            "clip.mp4",
        )
    )

    assert cached.path.read_bytes() == content


def testMediaCacheResolvesDvidsLazySourceOnDownload(tmp_path: Path) -> None:
    content = b"dvids-lazy-video"
    resolver = StubDvidsSourceResolver(
        "https://d34w7g4gy10iej.cloudfront.net/video/20.mp4"
    )

    def handleRequest(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "d34w7g4gy10iej.cloudfront.net"
        return httpx.Response(200, content=content)

    service = MediaCacheService(
        createProjectService(tmp_path / "project"),
        (),
        1000,
        5,
        httpx.MockTransport(handleRequest),
        dvidsSourceResolver=resolver,
    )

    cached = asyncio.run(
        service.cache(
            "dvids",
            "dvids-video-20",
            "dvids://asset/video%3A20?type=video",
            "clip.mp4",
        )
    )

    assert resolver.requests == ["dvids://asset/video%3A20?type=video"]
    assert cached.path.read_bytes() == content
    assert service.getManifest().entries[0].sources[0].sourceUri == (
        "dvids://asset/video%3A20?type=video"
    )


def testMediaCacheRejectsUntrustedAndOversizedSources(tmp_path: Path) -> None:
    projectService = createProjectService(tmp_path / "project")
    untrusted = MediaCacheService(projectService, (), 1000, 5)

    with pytest.raises(MediaError) as untrustedError:
        asyncio.run(
            untrusted.cache("pexels", "id", "https://example.com/file.mp4", None)
        )
    assert untrustedError.value.code == "INVALID_MEDIA_SOURCE"

    oversized = MediaCacheService(
        projectService,
        (),
        2,
        5,
        httpx.MockTransport(lambda _request: httpx.Response(200, content=b"large")),
    )
    with pytest.raises(MediaError) as sizeError:
        asyncio.run(
            oversized.cache(
                "pexels",
                "id",
                "https://videos.pexels.com/file.mp4",
                None,
            )
        )
    assert sizeError.value.code == "MEDIA_FILE_TOO_LARGE"


def testMediaCacheRejectsLocalSourceOutsideLibrary(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"outside")
    service = MediaCacheService(
        createProjectService(tmp_path / "project"), (library,), 1000, 5
    )

    with pytest.raises(MediaError) as error:
        asyncio.run(service.cache("local", "id", outside.as_uri(), None))

    assert error.value.code == "INVALID_MEDIA_SOURCE"


def testMediaCacheCleanupSupportsDryRunAndExecution(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    source = library / "asset.jpg"
    source.write_bytes(b"cache-entry")
    service = MediaCacheService(
        createProjectService(tmp_path / "project"), (library,), 1000, 5
    )
    cached = asyncio.run(service.cache("local", "asset", source.as_uri(), None))

    preview = service.cleanup(dryRun=True, maxTotalSizeBytes=0, maxAgeDays=30)

    assert preview.removedEntries[0].contentHash == cached.contentHash
    assert cached.path.exists()
    assert len(service.getManifest().entries) == 1

    result = service.cleanup(dryRun=False, maxTotalSizeBytes=0, maxAgeDays=30)

    assert result.remainingEntries == 0
    assert result.remainingSizeBytes == 0
    assert not cached.path.exists()
    assert service.getManifest().entries == ()
