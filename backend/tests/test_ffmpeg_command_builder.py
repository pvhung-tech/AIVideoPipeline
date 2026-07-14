from datetime import UTC, datetime
from pathlib import Path

from app.render.ffmpeg_command_builder import FFmpegCommandBuilder
from app.render.models import RenderExportSettings
from app.timeline.models import (
    AudioClip,
    MediaClip,
    SubtitleClip,
    Timeline,
    TimelineMediaType,
    TimelineScene,
    VisualClipRole,
)


def testBuilderComposesVisualSubtitleAndMusicInputs(tmp_path: Path) -> None:
    timestamp = datetime.now(UTC)
    imageHash = "a" * 64
    avatarHash = "b" * 64
    musicHash = "c" * 64
    scene = TimelineScene(
        "scene-1",
        1,
        0,
        5_000,
        (
            MediaClip(
                "broll",
                imageHash,
                TimelineMediaType.IMAGE,
                0,
                5_000,
            ),
            MediaClip(
                "avatar",
                avatarHash,
                TimelineMediaType.VIDEO,
                0,
                5_000,
                1,
                1_000,
                6_000,
                VisualClipRole.AVATAR,
            ),
        ),
        (SubtitleClip("subtitle", "It's: 50%", 0, 5_000),),
    )
    timeline = Timeline(
        "timeline",
        (scene,),
        timestamp,
        timestamp,
        audioClips=(AudioClip("music", musicHash, 0, 5_000, 0, 2_000, 0.25),),
    )
    assets = {
        imageHash: tmp_path / "image.jpg",
        avatarHash: tmp_path / "avatar.mp4",
        musicHash: tmp_path / "music.mp3",
    }

    command = FFmpegCommandBuilder().build(
        "ffmpeg", timeline, assets, tmp_path / "output.mp4"
    )
    joined = " ".join(command.arguments)

    assert "color=c=black:s=1920x1080:r=30:d=5.000" in joined
    assert "scale=1920:1080" in joined
    assert "overlay=W-w-48:H-h-48" in joined
    assert "drawtext=text='It\\'s\\: 50\\%'" in joined
    assert "volume=0.250[aout]" in joined
    assert "-stream_loop -1" in joined
    assert command.arguments[-1] == str(tmp_path / "output.mp4")


def testBuilderUsesExportSettings(tmp_path: Path) -> None:
    timestamp = datetime.now(UTC)
    timeline = Timeline(
        "timeline",
        (TimelineScene("scene-1", 1, 0, 1_000),),
        timestamp,
        timestamp,
    )
    settings = RenderExportSettings(1280, 720, 24, 22, "fast", 128)

    command = FFmpegCommandBuilder().build(
        "ffmpeg", timeline, {}, tmp_path / "output.mp4", settings
    )
    joined = " ".join(command.arguments)

    assert "color=c=black:s=1280x720:r=24:d=1.000" in joined
    assert "-preset fast" in joined
    assert "-crf 22" in joined
    assert "-r 24" in joined
    assert "-b:a" not in joined
    assert "flags=fast_bilinear" not in joined


def testBuilderUsesFastScalerForDraftProfile(tmp_path: Path) -> None:
    timestamp = datetime.now(UTC)
    imageHash = "f" * 64
    timeline = Timeline(
        "timeline",
        (
            TimelineScene(
                "scene-1",
                1,
                0,
                1_000,
                (
                    MediaClip(
                        "broll",
                        imageHash,
                        TimelineMediaType.IMAGE,
                        0,
                        1_000,
                    ),
                ),
            ),
        ),
        timestamp,
        timestamp,
    )
    settings = RenderExportSettings(854, 480, 24, 28, "veryfast", 128, "draft")

    command = FFmpegCommandBuilder().build(
        "ffmpeg",
        timeline,
        {imageHash: tmp_path / "frame.png"},
        tmp_path / "output.mp4",
        settings,
    )

    assert "scale=854:480:force_original_aspect_ratio=decrease:flags=fast_bilinear" in (
        " ".join(command.arguments)
    )


def testBuilderUsesFastScalerForFastPreviewProfile(tmp_path: Path) -> None:
    timestamp = datetime.now(UTC)
    imageHash = "e" * 64
    timeline = Timeline(
        "timeline",
        (
            TimelineScene(
                "scene-1",
                1,
                0,
                1_000,
                (
                    MediaClip(
                        "broll",
                        imageHash,
                        TimelineMediaType.IMAGE,
                        0,
                        1_000,
                    ),
                ),
            ),
        ),
        timestamp,
        timestamp,
    )
    settings = RenderExportSettings(640, 360, 15, 32, "veryfast", 96, "fast_preview")

    command = FFmpegCommandBuilder().build(
        "ffmpeg",
        timeline,
        {imageHash: tmp_path / "frame.png"},
        tmp_path / "output.mp4",
        settings,
    )

    joined = " ".join(command.arguments)
    assert "color=c=black:s=640x360:r=15:d=1.000" in joined
    assert (
        "scale=640:360:force_original_aspect_ratio=decrease:flags=fast_bilinear"
        in joined
    )


