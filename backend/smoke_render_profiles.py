import json
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from app.media.cache_manifest import MediaCacheManifest
from app.project.project_model import Project
from app.render.ffmpeg_command_builder import FFmpegCommandBuilder
from app.render.models import RENDER_PROFILES
from app.services.render_service import RenderService
from app.timeline.models import Timeline, TimelineScene


class SmokeTimelineService:
    def __init__(self) -> None:
        timestamp = datetime.now(UTC)
        self.timeline = Timeline(
            "timeline-smoke",
            (TimelineScene("scene-smoke", 1, 0, 500),),
            timestamp,
            timestamp,
        )

    def getTimeline(self) -> Timeline:
        return self.timeline


class SmokeCacheService:
    def getManifest(self) -> MediaCacheManifest:
        return MediaCacheManifest(())


class SmokeProjectService:
    def __init__(self, projectPath: Path) -> None:
        timestamp = datetime.now(UTC)
        self.project = Project(
            "render-profile-smoke",
            "Render Profile Smoke",
            projectPath,
            timestamp,
            timestamp,
        )

    def getCurrentProject(self) -> Project:
        return self.project


def main() -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        raise RuntimeError("FFmpeg and FFprobe must be available on PATH.")
    with tempfile.TemporaryDirectory(prefix="render-profile-smoke-") as workspace:
        projectPath = Path(workspace)
        service = RenderService(
            SmokeTimelineService(),
            SmokeCacheService(),
            SmokeProjectService(projectPath),
            FFmpegCommandBuilder(),
            ffmpeg,
        )
        results = []
        for profile in RENDER_PROFILES.values():
            result = service.render(
                None,
                profile.settings,
                f"smoke-{profile.profileId}.mp4",
            )
            previewPath = (
                projectPath / "render" / "previews" / f"{profile.profileId}.jpg"
            )
            preview = service.createOutputPreview(
                result,
                profile.settings,
                previewPath,
                datetime.now(UTC).isoformat(),
            )
            metadata = probe(ffprobe, result.outputPath)
            assert int(metadata["width"]) == profile.settings.width
            assert int(metadata["height"]) == profile.settings.height
            assert preview.status == "available"
            assert preview.thumbnailPath == previewPath
            assert preview.thumbnailUri is not None
            assert previewPath.is_file()
            assert previewPath.stat().st_size > 0
            results.append(
                {
                    "profileId": profile.profileId,
                    "outputPath": str(result.outputPath),
                    "previewPath": str(previewPath),
                    "sizeBytes": result.sizeBytes,
                    "previewSizeBytes": previewPath.stat().st_size,
                    "width": metadata["width"],
                    "height": metadata["height"],
                    "frameRate": metadata["r_frame_rate"],
                }
            )
        print(json.dumps({"profiles": results}, indent=2))


def probe(ffprobe: str, outputPath: Path) -> dict[str, str]:
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate",
            "-of",
            "json",
            str(outputPath),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    data = json.loads(completed.stdout)
    streams = data.get("streams")
    if not isinstance(streams, list) or not streams:
        raise RuntimeError("Rendered file has no video stream.")
    stream = streams[0]
    if not isinstance(stream, dict):
        raise RuntimeError("Rendered video stream metadata is invalid.")
    return {str(key): str(value) for key, value in stream.items()}


if __name__ == "__main__":
    main()
