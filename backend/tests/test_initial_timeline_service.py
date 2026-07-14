from datetime import UTC, datetime

from app.pipeline.scene_collection import SceneCollection
from app.pipeline.script_models import Scene
from app.timeline.initial_timeline_service import InitialTimelineService


def testCreatesContinuousTimelineWithSubtitles() -> None:
    scenes = SceneCollection(
        (
            Scene("scene-1", 1, "Five words make this scene"),
            Scene("scene-2", 2, "Subtitle scene", (), 5_000, 8_500),
        ),
        datetime.now(UTC),
    )

    timeline = InitialTimelineService().create(scenes)

    assert timeline.scenes[0].startMilliseconds == 0
    assert timeline.scenes[0].endMilliseconds == 2_000
    assert timeline.scenes[1].startMilliseconds == 2_000
    assert timeline.scenes[1].endMilliseconds == 5_500
    assert timeline.scenes[1].subtitleClips[0].text == "Subtitle scene"
    assert timeline.durationMilliseconds == 5_500


def testClampsEstimatedTextDuration() -> None:
    scenes = SceneCollection(
        (
            Scene("short", 1, "One"),
            Scene("long", 2, " ".join("word" for _ in range(200))),
        ),
        datetime.now(UTC),
    )

    timeline = InitialTimelineService().create(scenes)

    assert timeline.scenes[0].endMilliseconds == 2_000
    assert (
        timeline.scenes[1].endMilliseconds - timeline.scenes[1].startMilliseconds
        == 30_000
    )
