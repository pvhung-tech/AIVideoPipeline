import subprocess
from pathlib import Path

import pytest
from PIL import Image

from app.media.media_fingerprint_service import MediaFingerprintService


def testImageFingerprintIsStableAcrossBrightnessChanges(tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    reversedImage = tmp_path / "reversed.png"
    pixels = [column * 28 for _row in range(8) for column in range(9)]
    for path, values in (
        (first, pixels),
        (second, [min(value + 10, 255) for value in pixels]),
        (reversedImage, list(reversed(pixels))),
    ):
        image = Image.new("L", (9, 8))
        image.putdata(values)
        image.save(path)

    service = MediaFingerprintService()

    assert (
        service.fingerprint(first).perceptualHash
        == service.fingerprint(second).perceptualHash
    )
    assert (
        service.fingerprint(first).perceptualHash
        != service.fingerprint(reversedImage).perceptualHash
    )


def testVideoFingerprintUsesRepresentativeFrameSequence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frameOne = bytes([column for _row in range(8) for column in range(9)])
    frameTwo = bytes([8 - column for _row in range(8) for column in range(9)])

    def run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess([], 0, frameOne + frameTwo, b"")

    monkeypatch.setattr(subprocess, "run", run)
    fingerprint = MediaFingerprintService(ffmpegPath="ffmpeg").fingerprint(
        tmp_path / "clip.mp4"
    )

    assert fingerprint.videoFingerprint == (
        "dhash64-sequence-v1:0000000000000000,ffffffffffffffff"
    )
