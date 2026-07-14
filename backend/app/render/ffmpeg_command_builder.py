from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from app.render.errors import RenderError
from app.render.models import FFmpegCommand, RenderExportSettings
from app.timeline.models import (
    MediaClip,
    Timeline,
    TimelineMediaType,
    VisualClipRole,
)


class FFmpegCommandBuilder:
    def build(
        self,
        executable: str,
        timeline: Timeline,
        assets: Mapping[str, Path],
        outputPath: Path,
        settings: RenderExportSettings | None = None,
        subtitleFile: Path | None = None,
        subtitleOverlayFile: Path | None = None,
        subtitleCommandFile: Path | None = None,
    ) -> FFmpegCommand:
        exportSettings = settings or RenderExportSettings()
        duration = self._seconds(timeline.durationMilliseconds)
        arguments = [executable, "-hide_banner", "-loglevel", "error", "-y"]
        arguments.extend(("-progress", "pipe:1", "-nostats"))
        arguments.extend(
            (
                "-f",
                "lavfi",
                "-i",
                "color=c=black:"
                f"s={exportSettings.width}x{exportSettings.height}:"
                f"r={exportSettings.frameRate}:d={duration}",
            )
        )
        visualInputs = self._appendVisualInputs(arguments, timeline, assets)
        visualInputCount = max(
            (inputIndex for _, inputIndex in visualInputs), default=0
        )
        musicInput = self._appendMusicInput(
            arguments, timeline, assets, visualInputCount
        )
        subtitleOverlayInput = self._appendSubtitleOverlayInput(
            arguments, subtitleOverlayFile, visualInputCount, musicInput
        )
        filterGraph, videoLabel, audioLabel = self._filterGraph(
            timeline,
            visualInputs,
            musicInput,
            exportSettings,
            subtitleFile,
            subtitleOverlayInput,
            subtitleCommandFile,
        )
        arguments.extend(("-filter_complex", filterGraph, "-map", videoLabel))
        if audioLabel:
            arguments.extend(
                (
                    "-map",
                    audioLabel,
                    "-c:a",
                    "aac",
                    "-b:a",
                    f"{exportSettings.audioBitrateKbps}k",
                )
            )
        else:
            arguments.append("-an")
        arguments.extend(
            (
                "-c:v",
                "libx264",
                "-preset",
                exportSettings.encoderPreset,
                "-crf",
                str(exportSettings.crf),
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(exportSettings.frameRate),
                "-movflags",
                "+faststart",
                str(outputPath),
            )
        )
        return FFmpegCommand(tuple(arguments), outputPath)

    def _appendVisualInputs(
        self,
        arguments: list[str],
        timeline: Timeline,
        assets: Mapping[str, Path],
    ) -> tuple[tuple[MediaClip, int], ...]:
        clips = sorted(
            (clip for scene in timeline.scenes for clip in scene.mediaClips),
            key=lambda clip: (
                clip.role is VisualClipRole.AVATAR,
                clip.startMilliseconds,
            ),
        )
        inputIndexes: dict[VisualInputKey, int] = {}
        inputs: list[tuple[MediaClip, int]] = []
        for clip in clips:
            key = VisualInputKey.fromClip(clip)
            inputIndex = inputIndexes.get(key)
            if inputIndex is not None:
                inputs.append((clip, inputIndex))
                continue

            path = self._assetPath(assets, clip.contentHash)
            if clip.mediaType is TimelineMediaType.IMAGE:
                arguments.extend(
                    ("-loop", "1", "-t", self._seconds(timeline.durationMilliseconds))
                )
            else:
                duration = self._seconds(clip.endMilliseconds - clip.startMilliseconds)
                arguments.extend(
                    (
                        "-ss",
                        self._seconds(clip.sourceStartMilliseconds or 0),
                        "-t",
                        duration,
                    )
                )
            arguments.extend(("-i", str(path)))
            inputIndex = len(inputIndexes) + 1
            inputIndexes[key] = inputIndex
            inputs.append((clip, inputIndex))
        return tuple(inputs)

    def _appendMusicInput(
        self,
        arguments: list[str],
        timeline: Timeline,
        assets: Mapping[str, Path],
        visualInputCount: int,
    ) -> int | None:
        if not timeline.audioClips:
            return None
        clip = timeline.audioClips[0]
        path = self._assetPath(assets, clip.contentHash)
        inputIndex = 1 + visualInputCount
        if clip.loop:
            arguments.extend(("-stream_loop", "-1"))
        arguments.extend(
            ("-ss", self._seconds(clip.sourceStartMilliseconds), "-i", str(path))
        )
        return inputIndex

    def _appendSubtitleOverlayInput(
        self,
        arguments: list[str],
        subtitleOverlayFile: Path | None,
        visualInputCount: int,
        musicInput: int | None,
    ) -> int | None:
        if subtitleOverlayFile is None:
            return None
        inputIndex = 1 + visualInputCount + (1 if musicInput is not None else 0)
        arguments.extend(("-i", str(subtitleOverlayFile)))
        return inputIndex

    def _filterGraph(
        self,
        timeline: Timeline,
        visualInputs: tuple[tuple[MediaClip, int], ...],
        musicInput: int | None,
        settings: RenderExportSettings,
        subtitleFile: Path | None = None,
        subtitleOverlayInput: int | None = None,
        subtitleCommandFile: Path | None = None,
    ) -> tuple[str, str, str | None]:
        filters = ["[0:v]format=rgba[base]"]
        clipLabels = self._visualClipLabels(filters, visualInputs, settings)
        current = "base"
        for position, (clip, _inputIndex) in enumerate(visualInputs):
            clipLabel = clipLabels[position]
            outputLabel = f"visual{position}"
            filters.append(self._overlayFilter(current, clipLabel, outputLabel, clip))
            current = outputLabel
        if subtitleFile is not None:
            filters.append(self._assSubtitleFilter(current, "subtitle0", subtitleFile))
            current = "subtitle0"
        elif subtitleOverlayInput is not None:
            filters.append(self._subtitleOverlayInputFilter(subtitleOverlayInput))
            filters.append(
                self._subtitleOverlayFilter(current, "subtitleOverlay", "subtitle0")
            )
            current = "subtitle0"
        elif subtitleCommandFile is not None:
            filters.append(
                self._subtitleCommandFilter(current, "subtitle0", subtitleCommandFile)
            )
            current = "subtitle0"
        else:
            for position, subtitle in enumerate(
                clip for scene in timeline.scenes for clip in scene.subtitleClips
            ):
                outputLabel = f"subtitle{position}"
                filters.append(
                    self._subtitleFilter(
                        current,
                        outputLabel,
                        subtitle.text,
                        subtitle.startMilliseconds,
                        subtitle.endMilliseconds,
                    )
                )
                current = outputLabel
        filters.append(f"[{current}]format=yuv420p[vout]")
        audioLabel = self._audioFilter(filters, timeline, musicInput)
        return ";".join(filters), "[vout]", audioLabel

    def _visualClipLabels(
        self,
        filters: list[str],
        visualInputs: tuple[tuple[MediaClip, int], ...],
        settings: RenderExportSettings,
    ) -> tuple[str, ...]:
        groups: dict[VisualTransformKey, list[tuple[int, MediaClip]]] = {}
        for position, (clip, inputIndex) in enumerate(visualInputs):
            key = VisualTransformKey(inputIndex, clip.role)
            groups.setdefault(key, []).append((position, clip))

        labels: list[str | None] = [None] * len(visualInputs)
        for groupPosition, (key, group) in enumerate(groups.items()):
            if len(group) == 1:
                position, clip = group[0]
                label = f"clip{position}"
                filters.append(
                    self._visualFilter(key.inputIndex, clip, label, settings)
                )
                labels[position] = label
                continue

            transformedLabel = f"asset{groupPosition}"
            filters.append(
                self._visualTransformFilter(
                    key.inputIndex,
                    group[0][1],
                    transformedLabel,
                    settings,
                )
            )
            splitLabels = tuple(
                f"{transformedLabel}_{position}" for position in range(len(group))
            )
            filters.append(
                f"[{transformedLabel}]split={len(splitLabels)}"
                + "".join(f"[{label}]" for label in splitLabels)
            )
            for splitLabel, (position, clip) in zip(splitLabels, group, strict=True):
                label = f"clip{position}"
                filters.append(self._clipTimingFilter(splitLabel, clip, label))
                labels[position] = label

        if any(label is None for label in labels):
            raise RenderError(
                "RENDER_VISUAL_FILTER_BUILD_FAILED",
                "A visual clip could not be added to the render filter graph.",
            )
        return tuple(label for label in labels if label is not None)

    def _visualFilter(
        self,
        inputIndex: int,
        clip: MediaClip,
        label: str,
        settings: RenderExportSettings,
    ) -> str:
        return (
            self._visualTransformFilter(inputIndex, clip, f"{label}Prepared", settings)
            + ";"
            + self._clipTimingFilter(f"{label}Prepared", clip, label)
        )

    def _visualTransformFilter(
        self,
        inputIndex: int,
        clip: MediaClip,
        label: str,
        settings: RenderExportSettings,
    ) -> str:
        return (
            f"[{inputIndex}:v]"
            f"{self._visualTransform(clip, settings)},setsar=1[{label}]"
        )

    def _visualTransform(
        self,
        clip: MediaClip,
        settings: RenderExportSettings,
    ) -> str:
        if clip.role is VisualClipRole.BROLL:
            return (
                f"scale={settings.width}:{settings.height}:"
                "force_original_aspect_ratio=decrease"
                f"{self._scaleFlags(settings)},"
                f"pad={settings.width}:{settings.height}:(ow-iw)/2:(oh-ih)/2"
            )
        avatarWidth = max(160, min(480, settings.width // 4))
        return (
            f"scale={avatarWidth}:-2:force_original_aspect_ratio=decrease"
            f"{self._scaleFlags(settings)}"
        )

    def _clipTimingFilter(
        self,
        source: str,
        clip: MediaClip,
        label: str,
    ) -> str:
        start = self._seconds(clip.startMilliseconds)
        duration = self._seconds(clip.endMilliseconds - clip.startMilliseconds)
        return (
            f"[{source}]trim=duration={duration},"
            f"setpts=PTS-STARTPTS+{start}/TB[{label}]"
        )

    def _scaleFlags(self, settings: RenderExportSettings) -> str:
        if settings.profileId in {"fast_preview", "draft"}:
            return ":flags=fast_bilinear"
        return ""

    def _overlayFilter(
        self, base: str, overlay: str, output: str, clip: MediaClip
    ) -> str:
        position = "0:0" if clip.role is VisualClipRole.BROLL else "W-w-48:H-h-48"
        return (
            f"[{base}][{overlay}]overlay={position}:"
            f"eof_action=pass:shortest=0[{output}]"
        )

    def _subtitleFilter(
        self, source: str, output: str, text: str, start: int, end: int
    ) -> str:
        escaped = self._escapeDrawtext(text)
        enabled = f"between(t,{self._seconds(start)},{self._seconds(end)})"
        return (
            f"[{source}]drawtext=text='{escaped}':fontcolor=white:fontsize=52:"
            f"borderw=3:bordercolor=black:x=(w-text_w)/2:y=h-text_h-80:"
            f"enable='{enabled}'[{output}]"
        )

    def _assSubtitleFilter(self, source: str, output: str, subtitleFile: Path) -> str:
        path = self._escapeFilterPath(subtitleFile)
        return f"[{source}]subtitles=filename='{path}'[{output}]"

    def _subtitleOverlayInputFilter(self, inputIndex: int) -> str:
        return f"[{inputIndex}:v]format=rgba,setpts=PTS-STARTPTS[subtitleOverlay]"

    def _subtitleOverlayFilter(self, source: str, overlay: str, output: str) -> str:
        return (
            f"[{source}][{overlay}]overlay=0:0:" f"eof_action=pass:shortest=0[{output}]"
        )

    def _subtitleCommandFilter(
        self, source: str, output: str, commandFile: Path
    ) -> str:
        path = self._escapeFilterPath(commandFile)
        return (
            f"[{source}]sendcmd=f='{path}',"
            "drawtext@subtitle=text='':fontcolor=white:fontsize=52:"
            "borderw=3:bordercolor=black:x=(w-text_w)/2:y=h-text_h-80"
            f"[{output}]"
        )

    def _audioFilter(
        self, filters: list[str], timeline: Timeline, inputIndex: int | None
    ) -> str | None:
        if inputIndex is None:
            return None
        clip = timeline.audioClips[0]
        duration = self._seconds(clip.endMilliseconds - clip.startMilliseconds)
        filters.append(
            f"[{inputIndex}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,"
            f"volume={clip.volume:.3f}[aout]"
        )
        return "[aout]"

    def _assetPath(self, assets: Mapping[str, Path], contentHash: str) -> Path:
        path = assets.get(contentHash)
        if path is None:
            raise RenderError("RENDER_ASSET_NOT_FOUND", "A timeline asset is missing.")
        return path

    def _escapeDrawtext(self, value: str) -> str:
        return (
            value.replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace(":", "\\:")
            .replace("%", "\\%")
            .replace("\n", "\\n")
        )

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


@dataclass(frozen=True)
class VisualInputKey:
    contentHash: str
    mediaType: TimelineMediaType
    sourceStartMilliseconds: int
    durationMilliseconds: int | None

    @classmethod
    def fromClip(cls, clip: MediaClip) -> "VisualInputKey":
        if clip.mediaType is TimelineMediaType.IMAGE:
            return cls(clip.contentHash, clip.mediaType, 0, None)
        return cls(
            clip.contentHash,
            clip.mediaType,
            clip.sourceStartMilliseconds or 0,
            clip.endMilliseconds - clip.startMilliseconds,
        )


@dataclass(frozen=True)
class VisualTransformKey:
    inputIndex: int
    role: VisualClipRole
