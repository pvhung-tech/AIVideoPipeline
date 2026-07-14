from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from app.media.cache_manifest import (
    MediaCacheEntry,
    MediaCacheManifest,
    MediaCacheSource,
)
from app.project.project_model import Project
from app.services.timeline_media_service import (
    TimelineMediaService,
    VisualMediaAssignment,
)
from app.timeline.errors import TimelineError
from app.timeline.models import (
    MediaClip,
    Timeline,
    TimelineMediaType,
    TimelineScene,
    VisualClipRole,
)


class FakeTimelineService:
    def __init__(self, timeline: Timeline) -> None:
        self.timeline = timeline
        self.getCount = 0
        self.saveCount = 0

    def getTimeline(self) -> Timeline:
        self.getCount += 1
        return self.timeline

    def saveTimeline(self, timeline: Timeline) -> Timeline:
        self.saveCount += 1
        self.timeline = timeline
        return timeline


class FakeMediaCacheService:
    def __init__(self, manifest: MediaCacheManifest) -> None:
        self.manifest = manifest
        self.getCount = 0

    def getManifest(self) -> MediaCacheManifest:
        self.getCount += 1
        return self.manifest


class StubProjectService:
    def __init__(self, project: Project) -> None:
        self.project = project

    def getCurrentProject(self) -> Project:
        return self.project


def createService(
    tmp_path: Path, extension: str = ".jpg"
) -> tuple[TimelineMediaService, str]:
    timestamp = datetime.now(UTC)
    project = Project("project", "Project", tmp_path, timestamp, timestamp)
    contentHash = "a" * 64
    relativePath = f"aa/{contentHash}{extension}"
    path = tmp_path / "cache" / relativePath
    path.parent.mkdir(parents=True)
    path.write_bytes(b"media")
    entry = MediaCacheEntry(
        contentHash,
        relativePath,
        5,
        timestamp,
        timestamp,
        (
            MediaCacheSource(
                "local" if extension == ".mp3" else "pexels",
                "asset-1",
                (
                    "file:///library/music.mp3"
                    if extension == ".mp3"
                    else "https://example.test"
                ),
            ),
        ),
        durationMilliseconds=10_000 if extension in (".mp4", ".mp3") else None,
    )
    oldClip = MediaClip(
        "old-primary",
        "b" * 64,
        TimelineMediaType.IMAGE,
        0,
        3_000,
    )
    overlay = MediaClip(
        "overlay",
        "c" * 64,
        TimelineMediaType.IMAGE,
        0,
        3_000,
        layer=1,
        role=VisualClipRole.AVATAR,
    )
    timeline = Timeline(
        "timeline",
        (TimelineScene("scene-1", 1, 0, 3_000, (oldClip, overlay)),),
        timestamp,
        timestamp,
    )
    service = TimelineMediaService(
        FakeTimelineService(timeline),
        FakeMediaCacheService(MediaCacheManifest((entry,))),
        StubProjectService(project),
    )
    return service, contentHash


def testListsAndAssignsCachedImage(tmp_path: Path) -> None:
    service, contentHash = createService(tmp_path)

    assets = service.listAssets()
    timeline = service.assignPrimaryMedia("scene-1", contentHash)

    assert assets[0].contentHash == contentHash
    assert assets[0].mediaType is TimelineMediaType.IMAGE
    assert assets[0].providerIds == ("pexels",)
    assert [clip.layer for clip in timeline.scenes[0].mediaClips] == [1, 0]
    assert timeline.scenes[0].mediaClips[1].contentHash == contentHash


def testAssignsVideoWithSceneLengthSourceRange(tmp_path: Path) -> None:
    service, contentHash = createService(tmp_path, ".mp4")

    timeline = service.assignPrimaryMedia("scene-1", contentHash)
    clip = timeline.scenes[0].mediaClips[1]

    assert clip.mediaType is TimelineMediaType.VIDEO
    assert clip.sourceStartMilliseconds == 0
    assert clip.sourceEndMilliseconds == 3_000

    trimmed = service.trimPrimaryVideo("scene-1", 2_000, 5_000)
    trimmedClip = trimmed.scenes[0].mediaClips[1]
    assert trimmedClip.sourceStartMilliseconds == 2_000
    assert trimmedClip.sourceEndMilliseconds == 5_000


def testRejectsUnknownCachedMedia(tmp_path: Path) -> None:
    service, _contentHash = createService(tmp_path)

    with pytest.raises(TimelineError) as error:
        service.assignPrimaryMedia("scene-1", "f" * 64)

    assert error.value.code == "CACHED_MEDIA_NOT_FOUND"


def testRemovesPrimaryMediaAndPreservesOverlays(tmp_path: Path) -> None:
    service, _contentHash = createService(tmp_path)

    timeline = service.assignPrimaryMedia("scene-1", None)

    assert tuple(clip.id for clip in timeline.scenes[0].mediaClips) == ("overlay",)


def testAssignsAvatarAndLocalMusic(tmp_path: Path) -> None:
    avatarService, avatarHash = createService(tmp_path / "avatar")
    avatarTimeline = avatarService.assignVisualMedia(
        "scene-1", VisualClipRole.AVATAR, avatarHash
    )
    avatar = next(
        clip
        for clip in avatarTimeline.scenes[0].mediaClips
        if clip.role is VisualClipRole.AVATAR
    )
    assert avatar.layer == 1

    musicService, musicHash = createService(tmp_path / "music", ".mp3")
    musicTimeline = musicService.assignMusic(musicHash, 0.35)
    assert musicTimeline.audioClips[0].contentHash == musicHash
    assert musicTimeline.audioClips[0].volume == 0.35
    assert musicTimeline.audioClips[0].loop is True


def testBatchAssignsVisualMediaWithSingleTimelineSave(tmp_path: Path) -> None:
    service, contentHash = createService(tmp_path)

    timeline = service.assignVisualMediaBatch(
        (
            VisualMediaAssignment("scene-1", VisualClipRole.BROLL, contentHash),
            VisualMediaAssignment("scene-1", VisualClipRole.AVATAR, contentHash),
        )
    )

    timelineService = cast(FakeTimelineService, service.timelineService)
    mediaCacheService = cast(FakeMediaCacheService, service.mediaCacheService)

    assert tuple(clip.role for clip in timeline.scenes[0].mediaClips) == (
        VisualClipRole.BROLL,
        VisualClipRole.AVATAR,
    )
    assert timelineService.getCount == 1
    assert timelineService.saveCount == 1
    assert mediaCacheService.getCount == 1


def testBatchRejectsDuplicateSceneRoleAssignments(tmp_path: Path) -> None:
    service, contentHash = createService(tmp_path)

    with pytest.raises(TimelineError) as error:
        service.assignVisualMediaBatch(
            (
                VisualMediaAssignment("scene-1", VisualClipRole.BROLL, contentHash),
                VisualMediaAssignment("scene-1", VisualClipRole.BROLL, None),
            )
        )

    assert error.value.code == "DUPLICATE_TIMELINE_MEDIA_ASSIGNMENT"
