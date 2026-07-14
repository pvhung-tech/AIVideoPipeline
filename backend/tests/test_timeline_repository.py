from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.repositories.file_timeline_repository import FileTimelineRepository
from app.timeline.errors import TimelineError
from app.timeline.models import Timeline, TimelineScene, VisualClipRole


def createTimeline() -> Timeline:
    timestamp = datetime.now(UTC)
    return Timeline(
        "timeline-1",
        (TimelineScene("scene-1", 1, 0, 1_000),),
        timestamp,
        timestamp,
    )


def testFileTimelineRepositorySavesAndLoadsTimeline(tmp_path: Path) -> None:
    repository = FileTimelineRepository()
    timeline = createTimeline()

    saved = repository.saveTimeline(tmp_path, timeline)
    loaded = repository.loadTimeline(tmp_path)

    assert saved == timeline
    assert loaded == timeline
    assert (tmp_path / "timeline" / "timeline.json").is_file()


def testFileTimelineRepositoryRejectsInvalidDocument(tmp_path: Path) -> None:
    timelineDirectory = tmp_path / "timeline"
    timelineDirectory.mkdir()
    (timelineDirectory / "timeline.json").write_text("{}", encoding="utf-8")

    with pytest.raises(TimelineError) as error:
        FileTimelineRepository().loadTimeline(tmp_path)

    assert error.value.code == "INVALID_TIMELINE_FILE"


def testFileTimelineRepositoryMigratesVersionOne(tmp_path: Path) -> None:
    timelineDirectory = tmp_path / "timeline"
    timelineDirectory.mkdir()
    (timelineDirectory / "timeline.json").write_text(
        '{"schemaVersion":1,"id":"old","createdAt":"2026-01-01T00:00:00+00:00",'
        '"updatedAt":"2026-01-01T00:00:00+00:00","scenes":[{"sceneId":"scene-1",'
        '"order":1,"startMilliseconds":0,"endMilliseconds":1000,"mediaClips":[],'
        '"subtitleClips":[]}]}',
        encoding="utf-8",
    )

    migrated = FileTimelineRepository().loadTimeline(tmp_path)

    assert migrated.schemaVersion == 2
    assert migrated.audioClips == ()


def testTimelineMigrationMapsLegacyOverlayToAvatar() -> None:
    data = createTimeline().toDictionary()
    data["schemaVersion"] = 1
    data["scenes"][0]["mediaClips"] = [
        {
            "id": "legacy-overlay",
            "contentHash": "a" * 64,
            "mediaType": "image",
            "startMilliseconds": 0,
            "endMilliseconds": 1_000,
            "layer": 1,
            "sourceStartMilliseconds": None,
            "sourceEndMilliseconds": None,
        }
    ]

    migrated = Timeline.fromDictionary(data)

    assert migrated.scenes[0].mediaClips[0].role is VisualClipRole.AVATAR
