from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.media.cache_manifest import (
    MediaCacheEntry,
    MediaCacheManifest,
    MediaCacheSource,
)
from app.media.errors import MediaError
from app.repositories.file_media_cache_repository import FileMediaCacheRepository


def testMediaCacheRepositoryRoundTripsManifest(tmp_path: Path) -> None:
    repository = FileMediaCacheRepository()
    timestamp = datetime.now(UTC)
    entry = MediaCacheEntry(
        contentHash="a" * 64,
        relativePath="aa/asset.jpg",
        sizeBytes=12,
        createdAt=timestamp,
        lastAccessedAt=timestamp,
        sources=(MediaCacheSource("pexels", "photo-1", "https://example.test"),),
        perceptualHash="dhash64-v1:0123456789abcdef",
        videoFingerprint="dhash64-sequence-v1:0123456789abcdef",
    )

    repository.save(tmp_path, MediaCacheManifest((entry,)))
    loaded = repository.load(tmp_path)

    assert loaded == MediaCacheManifest((entry,))
    assert loaded.totalSizeBytes == 12


def testMediaCacheRepositoryReadsManifestWithoutFingerprints(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text(
        '{"schemaVersion":1,"entries":[]}', encoding="utf-8"
    )

    assert FileMediaCacheRepository().load(tmp_path) == MediaCacheManifest(())


def testMediaCacheRepositoryRejectsInvalidManifest(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")

    with pytest.raises(MediaError) as error:
        FileMediaCacheRepository().load(tmp_path)

    assert error.value.code == "INVALID_MEDIA_CACHE_MANIFEST"
