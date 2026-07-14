import json
import shutil
import subprocess
from pathlib import Path

from app.media.errors import MediaError


class MediaMetadataService:
    def __init__(
        self, ffmpegPath: str | None = None, timeoutSeconds: float = 120
    ) -> None:
        self.ffprobePath = self._resolveFfprobe(ffmpegPath)
        self.timeoutSeconds = timeoutSeconds

    def probeDurationMilliseconds(self, path: Path) -> int:
        if self.ffprobePath is None:
            raise MediaError(
                "MEDIA_METADATA_TOOL_NOT_FOUND",
                "FFprobe is required to inspect video metadata.",
            )
        try:
            result = subprocess.run(
                (
                    self.ffprobePath,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "json",
                    str(path),
                ),
                capture_output=True,
                check=False,
                text=True,
                timeout=self.timeoutSeconds,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            duration = float(json.loads(result.stdout)["format"]["duration"])
        except (
            OSError,
            ValueError,
            KeyError,
            json.JSONDecodeError,
            subprocess.TimeoutExpired,
        ) as error:
            raise MediaError(
                "MEDIA_METADATA_PROBE_FAILED",
                "FFprobe could not inspect the cached video.",
            ) from error
        if result.returncode != 0 or duration <= 0:
            raise MediaError(
                "MEDIA_METADATA_PROBE_FAILED",
                "FFprobe could not inspect the cached video.",
            )
        return round(duration * 1_000)

    def _resolveFfprobe(self, ffmpegPath: str | None) -> str | None:
        if ffmpegPath:
            ffmpeg = Path(ffmpegPath)
            candidate = ffmpeg.with_name(f"ffprobe{ffmpeg.suffix}")
            if candidate.is_file():
                return str(candidate)
        return shutil.which("ffprobe")
