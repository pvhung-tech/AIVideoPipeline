from dataclasses import replace
from datetime import UTC, datetime

from app.media.cache_manifest import (
    MediaCacheEntry,
    MediaCacheManifest,
    MediaCacheSource,
)
from app.media.deduplication_thresholds import MediaDeduplicationThresholds
from app.media.media_result_ranker import MediaResultRanker
from app.media.models import MediaSearchItem, MediaSearchPage, MediaType


def testRankerDeduplicatesCanonicalPagesAndMetadata() -> None:
    first = createItem(
        "local", "first", "file:///media/clip.mp4", "https://source.test/item"
    )
    duplicatePage = createItem(
        "pexels",
        "page-copy",
        "https://cdn.test/other.mp4",
        "https://source.test/item?utm_source=provider",
    )
    duplicateMetadata = createItem(
        "pixabay",
        "metadata-copy",
        "https://cdn.test/copy.mp4",
        "https://source.test/different",
    )

    result = MediaResultRanker().rankWithStatistics(
        (
            createPage("local", (first,)),
            createPage("pexels", (duplicatePage,)),
            createPage("pixabay", (duplicateMetadata,)),
        )
    )

    assert [item.id for item in result.items] == ["local-first"]
    assert result.items[0].score == 1.0
    assert result.statistics.canonicalDuplicates == 2


def testRankerDeduplicatesImagesWithinHammingThreshold() -> None:
    first = replace(
        createItem("local", "first", "file:///first.jpg", "https://first.test"),
        mediaType=MediaType.IMAGE,
        title="First",
    )
    near = replace(
        createItem("pexels", "near", "https://cdn.test/near.jpg", "https://near.test"),
        mediaType=MediaType.IMAGE,
        title="Near",
    )
    different = replace(
        createItem(
            "pixabay",
            "different",
            "https://cdn.test/different.jpg",
            "https://different.test",
        ),
        mediaType=MediaType.IMAGE,
        title="Different",
    )
    manifest = createManifest(
        (
            (first, "dhash64-v1:0000000000000000"),
            (near, "dhash64-v1:00000000000000ff"),
            (different, "dhash64-v1:ffffffffffffffff"),
        )
    )

    result = MediaResultRanker().rankWithStatistics(
        (
            createPage("local", (first,)),
            createPage("pexels", (near,)),
            createPage("pixabay", (different,)),
        ),
        manifest,
    )

    assert [item.id for item in result.items] == [first.id, different.id]
    assert result.statistics.totalCandidates == 3
    assert result.statistics.retainedItems == 2
    assert result.statistics.fingerprintedCandidates == 3
    assert result.statistics.perceptualImageDuplicates == 1
    assert result.statistics.perceptualVideoDuplicates == 0


def testRankerRequiresEqualVideoFrameCountsForPerceptualDeduplication() -> None:
    first = replace(
        createItem("local", "first", "file:///first.mp4", "https://first.test"),
        title="First",
    )
    near = replace(
        createItem("pexels", "near", "https://cdn.test/near.mp4", "https://near.test"),
        title="Near",
    )
    partial = replace(
        createItem(
            "pixabay", "partial", "https://cdn.test/partial.mp4", "https://partial.test"
        ),
        title="Partial",
    )
    manifest = createManifest(
        (
            (first, "dhash64-sequence-v1:0000000000000000,ffffffffffffffff"),
            (near, "dhash64-sequence-v1:000000000000000f,fffffffffffffff0"),
            (partial, "dhash64-sequence-v1:0000000000000000"),
        )
    )

    result = MediaResultRanker().rankWithStatistics(
        (
            createPage("local", (first,)),
            createPage("pexels", (near,)),
            createPage("pixabay", (partial,)),
        ),
        manifest,
    )

    assert [item.id for item in result.items] == [first.id, partial.id]
    assert result.statistics.perceptualVideoDuplicates == 1


def testRankerUsesCategorySpecificThresholds() -> None:
    first = replace(
        createItem("local", "first", "file:///first.jpg", "https://first.test"),
        mediaType=MediaType.IMAGE,
        title="First",
    )
    near = replace(
        createItem("pexels", "near", "https://cdn.test/near.jpg", "https://near.test"),
        mediaType=MediaType.IMAGE,
        title="Near",
    )
    manifest = createManifest(
        (
            (first, "dhash64-v1:0000000000000000"),
            (near, "dhash64-v1:0000000000003fff"),
        )
    )
    ranker = MediaResultRanker(
        MediaDeduplicationThresholds(
            8, 8, {"news": {MediaType.IMAGE: 14, MediaType.VIDEO: 15}}
        )
    )
    pages = (createPage("local", (first,)), createPage("pexels", (near,)))

    fallback = ranker.rankWithStatistics(pages, manifest)
    calibrated = ranker.rankWithStatistics(pages, manifest, " NEWS ")

    assert len(fallback.items) == 2
    assert len(calibrated.items) == 1
    assert calibrated.statistics.imageHammingThreshold == 14


def createItem(
    providerId: str, itemId: str, sourceUri: str, sourcePageUri: str
) -> MediaSearchItem:
    return MediaSearchItem(
        id=f"{providerId}-{itemId}",
        providerId=providerId,
        mediaType=MediaType.VIDEO,
        title="Shared Clip",
        sourceUri=sourceUri,
        previewUri=None,
        fileSizeBytes=500,
        modifiedAt=None,
        score=1.0,
        sourcePageUri=sourcePageUri,
    )


def createPage(providerId: str, items: tuple[MediaSearchItem, ...]) -> MediaSearchPage:
    return MediaSearchPage(providerId, "shared", len(items), 0, 10, False, items)


def createManifest(
    fingerprints: tuple[tuple[MediaSearchItem, str], ...],
) -> MediaCacheManifest:
    timestamp = datetime.now(UTC)
    entries = tuple(
        MediaCacheEntry(
            contentHash=f"{index:064x}",
            relativePath=f"aa/{index}.bin",
            sizeBytes=500,
            createdAt=timestamp,
            lastAccessedAt=timestamp,
            sources=(MediaCacheSource(item.providerId, item.id, item.sourceUri),),
            perceptualHash=(fingerprint if item.mediaType == MediaType.IMAGE else None),
            videoFingerprint=(
                fingerprint if item.mediaType == MediaType.VIDEO else None
            ),
        )
        for index, (item, fingerprint) in enumerate(fingerprints, start=1)
    )
    return MediaCacheManifest(entries)