def testBuilderCanUseAssSubtitleSidecar(tmp_path: Path) -> None:
    timestamp = datetime.now(UTC)
    timeline = Timeline(
        "timeline",
        (
            TimelineScene(
                "scene-1",
                1,
                0,
                1_000,
                subtitleClips=(SubtitleClip("subtitle", "Fast subtitle", 0, 1_000),),
            ),
        ),
        timestamp,
        timestamp,
    )
    subtitlePath = tmp_path / "render, subtitle.ass"

    command = FFmpegCommandBuilder().build(
        "ffmpeg", timeline, {}, tmp_path / "output.mp4", subtitleFile=subtitlePath
    )
    joined = " ".join(command.arguments)

    assert "subtitles=filename='" in joined
    assert "render\\, subtitle.ass" in joined
    assert "drawtext=" not in joined


def testBuilderCanUsePreRenderedSubtitleOverlay(tmp_path: Path) -> None:
    timestamp = datetime.now(UTC)
    musicHash = "f" * 64
    timeline = Timeline(
        "timeline",
        (TimelineScene("scene-1", 1, 0, 1_000),),
        timestamp,
        timestamp,
        audioClips=(AudioClip("music", musicHash, 0, 1_000, 0, 1_000, 0.5),),
    )
    musicPath = tmp_path / "music.mp3"
    overlayPath = tmp_path / "subtitle-overlay.mov"

    command = FFmpegCommandBuilder().build(
        "ffmpeg",
        timeline,
        {musicHash: musicPath},
        tmp_path / "output.mp4",
        subtitleOverlayFile=overlayPath,
    )
    joined = " ".join(command.arguments)

    assert command.arguments.count("-i") == 3
    assert str(overlayPath) in command.arguments
    assert "[1:a]atrim=duration=1.000" in joined
    assert "[2:v]format=rgba,setpts=PTS-STARTPTS[subtitleOverlay]" in joined
    assert "[subtitleOverlay]overlay=0:0" in joined
    assert "drawtext=" not in joined
    assert "subtitles=filename=" not in joined


def testBuilderCanUseSubtitleCommandFile(tmp_path: Path) -> None:
    timestamp = datetime.now(UTC)
    timeline = Timeline(
        "timeline",
        (
            TimelineScene(
                "scene-1",
                1,
                0,
                1_000,
                subtitleClips=(SubtitleClip("subtitle", "Fast subtitle", 0, 1_000),),
            ),
        ),
        timestamp,
        timestamp,
    )
    commandPath = tmp_path / "subtitle commands.txt"

    command = FFmpegCommandBuilder().build(
        "ffmpeg",
        timeline,
        {},
        tmp_path / "output.mp4",
        subtitleCommandFile=commandPath,
    )
    joined = " ".join(command.arguments)

    assert "sendcmd=f='" in joined
    assert "subtitle commands.txt" in joined
    assert joined.count("drawtext") == 1
    assert "drawtext@subtitle=text=''" in joined
    assert "subtitles=filename=" not in joined


def testBuilderReusesDuplicateVisualInputsAndKeepsMusicIndex(
    tmp_path: Path,
) -> None:
    timestamp = datetime.now(UTC)
    imageHash = "d" * 64
    musicHash = "e" * 64
    scenes = tuple(
        TimelineScene(
            f"scene-{index}",
            index,
            index * 2_000,
            (index + 1) * 2_000,
            (
                MediaClip(
                    f"broll-{index}",
                    imageHash,
                    TimelineMediaType.IMAGE,
                    index * 2_000,
                    (index + 1) * 2_000,
                ),
            ),
        )
        for index in range(3)
    )
    timeline = Timeline(
        "timeline",
        scenes,
        timestamp,
        timestamp,
        audioClips=(AudioClip("music", musicHash, 0, 6_000, 0, 6_000, 0.5),),
    )
    imagePath = tmp_path / "shared-image.jpg"
    musicPath = tmp_path / "music.mp3"

    command = FFmpegCommandBuilder().build(
        "ffmpeg",
        timeline,
        {imageHash: imagePath, musicHash: musicPath},
        tmp_path / "output.mp4",
    )
    joined = " ".join(command.arguments)

    assert command.arguments.count(str(imagePath)) == 1
    assert command.arguments.count(str(musicPath)) == 1
    assert joined.count("scale=1920:1080") == 1
    assert "split=3[asset0_0][asset0_1][asset0_2]" in joined
    assert joined.count("trim=duration=2.000") == 3
    assert "[2:a]atrim=duration=6.000" in joined
