import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.media.cache_manifest import MediaCacheManifest
from app.media.cache_paths import resolveCacheEntryPath
from app.project.errors import ProjectError
from app.project.project_model import Project
from app.render.errors import RenderError
from app.render.ffmpeg_command_builder import FFmpegCommandBuilder
from app.render.models import (
    ProcessResult,
    RenderDraft,
    RenderExportSettings,
    RenderOutputPreview,
    RenderPlan,
    RenderPreflightCheck,
    RenderPreflightGroup,
    RenderPreflightReport,
    RenderResult,
)
from app.render.subtitle_ass_writer import writeAssSubtitleFile
from app.services.script_service import ActiveProjectProvider
from app.timeline.models import (
    AudioClip,
    MediaClip,
    SubtitleClip,
    Timeline,
    TimelineMediaType,
    VisualClipRole,
)

logger = logging.getLogger(__name__)
OUTPUT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,119}\.mp4$")
DEFAULT_SUBTITLE_OVERLAY_FRAME_RATE = 8


class TimelineProvider(Protocol):
    def getTimeline(self) -> Timeline: ...


class MediaCacheProvider(Protocol):
    def getManifest(self) -> MediaCacheManifest: ...


class RenderExecutor(Protocol):
    def run(self, arguments: tuple[str, ...]) -> ProcessResult: ...


@dataclass(frozen=True)
class SubtitleRenderAssets:
    assPath: Path | None = None
    overlayPath: Path | None = None
    commandPath: Path | None = None
    cleanupPaths: tuple[Path, ...] | None = None

    @property
    def temporaryFiles(self) -> tuple[Path, ...]:
        if self.cleanupPaths is not None:
            return self.cleanupPaths
        return tuple(
            path
            for path in (self.assPath, self.overlayPath, self.commandPath)
            if path is not None
        )


