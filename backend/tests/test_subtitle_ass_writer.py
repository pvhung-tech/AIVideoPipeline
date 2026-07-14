from datetime import UTC, datetime
from pathlib import Path

from app.render.models import RenderExportSettings
from app.render.subtitle_ass_writer import (
    assTimestamp,
    escapeAssText,
    writeAssSubtitleFile,
)
from app.timeline.models import SubtitleClip, Timeline, TimelineScene


def testAssTimestampUsesCentiseconds() -> None:
    assert assTimestamp(0) == "0:00:00.00"
    assert assTimestamp(3_456) == "0:00:03.45"
    assert assTimestamp(3_723_450) == "1:02:03.45"


def testEscapeAssTextPreservesLineBreaksAndBraces() -> None:
    assert escapeAssText("Line {one}\nLine \\two") == "Line \\{one\\}\\NLine \\\\two"


def testWriteAssSubtitleFileCreatesRenderableDocument(tmp_path: Path) -> None:
    timestamp = datetime.now(UTC)
    timeline = Timeline(
        "timeline",
        (
            TimelineScene(
                "scene",
                1,
                0,
                2_000,
                subtitleClips=(
                    SubtitleClip("subtitle", "Hello {world}\nNext", 0, 2_000),
                ),
            ),
        ),
        timestamp,
        timestamp,
    )
    outputPath = tmp_path / "render.ass"

    writeAssSubtitleFile(timeline, RenderExportSettings(854, 480, 24, 28), outputPath)
    content = outputPath.read_text(encoding="utf-8")

    assert "PlayResX: 854" in content
    assert "PlayResY: 480" in content
    assert "Style: Default,Arial,52" in content
    assert "Dialogue: 0,0:00:00.00,0:00:02.00" in content
    assert "Hello \\{world\\}\\NNext" in content
