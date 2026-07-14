import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.media.errors import MediaError

IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}
AUDIO_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav"}
FRAME_WIDTH = 9
FRAME_HEIGHT = 8
FRAME_BYTES = FRAME_WIDTH * FRAME_HEIGHT
MAX_VIDEO_FRAMES = 12


@dataclass(frozen=True)
class MediaFingerprints:
    perceptualHash: str | None = None
    videoFingerprint: str | None = None


class MediaFingerprintService:
    def __init__(
        self, ffmpegPath: str | None = None, timeoutSeconds: float = 120
    ) -> None:
        if timeoutSeconds <= 0:
            raise ValueError("Fingerprint timeout must be positive.")
        self.ffmpegPath = ffmpegPath.strip() if ffmpegPath else None
        self.timeoutSeconds = timeoutSeconds

    def fingerprint(
        self, path: Path, extensionHint: str | None = None
    ) -> MediaFingerprints:
        extension = (extensionHint or path.suffix).lower()
        if extension in IMAGE_EXTENSIONS:
            return MediaFingerprints(perceptualHash=self._imageHash(path))
        if extension in VIDEO_EXTENSIONS:
            return MediaFingerprints(videoFingerprint=self._videoFingerprint(path))
        return MediaFingerprints()

    def _imageHash(self, path: Path) -> str:
        try:
            with Image.open(path) as image:
                grayscale = image.convert("L").resize(
                    (FRAME_WIDTH, FRAME_HEIGHT), Image.Resampling.LANCZOS
                )
                return f"dhash64-v1:{self._differenceHash(bytes(grayscale.getdata()))}"
        except (OSError, UnidentifiedImageError) as error:
            raise MediaError(
                "MEDIA_IMAGE_FINGERPRINT_FAILED",
                "Unable to fingerprint cached image.",
            ) from error

    def _videoFingerprint(self, path: Path) -> str:
        executable = self.ffmpegPath or shutil.which("ffmpeg")
        if executable is None:
            raise MediaError(
                "MEDIA_FINGERPRINT_TOOL_NOT_FOUND",
                "FFmpeg is required to fingerprint cached video.",
            )
        command = (
            executable,
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(path),
            "-an",
            "-vf",
            "fps=1/10,scale=9:8:flags=area,format=gray",
            "-frames:v",
            str(MAX_VIDEO_FRAMES),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "pipe:1",
        )
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                check=False,
                timeout=self.timeoutSeconds,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise MediaError(
                "MEDIA_VIDEO_FINGERPRINT_FAILED",
                "Unable to fingerprint cached video.",
            ) from error
        if result.returncode != 0:
            raise MediaError(
                "MEDIA_VIDEO_FINGERPRINT_FAILED",
                "FFmpeg could not fingerprint cached video.",
            )
        frames = tuple(
            result.stdout[index : index + FRAME_BYTES]
            for index in range(0, len(result.stdout), FRAME_BYTES)
            if len(result.stdout[index : index + FRAME_BYTES]) == FRAME_BYTES
        )
        if not frames:
            raise MediaError(
                "MEDIA_VIDEO_FINGERPRINT_FAILED",
                "FFmpeg returned no frames for cached video.",
            )
        hashes = ",".join(self._differenceHash(frame) for frame in frames)
        return f"dhash64-sequence-v1:{hashes}"

    def _differenceHash(self, pixels: bytes) -> str:
        value = 0
        for row in range(FRAME_HEIGHT):
            start = row * FRAME_WIDTH
            for column in range(FRAME_WIDTH - 1):
                value = (value << 1) | int(
                    pixels[start + column] > pixels[start + column + 1]
                )
        return f"{value:016x}"
