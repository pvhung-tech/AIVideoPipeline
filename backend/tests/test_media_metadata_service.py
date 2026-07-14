import subprocess
from pathlib import Path
from unittest.mock import patch

from app.media.media_metadata_service import MediaMetadataService


def testProbesVideoDurationInMilliseconds(tmp_path: Path) -> None:
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffprobe = tmp_path / "ffprobe.exe"
    ffmpeg.write_bytes(b"")
    ffprobe.write_bytes(b"")
    result = subprocess.CompletedProcess([], 0, '{"format":{"duration":"12.345"}}', "")

    with patch("app.media.media_metadata_service.subprocess.run", return_value=result):
        duration = MediaMetadataService(str(ffmpeg)).probeDurationMilliseconds(
            tmp_path / "video.mp4"
        )

    assert duration == 12_345

