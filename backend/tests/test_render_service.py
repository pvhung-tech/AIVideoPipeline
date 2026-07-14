from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.media.cache_manifest import MediaCacheEntry, MediaCacheManifest
from app.project.project_model import Project
from app.render.errors import RenderError
from app.render.ffmpeg_command_builder import FFmpegCommandBuilder
from app.render.models import ProcessResult, RenderExportSettings
from app.services.render_service import RenderService
from app.timeline.models import (
    MediaClip,
    SubtitleClip,
    Timeline,
    TimelineMediaType,
    TimelineScene,
)

CONTENT_HASH = "a" * 64


class FakeTimelineService:
    def __init__(self, timeline: Timeline) -> None:
        self.timeline = timeline

    def getTimeline(self) -> Timeline:
        return self.timeline


class FakeCacheService:
    def __init__(self, manifest: MediaCacheManifest | None = None) -> None:
        self.manifest = manifest or MediaCacheManifest(())

    def getManifest(self) -> MediaCacheManifest:
        return self.manifest


class StubProjectService:
    def __init__(self, project: Project) -> None:
        self.project = project

    def getCurrentProject(self) -> Project:
        return self.project


class FakeExecutor:
    def __init__(self, returnCode: int = 0) -> None:
        self.returnCode = returnCode

    def run(self, arguments: tuple[str, ...]) -> ProcessResult:
        if self.returnCode == 0:
            Path(arguments[-1]).write_bytes(b"rendered-mp4")
        return ProcessResult(self.returnCode, "render failed")


def createTimeline(
    scenes: tuple[TimelineScene, ...] | None = None,
) -> Timeline:
    timestamp = datetime.now(UTC)
    return Timeline(
        "timeline",
        scenes if scenes is not None else (TimelineScene("scene", 1, 0, 1_000),),
        timestamp,
        timestamp,
    )


def createCacheEntry(tmp_path: Path) -> MediaCacheEntry:
    timestamp = datetime.now(UTC)
    cacheFile = tmp_path / "cache" / "assets" / "image.jpg"
    cacheFile.parent.mkdir(parents=True, exist_ok=True)
    cacheFile.write_bytes(b"image")
    return MediaCacheEntry(
        CONTENT_HASH,
        "assets/image.jpg",
        cacheFile.stat().st_size,
        timestamp,
        timestamp,
        (),
    )


def createService(
    tmp_path: Path,
    returnCode: int = 0,
    timeline: Timeline | None = None,
    manifest: MediaCacheManifest | None = None,
    subtitleMode: str | None = None,
) -> RenderService:
    tmp_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC)
    project = Project("project", "Project", tmp_path, timestamp, timestamp)
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffprobe = tmp_path / "ffprobe.exe"
    ffmpeg.write_bytes(b"executable")
    ffprobe.write_bytes(b"executable")
    return RenderService(
        FakeTimelineService(timeline or createTimeline()),
        FakeCacheService(manifest),
        StubProjectService(project),
        FFmpegCommandBuilder(),
        str(ffmpeg),
        FakeExecutor(returnCode),
        subtitleMode,
    )


def testRenderServiceWritesAtomicProjectOutput(tmp_path: Path) -> None:
    result = createService(tmp_path).render("final.mp4")

    assert result.outputPath == tmp_path / "output" / "final.mp4"
    assert result.sizeBytes == len(b"rendered-mp4")
    assert result.outputPath.read_bytes() == b"rendered-mp4"
    assert not tuple(result.outputPath.parent.glob("*.rendering.mp4"))


def testRenderServiceRejectsUnsafeNameAndFailedProcess(tmp_path: Path) -> None:
    service = createService(tmp_path)
    with pytest.raises(RenderError) as nameError:
        service.render("../outside.mp4")
    assert nameError.value.code == "INVALID_RENDER_FILE_NAME"

    with pytest.raises(RenderError) as renderError:
        createService(tmp_path / "failed", 1).render("failed.mp4")
    assert renderError.value.code == "RENDER_FAILED"


def testRenderServiceResolvesOutputTemplateAndSettings(tmp_path: Path) -> None:
    service = createService(tmp_path)

    plan = service.createRenderPlan(
        None,
        RenderExportSettings(1280, 720, 24, 22, "fast", 128),
        "{project}-{date}.mp4",
    )
    joined = " ".join(plan.command.arguments)

    assert plan.outputPath.name.startswith("Project-")
    assert plan.outputPath.name.endswith(".mp4")
    assert plan.exportSettings.width == 1280
    assert "color=c=black:s=1280x720:r=24" in joined
    assert "-preset fast" in joined