class SubprocessRenderExecutor:
    def run(self, arguments: tuple[str, ...]) -> ProcessResult:
        try:
            result = subprocess.run(
                arguments,
                capture_output=True,
                check=False,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as error:
            raise RenderError(
                "RENDER_PROCESS_START_FAILED", "FFmpeg could not be started."
            ) from error
        return ProcessResult(result.returncode, result.stderr)


class RenderService:
    def __init__(
        self,
        timelineService: TimelineProvider,
        mediaCacheService: MediaCacheProvider,
        projectService: ActiveProjectProvider,
        commandBuilder: FFmpegCommandBuilder,
        ffmpegPath: str | None = None,
        executor: RenderExecutor | None = None,
        subtitleMode: str | None = None,
    ) -> None:
        self.timelineService = timelineService
        self.mediaCacheService = mediaCacheService
        self.projectService = projectService
        self.commandBuilder = commandBuilder
        self.ffmpegPath = ffmpegPath
        self.executor = executor or SubprocessRenderExecutor()
        self.subtitleMode = subtitleMode

    def render(
        self,
        fileName: str | None = "rendered.mp4",
        exportSettings: RenderExportSettings | None = None,
        outputNameTemplate: str | None = None,
    ) -> RenderResult:
        plan = self.createRenderPlan(fileName, exportSettings, outputNameTemplate)
        result = self.executor.run(plan.command.arguments)
        return self.completeRenderPlan(plan, result.returnCode, result.standardError)

    def createRenderPlan(
        self,
        fileName: str | None = "rendered.mp4",
        exportSettings: RenderExportSettings | None = None,
        outputNameTemplate: str | None = None,
    ) -> RenderPlan:
        draft = self.createRenderDraft(fileName, exportSettings, outputNameTemplate)
        project = self._requireProject()
        timeline = self.timelineService.getTimeline()
        executable = self._resolveExecutable()
        temporaryPath = draft.outputPath.with_name(f".{uuid4().hex}.rendering.mp4")
        assets = self._resolveAssets(
            project, timeline, self.mediaCacheService.getManifest()
        )
        subtitleAssets = self._prepareSubtitleAssets(
            executable,
            project,
            timeline,
            draft.exportSettings,
            temporaryPath,
        )
        command = self.commandBuilder.build(
            executable,
            timeline,
            assets,
            temporaryPath,
            draft.exportSettings,
            subtitleAssets.assPath,
            subtitleAssets.overlayPath,
            subtitleAssets.commandPath,
        )
        return RenderPlan(
            draft.projectId,
            draft.projectPath,
            command,
            draft.outputPath,
            temporaryPath,
            draft.durationMilliseconds,
            draft.exportSettings,
            subtitleAssets.temporaryFiles,
        )

    def createRenderDraft(
        self,
        fileName: str | None = "rendered.mp4",
        exportSettings: RenderExportSettings | None = None,
        outputNameTemplate: str | None = None,
    ) -> RenderDraft:
        project = self._requireProject()
        settings = exportSettings or RenderExportSettings()
        resolvedFileName = self._resolveOutputFileName(
            project, fileName, outputNameTemplate
        )
        outputPath = self._outputPath(project, resolvedFileName)
        timeline = self.timelineService.getTimeline()
        executable = self._resolveExecutable()
        self._resolveProbeExecutable(executable)
        self._validateTimelineRenderable(timeline)
        self._prepareOutput(outputPath)
        self._resolveAssets(project, timeline, self.mediaCacheService.getManifest())
        return RenderDraft(
            project.id,
            project.path,
            outputPath,
            timeline.durationMilliseconds,
            settings,
        )

    def checkRenderPreflight(
        self,
        fileName: str | None = "rendered.mp4",
        exportSettings: RenderExportSettings | None = None,
        outputNameTemplate: str | None = None,
    ) -> RenderPreflightReport:
        _settings = exportSettings or RenderExportSettings()
        project = self._requireProject()
        resolvedFileName: str | None = None
        outputPath: Path | None = None
        timeline: Timeline | None = None
        executable: str | None = None
        groups: list[RenderPreflightGroup] = []

        toolChecks: list[RenderPreflightCheck] = []
        try:
            executable = self._resolveExecutable()
            toolChecks.append(
                self._preflightCheck(
                    "FFMPEG_AVAILABLE", "FFmpeg is available.", "passed"
                )
            )
        except RenderError as error:
            toolChecks.append(self._preflightCheck(error.code, error.message, "failed"))
        if executable is not None:
            try:
                self._resolveProbeExecutable(executable)
                toolChecks.append(
                    self._preflightCheck(
                        "FFPROBE_AVAILABLE", "FFprobe is available.", "passed"
                    )
                )
            except RenderError as error:
                toolChecks.append(
                    self._preflightCheck(error.code, error.message, "failed")
                )
        else:
            toolChecks.append(
                self._preflightCheck(
                    "FFPROBE_SKIPPED",
                    "FFprobe check requires FFmpeg to be configured first.",
                    "skipped",
                )
            )
        groups.append(self._preflightGroup("Tool", toolChecks))

        timelineChecks: list[RenderPreflightCheck] = []
        try:
            timeline = self.timelineService.getTimeline()
            self._validateTimelineRenderable(timeline)
            timelineChecks.append(
                self._preflightCheck(
                    "TIMELINE_RENDERABLE",
                    "Timeline duration and layers are renderable.",
                    "passed",
                )
            )
        except Exception as error:
            timelineChecks.append(
                self._preflightException(error, "INVALID_RENDER_TIMELINE")
            )
        groups.append(self._preflightGroup("Timeline", timelineChecks))

        outputChecks: list[RenderPreflightCheck] = []
        try:
            resolvedFileName = self._resolveOutputFileName(
                project, fileName, outputNameTemplate
            )
            outputPath = self._outputPath(project, resolvedFileName)
            self._prepareOutput(outputPath)
            outputChecks.append(
                self._preflightCheck(
                    "OUTPUT_WRITABLE",
                    "Render output location is writable.",
                    "passed",
                )
            )
        except Exception as error:
            outputChecks.append(
                self._preflightException(error, "RENDER_OUTPUT_NOT_WRITABLE")
            )
        groups.append(self._preflightGroup("Output", outputChecks))

        mediaChecks: list[RenderPreflightCheck] = []
        if timeline is None:
            mediaChecks.append(
                self._preflightCheck(
                    "MEDIA_SKIPPED",
                    "Media checks require a renderable timeline first.",
                    "skipped",
                )
            )
        else:
            try:
                self._resolveAssets(
                    project, timeline, self.mediaCacheService.getManifest()
                )
                mediaChecks.append(
                    self._preflightCheck(
                        "MEDIA_ASSETS_AVAILABLE",
                        "Timeline media assets are available in project cache.",
                        "passed",
                    )
                )
            except Exception as error:
                mediaChecks.append(
                    self._preflightException(error, "RENDER_ASSET_NOT_FOUND")
                )
        groups.append(self._preflightGroup("Media", mediaChecks))

        ready = all(group.status == "passed" for group in groups)
        return RenderPreflightReport(
            ready,
            tuple(groups),
            resolvedFileName,
            timeline.durationMilliseconds if timeline is not None else None,
        )

    def completeRenderPlan(
        self, plan: RenderPlan, returnCode: int, standardError: str
    ) -> RenderResult:
        try:
            if returnCode != 0 or not plan.temporaryPath.is_file():
                logger.error(
                    "FFmpeg render failed for project %s: %s",
                    plan.projectId,
                    standardError[-2_000:],
                )
                raise RenderError("RENDER_FAILED", "FFmpeg could not render the video.")
            os.replace(plan.temporaryPath, plan.outputPath)
            return RenderResult(
                plan.outputPath,
                plan.durationMilliseconds,
                plan.outputPath.stat().st_size,
            )
        except OSError as error:
            raise RenderError(
                "RENDER_OUTPUT_WRITE_FAILED", "Rendered video could not be saved."
            ) from error
        finally:
            plan.temporaryPath.unlink(missing_ok=True)
            self._cleanupTemporaryFiles(plan)

    def _prepareSubtitleAssets(
        self,
        executable: str,
        project: Project,
        timeline: Timeline,
        settings: RenderExportSettings,
        temporaryPath: Path,
    ) -> "SubtitleRenderAssets":
        mode = self._subtitleMode()
        if mode == "drawtext" or not self._hasSubtitles(timeline):
            return SubtitleRenderAssets()
        if mode == "sendcmd":
            commandPath = temporaryPath.with_suffix(".subtitle-commands.txt")
            textDirectory = self._subtitleCommandTextDirectory(commandPath)
            try:
                self._writeSubtitleCommandFile(timeline, commandPath)
            except OSError as error:
                raise RenderError(
                    "RENDER_SUBTITLE_COMMAND_FILE_FAILED",
                    "Render subtitle command file could not be written.",
                ) from error
            return SubtitleRenderAssets(
                commandPath=commandPath,
                cleanupPaths=(commandPath, textDirectory),
            )
        if mode == "prerender":
            cachedOverlayPath = self._subtitleOverlayCachePath(
                project.path, timeline, settings
            )
            if cachedOverlayPath.is_file():
                return SubtitleRenderAssets(
                    overlayPath=cachedOverlayPath, cleanupPaths=()
                )
        subtitlePath = temporaryPath.with_suffix(".ass")
        try:
            writeAssSubtitleFile(timeline, settings, subtitlePath)
        except OSError as error:
            raise RenderError(
                "RENDER_SUBTITLE_FILE_FAILED",
                "Render subtitle sidecar file could not be written.",
            ) from error
        if mode == "ass":
            return SubtitleRenderAssets(assPath=subtitlePath)
        overlayPath = temporaryPath.with_suffix(".subtitles.mov")
        cachedOverlayPath = self._subtitleOverlayCachePath(
            project.path, timeline, settings
        )
        try:
            cachedOverlayPath.parent.mkdir(parents=True, exist_ok=True)
            self._renderSubtitleOverlay(
                executable, timeline, settings, subtitlePath, overlayPath
            )
            if not cachedOverlayPath.is_file():
                os.replace(overlayPath, cachedOverlayPath)
            else:
                overlayPath.unlink(missing_ok=True)
        except OSError as error:
            raise RenderError(
                "RENDER_SUBTITLE_PRERENDER_FAILED",
                "Render subtitle overlay could not be pre-rendered.",
            ) from error
        return SubtitleRenderAssets(
            overlayPath=cachedOverlayPath,
            cleanupPaths=(subtitlePath, overlayPath),
        )

    def _renderSubtitleOverlay(
        self,
        executable: str,
        timeline: Timeline,
        settings: RenderExportSettings,
        subtitlePath: Path,
        overlayPath: Path,
    ) -> None:
        overlayPath.unlink(missing_ok=True)
        duration = self._seconds(timeline.durationMilliseconds)
        overlayFrameRate = self._subtitleOverlayFrameRate(settings)
        process = subprocess.run(
            (
                executable,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=black@0.0:"
                f"s={settings.width}x{settings.height}:"
                f"r={overlayFrameRate}:d={duration}",
                "-vf",
                "format=rgba,"
                f"subtitles=filename='{self._escapeFilterPath(subtitlePath)}':alpha=1,"
                "format=rgba",
                "-an",
                "-c:v",
                "qtrle",
                str(overlayPath),
            ),
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if process.returncode != 0 or not overlayPath.is_file():
            logger.error(
                "Subtitle overlay pre-render failed: %s",
                process.stderr[-2_000:],
            )
            raise RenderError(
                "RENDER_SUBTITLE_PRERENDER_FAILED",
                "Render subtitle overlay could not be pre-rendered.",
            )

    def _subtitleOverlayFrameRate(self, settings: RenderExportSettings) -> int:
        rawValue = os.environ.get("RENDER_SUBTITLE_OVERLAY_FPS", "").strip()
        if rawValue:
            try:
                configured = int(rawValue)
            except ValueError as error:
                raise RenderError(
                    "INVALID_RENDER_SUBTITLE_OVERLAY_FPS",
                    "Render subtitle overlay FPS must be a positive integer.",
                ) from error
            if configured <= 0:
                raise RenderError(
                    "INVALID_RENDER_SUBTITLE_OVERLAY_FPS",
                    "Render subtitle overlay FPS must be a positive integer.",
                )
            return max(1, min(settings.frameRate, configured))
        return max(1, min(settings.frameRate, DEFAULT_SUBTITLE_OVERLAY_FRAME_RATE))

    def _subtitleMode(self) -> str:
        mode = (self.subtitleMode or os.environ.get("RENDER_SUBTITLE_MODE", "sendcmd"))
        mode = mode.strip().lower()
        if mode not in {"drawtext", "ass", "prerender", "sendcmd"}:
            raise RenderError(
                "INVALID_RENDER_SUBTITLE_MODE",
                "Render subtitle mode must be drawtext, ass, prerender, or sendcmd.",
            )
        return mode

    def _writeSubtitleCommandFile(self, timeline: Timeline, commandPath: Path) -> None:
        commandPath.parent.mkdir(parents=True, exist_ok=True)
        textDirectory = self._subtitleCommandTextDirectory(commandPath)
        textDirectory.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        cueIndex = 0
        for scene in timeline.scenes:
            for subtitle in scene.subtitleClips:
                textPath = textDirectory / f"cue-{cueIndex:04d}.txt"
                textPath.write_text(subtitle.text, encoding="utf-8")
                escapedTextPath = self._escapeFilterPath(textPath)
                start = self._seconds(subtitle.startMilliseconds)
                end = self._seconds(subtitle.endMilliseconds)
                lines.append(f"{start} subtitle reinit textfile='{escapedTextPath}';")
                lines.append(f"{end} subtitle reinit text='';")
                cueIndex += 1
        commandPath.write_text("\n".join(lines), encoding="utf-8")

    def _subtitleCommandTextDirectory(self, commandPath: Path) -> Path:
        return commandPath.with_suffix(".subtitle-text")

    def _hasSubtitles(self, timeline: Timeline) -> bool:
        return any(scene.subtitleClips for scene in timeline.scenes)

    def _subtitleOverlayCachePath(
        self,
        projectPath: Path,
        timeline: Timeline,
        settings: RenderExportSettings,
    ) -> Path:
        return (
            projectPath
            / "render"
            / "cache"
            / "subtitles"
            / f"{self._subtitleOverlayCacheKey(timeline, settings)}.mov"
        )

    def _subtitleOverlayCacheKey(
        self, timeline: Timeline, settings: RenderExportSettings
    ) -> str:
        payload = {
            "schemaVersion": 1,
            "renderer": "qtrle-ass-alpha-low-fps",
            "settings": {
                "width": settings.width,
                "height": settings.height,
                "frameRate": settings.frameRate,
                "overlayFrameRate": self._subtitleOverlayFrameRate(settings),
            },
            "durationMilliseconds": timeline.durationMilliseconds,
            "subtitles": [
                {
                    "sceneId": scene.sceneId,
                    "id": subtitle.id,
                    "text": subtitle.text,
                    "startMilliseconds": subtitle.startMilliseconds,
                    "endMilliseconds": subtitle.endMilliseconds,
                    "layer": subtitle.layer,
                }
                for scene in timeline.scenes
                for subtitle in scene.subtitleClips
            ],
        }
        encoded = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _cleanupTemporaryFiles(self, plan: RenderPlan) -> None:
        for path in plan.temporaryFiles:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)

    def _escapeFilterPath(self, path: Path) -> str:
        return (
            str(path)
            .replace("\\", "/")
            .replace(":", "\\:")
            .replace("'", "\\'")
            .replace(",", "\\,")
        )

    def _seconds(self, milliseconds: int) -> str:
        return f"{milliseconds / 1_000:.3f}"

    def createOutputPreview(
        self,
        result: RenderResult,
        exportSettings: RenderExportSettings,
        thumbnailPath: Path,
        generatedAt: str,
    ) -> RenderOutputPreview:
        thumbnailPath.parent.mkdir(parents=True, exist_ok=True)
        thumbnailPath.unlink(missing_ok=True)
        try:
            executable = self._resolveExecutable()
            seekSeconds = max(0.0, min(3.0, result.durationMilliseconds / 2_000))
            process = subprocess.run(
                (
                    executable,
                    "-y",
                    "-ss",
                    f"{seekSeconds:.3f}",
                    "-i",
                    str(result.outputPath),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=480:-2",
                    str(thumbnailPath),
                ),
                capture_output=True,
                check=False,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if process.returncode != 0 or not thumbnailPath.is_file():
                logger.warning(
                    "Render thumbnail generation failed.",
                    extra={"returnCode": process.returncode},
                )
                return self._previewWithoutThumbnail(
                    result,
                    exportSettings,
                    generatedAt,
                    "Render thumbnail could not be generated.",
                )
        except (OSError, TypeError, subprocess.TimeoutExpired) as error:
            logger.warning("Render thumbnail generation failed.", exc_info=error)
            return self._previewWithoutThumbnail(
                result,
                exportSettings,
                generatedAt,
                "Render thumbnail could not be generated.",
            )
        return RenderOutputPreview(
            thumbnailPath,
            thumbnailPath.resolve().as_uri(),
            result.durationMilliseconds,
            result.sizeBytes,
            exportSettings.width,
            exportSettings.height,
            exportSettings.frameRate,
            generatedAt,
        )

    def _previewWithoutThumbnail(
        self,
        result: RenderResult,
        exportSettings: RenderExportSettings,
        generatedAt: str,
        errorMessage: str,
    ) -> RenderOutputPreview:
        return RenderOutputPreview(
            None,
            None,
            result.durationMilliseconds,
            result.sizeBytes,
            exportSettings.width,
            exportSettings.height,
            exportSettings.frameRate,
            generatedAt,
            "thumbnail_unavailable",
            errorMessage,
        )

    def _resolveAssets(
        self, project: Project, timeline: Timeline, manifest: MediaCacheManifest
    ) -> Mapping[str, Path]:
        required = self._requiredContentHashes(timeline)
        entries = {entry.contentHash: entry for entry in manifest.entries}
        resolved: dict[str, Path] = {}
        for contentHash in required:
            entry = entries.get(contentHash)
            if entry is None:
                raise RenderError(
                    "RENDER_ASSET_NOT_FOUND", "A timeline asset is missing from cache."
                )
            path = resolveCacheEntryPath(project.path / "cache", entry)
            if not path.is_file():
                raise RenderError(
                    "RENDER_ASSET_NOT_FOUND", "A timeline asset file is missing."
                )
            resolved[contentHash] = path
        return resolved

    def _requiredContentHashes(self, timeline: Timeline) -> set[str]:
        return {
            clip.contentHash for scene in timeline.scenes for clip in scene.mediaClips
        } | {clip.contentHash for clip in timeline.audioClips}

    def _resolveExecutable(self) -> str:
        if self.ffmpegPath:
            path = Path(self.ffmpegPath).expanduser().resolve()
            if path.is_file():
                return str(path)
        executable = shutil.which("ffmpeg")
        if executable is None:
            raise RenderError("FFMPEG_NOT_FOUND", "FFmpeg is not configured.")
        return executable

    def _resolveProbeExecutable(self, executable: str) -> str:
        candidate = Path(executable).with_name(
            "ffprobe.exe" if os.name == "nt" else "ffprobe"
        )
        if candidate.is_file():
            return str(candidate)
        ffprobe = shutil.which("ffprobe")
        if ffprobe is None:
            raise RenderError("FFPROBE_NOT_FOUND", "FFprobe is not configured.")
        return ffprobe

    def _validateTimelineRenderable(self, timeline: Timeline) -> None:
        self._requireRenderable(
            bool(timeline.scenes), "Timeline must contain at least one scene."
        )
        self._requireRenderable(
            timeline.durationMilliseconds > 0,
            "Timeline duration must be greater than zero.",
        )
        previousEnd = 0
        clipIds: set[str] = set()
        for scene in timeline.scenes:
            self._requireRenderable(
                scene.endMilliseconds > scene.startMilliseconds,
                "Timeline scene duration must be positive.",
            )
            self._requireRenderable(
                scene.startMilliseconds >= previousEnd,
                "Timeline scenes cannot overlap.",
            )
            for mediaClip in scene.mediaClips:
                self._validateSceneClip(
                    mediaClip,
                    scene.startMilliseconds,
                    scene.endMilliseconds,
                    clipIds,
                )
                self._validateVisualClip(mediaClip)
            for subtitleClip in scene.subtitleClips:
                self._validateSceneClip(
                    subtitleClip,
                    scene.startMilliseconds,
                    scene.endMilliseconds,
                    clipIds,
                )
                self._requireRenderable(
                    bool(subtitleClip.text.strip()), "Subtitle text cannot be empty."
                )
            self._validateLayerOverlaps(scene.mediaClips)
            self._validateLayerOverlaps(scene.subtitleClips)
            previousEnd = scene.endMilliseconds
        for audioClip in timeline.audioClips:
            self._validateAudioClip(
                audioClip, timeline.durationMilliseconds, clipIds
            )
        self._validateLayerOverlaps(timeline.audioClips)

    def _validateSceneClip(
        self,
        clip: MediaClip | SubtitleClip,
        sceneStartMilliseconds: int,
        sceneEndMilliseconds: int,
        clipIds: set[str],
    ) -> None:
        self._requireRenderable(
            bool(clip.id.strip()) and clip.id not in clipIds,
            "Timeline clip IDs must be non-empty and unique.",
        )
        clipIds.add(clip.id)
        self._requireRenderable(
            clip.layer >= 0, "Timeline clip layer cannot be negative."
        )
        self._requireRenderable(
            sceneStartMilliseconds
            <= clip.startMilliseconds
            < clip.endMilliseconds
            <= sceneEndMilliseconds,
            "Timeline clips must stay inside their scene.",
        )

    def _validateVisualClip(self, clip: MediaClip) -> None:
        self._requireRenderable(
            clip.mediaType is not TimelineMediaType.AUDIO,
            "Audio cannot be stored on a visual layer.",
        )
        self._requireRenderable(
            (clip.role is VisualClipRole.BROLL and clip.layer == 0)
            or (clip.role is VisualClipRole.AVATAR and clip.layer == 1),
            "Visual clip role does not match its layer.",
        )
        if clip.mediaType is TimelineMediaType.IMAGE:
            self._requireRenderable(
                clip.sourceStartMilliseconds is None
                and clip.sourceEndMilliseconds is None,
                "Image clips cannot define a source range.",
            )
            return
        self._requireRenderable(
            clip.sourceStartMilliseconds is not None
            and clip.sourceEndMilliseconds is not None,
            "Video clips require a source range.",
        )
        assert clip.sourceStartMilliseconds is not None
        assert clip.sourceEndMilliseconds is not None
        sourceDuration = clip.sourceEndMilliseconds - clip.sourceStartMilliseconds
        self._requireRenderable(
            clip.sourceStartMilliseconds >= 0 and sourceDuration > 0,
            "Video source range is invalid.",
        )
        self._requireRenderable(
            sourceDuration >= clip.endMilliseconds - clip.startMilliseconds,
            "Video source range is shorter than the timeline clip.",
        )

    def _validateAudioClip(
        self, clip: AudioClip, timelineDurationMilliseconds: int, clipIds: set[str]
    ) -> None:
        self._requireRenderable(
            bool(clip.id.strip()) and clip.id not in clipIds,
            "Timeline clip IDs must be non-empty and unique.",
        )
        clipIds.add(clip.id)
        self._requireRenderable(
            0
            <= clip.startMilliseconds
            < clip.endMilliseconds
            <= timelineDurationMilliseconds,
            "Audio clips must stay inside the timeline.",
        )
        sourceDuration = clip.sourceEndMilliseconds - clip.sourceStartMilliseconds
        self._requireRenderable(
            clip.sourceStartMilliseconds >= 0 and sourceDuration > 0,
            "Audio source range is invalid.",
        )
        self._requireRenderable(
            0 <= clip.volume <= 1, "Audio volume must be between 0 and 1."
        )
        self._requireRenderable(
            clip.loop
            or sourceDuration >= clip.endMilliseconds - clip.startMilliseconds,
            "Audio source range is shorter than the timeline clip.",
        )

    def _validateLayerOverlaps(
        self, clips: Iterable[MediaClip | SubtitleClip | AudioClip]
    ) -> None:
        previousEndByLayer: dict[int, int] = {}
        for clip in sorted(
            clips, key=lambda item: (item.layer, item.startMilliseconds)
        ):
            previousEnd = previousEndByLayer.get(clip.layer)
            self._requireRenderable(
                previousEnd is None or clip.startMilliseconds >= previousEnd,
                "Clips on the same layer cannot overlap.",
            )
            previousEndByLayer[clip.layer] = clip.endMilliseconds

    def _prepareOutput(self, outputPath: Path) -> None:
        try:
            outputPath.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise RenderError(
                "RENDER_OUTPUT_NOT_WRITABLE",
                "Render output directory is unavailable.",
            ) from error
        if outputPath.exists() and not outputPath.is_file():
            raise RenderError(
                "RENDER_OUTPUT_NOT_WRITABLE",
                "Render output path is not writable.",
            )
        probePath = outputPath.parent / f".{uuid4().hex}.preflight.tmp"
        try:
            probePath.write_bytes(b"")
        except OSError as error:
            raise RenderError(
                "RENDER_OUTPUT_NOT_WRITABLE",
                "Render output directory is not writable.",
            ) from error
        finally:
            probePath.unlink(missing_ok=True)

    def _requireRenderable(self, condition: bool, message: str) -> None:
        if not condition:
            raise RenderError("INVALID_RENDER_TIMELINE", message)

    def _preflightException(
        self, error: Exception, fallbackCode: str
    ) -> RenderPreflightCheck:
        code = getattr(error, "code", fallbackCode)
        message = getattr(error, "message", str(error) or "Preflight check failed.")
        return self._preflightCheck(str(code), str(message), "failed")

    def _preflightCheck(
        self, code: str, message: str, status: str
    ) -> RenderPreflightCheck:
        return RenderPreflightCheck(code, message, status)

    def _preflightGroup(
        self, group: str, checks: list[RenderPreflightCheck]
    ) -> RenderPreflightGroup:
        if any(check.status == "failed" for check in checks):
            status = "failed"
        elif any(check.status == "skipped" for check in checks):
            status = "skipped"
        else:
            status = "passed"
        return RenderPreflightGroup(group, status, tuple(checks))

    def _outputPath(self, project: Project, fileName: str) -> Path:
        if (
            not OUTPUT_NAME_PATTERN.fullmatch(fileName)
            or Path(fileName).name != fileName
        ):
            raise RenderError(
                "INVALID_RENDER_FILE_NAME", "Render file name must be a safe MP4 name."
            )
        return project.path / "output" / fileName

    def _resolveOutputFileName(
        self,
        project: Project,
        fileName: str | None,
        outputNameTemplate: str | None,
    ) -> str:
        if fileName:
            return fileName.strip()
        template = (outputNameTemplate or "rendered.mp4").strip()
        timestamp = datetime.now(UTC)
        values = {
            "project": self._safeNamePart(project.name),
            "title": self._safeNamePart(project.name),
            "date": timestamp.strftime("%Y%m%d"),
            "time": timestamp.strftime("%H%M%S"),
            "datetime": timestamp.strftime("%Y%m%d-%H%M%S"),
        }
        resolved = template
        for key, value in values.items():
            resolved = resolved.replace("{" + key + "}", value)
        if "{" in resolved or "}" in resolved:
            raise RenderError(
                "INVALID_RENDER_OUTPUT_TEMPLATE",
                "Render output template contains an unsupported placeholder.",
            )
        safe = self._safeNamePart(resolved)
        if not safe.lower().endswith(".mp4"):
            safe = f"{safe}.mp4"
        if not safe or safe.startswith("."):
            safe = "rendered.mp4"
        return safe

    def _safeNamePart(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", value.strip())
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._")
        return cleaned[:120] or "rendered"

    def _requireProject(self) -> Project:
        project = self.projectService.getCurrentProject()
        if project is None:
            raise ProjectError("NO_ACTIVE_PROJECT", "No project is currently open.")
        return project
