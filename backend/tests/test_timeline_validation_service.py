from datetime import UTC, datetime

import pytest

from app.pipeline.scene_collection import SceneCollection
from app.pipeline.script_models import Scene
from app.timeline.errors import TimelineError
from app.timeline.models import (
    AudioClip,
    MediaClip,
    SubtitleClip,
    Timeline,
    TimelineMediaType,
    TimelineScene,
    VisualClipRole,
)
from app.timeline.validation_service import TimelineValidationService

CONTENT_HASH = "a" * 64


def createScenes() -> SceneCollection:
    return SceneCollection((Scene("scene-1", 1, "Scene"),), datetime.now(UTC))


def createTimeline(
    *, mediaClips: tuple[MediaClip, ...] = (), sceneId: str = "scene-1"
) -> Timeline:
    timestamp = datetime.now(UTC)
    return Timeline(
        "timeline-1",
        (
            TimelineScene(
                sceneId,
                1,
                0,
                5_000,
                mediaClips,
                (SubtitleClip("subtitle-1", "Caption", 0, 2_000),),
            ),
        ),
        timestamp,
        timestamp,
    )


def testValidTimelinePasses() -> None:
    clip = MediaClip(
        "media-1", CONTENT_HASH, TimelineMediaType.VIDEO, 0, 3_000, 0, 500, 3_500
    )

    TimelineValidationService().validate(
        createTimeline(mediaClips=(clip,)), createScenes()
    )


def testRejectsUnknownScene() -> None:
    with pytest.raises(TimelineError, match="unknown project scene"):
        TimelineValidationService().validate(
            createTimeline(sceneId="missing"), createScenes()
        )


def testRejectsClipOutsideScene() -> None:
    clip = MediaClip("media-1", CONTENT_HASH, TimelineMediaType.IMAGE, 4_000, 6_000)

    with pytest.raises(TimelineError, match="inside their scene"):
        TimelineValidationService().validate(
            createTimeline(mediaClips=(clip,)), createScenes()
        )


def testRejectsOverlappingClipsOnSameLayer() -> None:
    clips = (
        MediaClip("media-1", CONTENT_HASH, TimelineMediaType.IMAGE, 0, 3_000),
        MediaClip("media-2", "b" * 64, TimelineMediaType.IMAGE, 2_000, 4_000),
    )

    with pytest.raises(TimelineError, match="same layer"):
        TimelineValidationService().validate(
            createTimeline(mediaClips=clips), createScenes()
        )


def testAllowsOverlappingClipsOnDifferentLayers() -> None:
    clips = (
        MediaClip("media-1", CONTENT_HASH, TimelineMediaType.IMAGE, 0, 3_000),
        MediaClip(
            "media-2",
            "b" * 64,
            TimelineMediaType.IMAGE,
            2_000,
            4_000,
            layer=1,
            role=VisualClipRole.AVATAR,
        ),
    )

    TimelineValidationService().validate(
        createTimeline(mediaClips=clips), createScenes()
    )


def testRejectsVideoSourceShorterThanTimelineClip() -> None:
    clip = MediaClip(
        "media-1", CONTENT_HASH, TimelineMediaType.VIDEO, 0, 3_000, 0, 0, 2_000
    )

    with pytest.raises(TimelineError, match="shorter"):
        TimelineValidationService().validate(
            createTimeline(mediaClips=(clip,)), createScenes()
        )


def testValidatesLoopingTimelineAudio() -> None:
    timeline = createTimeline()
    timeline = Timeline(
        timeline.id,
        timeline.scenes,
        timeline.createdAt,
        timeline.updatedAt,
        audioClips=(AudioClip("music-1", CONTENT_HASH, 0, 5_000, 0, 2_000),),
    )

    TimelineValidationService().validate(timeline, createScenes())