def testRenderServiceCanRenderWithAssSubtitleSidecar(tmp_path: Path) -> None:
    timeline = createTimeline(
        (
            TimelineScene(
                "scene",
                1,
                0,
                1_000,
                subtitleClips=(
                    SubtitleClip("subtitle", "Rendered through ASS", 0, 1_000),
                ),
            ),
        )
    )
    service = createService(tmp_path, timeline=timeline, subtitleMode="ass")

    plan = service.createRenderPlan("final.mp4")
    joined = " ".join(plan.command.arguments)

    assert len(plan.temporaryFiles) == 1
    assert plan.temporaryFiles[0].is_file()
    assert "subtitles=filename=" in joined
    assert "drawtext=" not in joined

    plan.temporaryPath.write_bytes(b"rendered-mp4")
    result = service.completeRenderPlan(plan, 0, "")

    assert result.outputPath == tmp_path / "output" / "final.mp4"
    assert not plan.temporaryFiles[0].exists()


def testRenderServiceCanUsePreRenderedSubtitleOverlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    timeline = createTimeline(
        (
            TimelineScene(
                "scene",
                1,
                0,
                1_000,
                subtitleClips=(
                    SubtitleClip("subtitle", "Rendered through overlay", 0, 1_000),
                ),
            ),
        )
    )

    class FakeCompletedProcess:
        returncode = 0
        stderr = ""

    calls: list[tuple[str, ...]] = []

    def fakeRun(arguments: tuple[str, ...], **_kwargs: Any) -> FakeCompletedProcess:
        calls.append(arguments)
        Path(arguments[-1]).write_bytes(b"subtitle-overlay")
        return FakeCompletedProcess()

    monkeypatch.setattr("app.services.render_service.subprocess.run", fakeRun)
    service = createService(tmp_path, timeline=timeline, subtitleMode="prerender")

    plan = service.createRenderPlan("final.mp4")
    joined = " ".join(plan.command.arguments)

    assert len(plan.temporaryFiles) == 2
    assert plan.temporaryFiles[0].suffix == ".ass"
    assert plan.temporaryFiles[1].suffix == ".mov"
    assert not plan.temporaryFiles[1].exists()
    assert "[subtitleOverlay]overlay=0:0" in joined
    assert "drawtext=" not in joined
    assert "subtitles=filename=" not in joined
    inputIndexes = [
        index
        for index, argument in enumerate(plan.command.arguments)
        if argument == "-i"
    ]
    overlayInput = Path(plan.command.arguments[inputIndexes[-1] + 1])
    assert overlayInput.is_file()
    assert overlayInput.parent == tmp_path / "render" / "cache" / "subtitles"
    assert any("r=8" in argument for argument in calls[0])

    plan.temporaryPath.write_bytes(b"rendered-mp4")
    service.completeRenderPlan(plan, 0, "")

    assert not plan.temporaryFiles[0].exists()
    assert not plan.temporaryFiles[1].exists()
    assert overlayInput.is_file()

    cachedPlan = service.createRenderPlan("cached-final.mp4")
    cachedJoined = " ".join(cachedPlan.command.arguments)

    assert len(calls) == 1
    assert cachedPlan.temporaryFiles == ()
    assert str(overlayInput) in cachedPlan.command.arguments
    assert "[subtitleOverlay]overlay=0:0" in cachedJoined


def testRenderServiceCanUseSubtitleCommandFile(tmp_path: Path) -> None:
    subtitleText = 'Rendered: 50% "ok"\nit\\\'s live\nCafe\\u0301'
    timeline = createTimeline(
        (
            TimelineScene(
                "scene",
                1,
                0,
                1_000,
                subtitleClips=(
                    SubtitleClip("subtitle", subtitleText, 0, 1_000),
                ),
            ),
        )
    )
    service = createService(tmp_path, timeline=timeline, subtitleMode="sendcmd")

    plan = service.createRenderPlan("final.mp4")
    joined = " ".join(plan.command.arguments)

    assert len(plan.temporaryFiles) == 2
    commandPath = plan.temporaryFiles[0]
    textDirectory = plan.temporaryFiles[1]
    assert commandPath.suffix == ".txt"
    assert commandPath.is_file()
    assert textDirectory.is_dir()
    assert "sendcmd=f='" in joined
    assert "drawtext@subtitle=text=''" in joined
    assert joined.count("drawtext") == 1
    assert "drawtext=text='Rendered\\: 50\\%'" not in joined
    commandText = commandPath.read_text(encoding="utf-8")
    cuePath = textDirectory / "cue-0000.txt"
    assert cuePath.is_file()
    assert cuePath.read_text(encoding="utf-8") == subtitleText
    assert "0.000 subtitle reinit textfile='" in commandText
    assert "1.000 subtitle reinit text='';" in commandText

    plan.temporaryPath.write_bytes(b"rendered-mp4")
    service.completeRenderPlan(plan, 0, "")

    assert not commandPath.exists()
    assert not textDirectory.exists()


def testSubtitleCommandFileSupportsApostrophes(tmp_path: Path) -> None:
    timeline = createTimeline(
        (
            TimelineScene(
                "scene",
                1,
                0,
                1_000,
                subtitleClips=(SubtitleClip("subtitle", "it's live", 0, 1_000),),
            ),
        )
    )
    service = createService(tmp_path, timeline=timeline, subtitleMode="sendcmd")

    plan = service.createRenderPlan("final.mp4")

    assert plan.temporaryFiles[1].joinpath("cue-0000.txt").read_text(
        encoding="utf-8"
    ) == "it's live"


