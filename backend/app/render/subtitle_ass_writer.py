from pathlib import Path

from app.render.models import RenderExportSettings
from app.timeline.models import SubtitleClip, Timeline


def writeAssSubtitleFile(
    timeline: Timeline, settings: RenderExportSettings, outputPath: Path
) -> None:
    subtitles = tuple(
        sorted(
            (clip for scene in timeline.scenes for clip in scene.subtitleClips),
            key=lambda clip: (clip.startMilliseconds, clip.endMilliseconds, clip.id),
        )
    )
    outputPath.parent.mkdir(parents=True, exist_ok=True)
    outputPath.write_text(
        "\n".join(
            (
                "[Script Info]",
                "ScriptType: v4.00+",
                f"PlayResX: {settings.width}",
                f"PlayResY: {settings.height}",
                "",
                "[V4+ Styles]",
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
                "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
                "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
                "Alignment, MarginL, MarginR, MarginV, Encoding",
                "Style: Default,Arial,52,&H00FFFFFF,&H000000FF,&H00000000,"
                "&H64000000,0,0,0,0,100,100,0,0,1,3,0,2,48,48,80,1",
                "",
                "[Events]",
                "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
                "MarginV, Effect, Text",
                *(eventLine(subtitle) for subtitle in subtitles),
                "",
            )
        ),
        encoding="utf-8",
    )


def eventLine(subtitle: SubtitleClip) -> str:
    return (
        "Dialogue: 0,"
        f"{assTimestamp(subtitle.startMilliseconds)},"
        f"{assTimestamp(subtitle.endMilliseconds)},"
        f"Default,,0,0,0,,{escapeAssText(subtitle.text)}"
    )


def assTimestamp(milliseconds: int) -> str:
    centiseconds = max(0, milliseconds) // 10
    seconds, centisecond = divmod(centiseconds, 100)
    minutes, second = divmod(seconds, 60)
    hour, minute = divmod(minutes, 60)
    return f"{hour}:{minute:02d}:{second:02d}.{centisecond:02d}"


def escapeAssText(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\r\n", "\\N")
        .replace("\n", "\\N")
        .replace("\r", "\\N")
    )
