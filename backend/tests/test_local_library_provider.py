import asyncio
from pathlib import Path

import pytest

from app.media.errors import MediaError
from app.media.local_library_provider import LocalLibraryProvider
from app.media.models import MediaSearchQuery, MediaType


def createLibrary(root: Path) -> None:
    (root / "cities").mkdir(parents=True)
    (root / "nature").mkdir()
    (root / "cities" / "city_sunrise.jpg").write_bytes(b"image")
    (root / "cities" / "city_night.mp4").write_bytes(b"video")
    (root / "cities" / "city_theme.mp3").write_bytes(b"audio")
    (root / "nature" / "forest.png").write_bytes(b"image")
    (root / "notes.txt").write_text("ignored", encoding="utf-8")


def testLocalLibraryProviderSearchesAndFiltersMetadata(tmp_path: Path) -> None:
    createLibrary(tmp_path)
    provider = LocalLibraryProvider((tmp_path,), 100)

    page = asyncio.run(
        provider.search(
            MediaSearchQuery("city sunrise", tuple(MediaType), limit=10, offset=0)
        )
    )
    imagePage = asyncio.run(
        provider.search(
            MediaSearchQuery("city", (MediaType.IMAGE,), limit=10, offset=0)
        )
    )

    assert page.totalResults == 3
    assert page.items[0].title == "city_sunrise"
    assert page.items[0].score > page.items[1].score
    assert page.items[0].sourceUri.startswith("file:")
    assert imagePage.totalResults == 1
    assert imagePage.items[0].mediaType == MediaType.IMAGE


def testLocalLibraryProviderSupportsPagination(tmp_path: Path) -> None:
    createLibrary(tmp_path)
    provider = LocalLibraryProvider((tmp_path,), 100)

    page = asyncio.run(
        provider.search(MediaSearchQuery("city", tuple(MediaType), limit=1, offset=1))
    )

    assert page.totalResults == 3
    assert len(page.items) == 1
    assert page.offset == 1


def testLocalLibraryProviderFindsAudio(tmp_path: Path) -> None:
    createLibrary(tmp_path)
    provider = LocalLibraryProvider((tmp_path,), 100)

    page = asyncio.run(
        provider.search(MediaSearchQuery("theme", (MediaType.AUDIO,), 10, 0))
    )

    assert page.items[0].mediaType is MediaType.AUDIO


def testLocalLibraryProviderRequiresConfiguration() -> None:
    provider = LocalLibraryProvider((), 100)

    with pytest.raises(MediaError) as error:
        asyncio.run(
            provider.search(
                MediaSearchQuery("city", tuple(MediaType), limit=10, offset=0)
            )
        )

    assert error.value.code == "MEDIA_LIBRARY_NOT_CONFIGURED"


def testLocalLibraryProviderBoundsFileScanning(tmp_path: Path) -> None:
    createLibrary(tmp_path)
    provider = LocalLibraryProvider((tmp_path,), 1)

    page = asyncio.run(
        provider.search(MediaSearchQuery("city", tuple(MediaType), limit=10, offset=0))
    )

    assert page.truncated is True
    assert page.totalResults <= 1