def testRenderServiceDefaultsToSubtitleCommandFile(tmp_path: Path) -> None:
    timeline = createTimeline(
        (
            TimelineScene(
                "scene",
                1,
                0,
                1_000,
                subtitleClips=(SubtitleClip("subtitle", "Default sendcmd", 0, 1_000),),
            ),
        )
    )
    service = createService(tmp_path, timeline=timeline)

    plan = service.createRenderPlan("final.mp4")
    joined = " ".join(plan.command.arguments)

    assert "sendcmd=f='" in joined
    assert "drawtext@subtitle=text=''" in joined
    assert "drawtext=text='Default sendcmd'" not in joined


def testPrerenderSubtitleOverlayRejectsInvalidFps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    timeline = createTimeline(
        (
            TimelineScene(
                "scene",
                1,
                0,
                1_000,
                subtitleClips=(
                    SubtitleClip("subtitle", "Rendered through overlay", 0, 1_000),
                ),
            ),
        )
    )
    monkeypatch.setenv("RENDER_SUBTITLE_OVERLAY_FPS", "0")
    service = createService(tmp_path, timeline=timeline, subtitleMode="prerender")

    with pytest.raises(RenderError) as error:
        service.createRenderPlan("final.mp4")

    assert error.value.code == "INVALID_RENDER_SUBTITLE_OVERLAY_FPS"


def testRenderServiceRejectsUnknownOutputTemplatePlaceholder(tmp_path: Path) -> None:
    service = createService(tmp_path)

    with pytest.raises(RenderError) as error:
        service.createRenderPlan(None, None, "{unknown}.mp4")

    assert error.value.code == "INVALID_RENDER_OUTPUT_TEMPLATE"


def testRenderServiceRequiresFfprobe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = createService(tmp_path)
    (tmp_path / "ffprobe.exe").unlink()
    monkeypatch.setattr("app.services.render_service.shutil.which", lambda _name: None)

    with pytest.raises(RenderError) as error:
        service.createRenderPlan("final.mp4")

    assert error.value.code == "FFPROBE_NOT_FOUND"


def testRenderServicePreflightReportsGroupedStatus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = createService(tmp_path)
    (tmp_path / "ffprobe.exe").unlink()
    monkeypatch.setattr("app.services.render_service.shutil.which", lambda _name: None)

    report = service.checkRenderPreflight("final.mp4")
    groups = {group.group: group for group in report.groups}

    assert not report.ready
    assert groups["Tool"].status == "failed"
    assert groups["Tool"].checks[-1].code == "FFPROBE_NOT_FOUND"
    assert groups["Timeline"].status == "passed"
    assert groups["Output"].status == "passed"
    assert groups["Media"].status == "passed"


def testRenderServiceRejectsInvalidTimelineBeforeQueue(tmp_path: Path) -> None:
    service = createService(tmp_path, timeline=createTimeline(()))

    with pytest.raises(RenderError) as error:
        service.createRenderPlan("final.mp4")

    assert error.value.code == "INVALID_RENDER_TIMELINE"


def testRenderServiceRejectsUnwritableOutputPath(tmp_path: Path) -> None:
    (tmp_path / "output" / "final.mp4").mkdir(parents=True)
    service = createService(tmp_path)

    with pytest.raises(RenderError) as error:
        service.createRenderPlan("final.mp4")

    assert error.value.code == "RENDER_OUTPUT_NOT_WRITABLE"


def testRenderServiceRejectsMissingTimelineAsset(tmp_path: Path) -> None:
    timeline = createTimeline(
        (
            TimelineScene(
                "scene",
                1,
                0,
                1_000,
                (
                    MediaClip(
                        "clip",
                        CONTENT_HASH,
                        TimelineMediaType.IMAGE,
                        0,
                        1_000,
                    ),
                ),
            ),
        )
    )
    service = createService(tmp_path, timeline=timeline)

    with pytest.raises(RenderError) as error:
        service.createRenderPlan("final.mp4")

    assert error.value.code == "RENDER_ASSET_NOT_FOUND"


def testRenderServiceAcceptsExistingTimelineAsset(tmp_path: Path) -> None:
    timeline = createTimeline(
        (
            TimelineScene(
                "scene",
                1,
                0,
                1_000,
                (
                    MediaClip(
                        "clip",
                        CONTENT_HASH,
                        TimelineMediaType.IMAGE,
                        0,
                        1_000,
                    ),
                ),
            ),
        )
    )
    manifest = MediaCacheManifest((createCacheEntry(tmp_path),))

    plan = createService(
        tmp_path, timeline=timeline, manifest=manifest
    ).createRenderPlan("final.mp4")

    assert plan.outputPath.name == "final.mp4"


def testRenderServicePreflightReadyForValidProject(tmp_path: Path) -> None:
    report = createService(tmp_path).checkRenderPreflight("final.mp4")

    assert report.ready
    assert report.outputFileName == "final.mp4"
    assert report.durationMilliseconds == 1_000
    assert [group.status for group in report.groups] == [
        "passed",
        "passed",
        "passed",
        "passed",
    ]
