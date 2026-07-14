from pathlib import Path

import pytest

from app.render.errors import RenderError
from app.render.models import (
    RenderDiagnostics,
    RenderJobSnapshot,
    RenderOutputPreview,
    RenderReview,
)
from app.repositories.file_render_job_repository import FileRenderJobRepository


def testRenderJobRepositoryPersistsQueue(tmp_path: Path) -> None:
    repository = FileRenderJobRepository()
    snapshot = RenderJobSnapshot(
        "job-1",
        "project-1",
        "final.mp4",
        "queued",
        0.0,
        0,
        5_000,
        None,
        None,
        None,
        None,
        "2026-07-09T00:00:00+00:00",
        "2026-07-09T00:00:00+00:00",
    )

    repository.saveJobs(tmp_path, (snapshot,))
    loaded = repository.loadJobs(tmp_path)

    assert loaded == (snapshot,)
    assert (tmp_path / "render" / "jobs.json").is_file()


def testRenderJobRepositoryRejectsInvalidQueue(tmp_path: Path) -> None:
    queuePath = tmp_path / "render" / "jobs.json"
    queuePath.parent.mkdir(parents=True)
    queuePath.write_text('{"schemaVersion": 999, "jobs": []}', encoding="utf-8")

    with pytest.raises(RenderError) as error:
        FileRenderJobRepository().loadJobs(tmp_path)

    assert error.value.code == "INVALID_RENDER_QUEUE_FILE"


def testRenderJobRepositoryPersistsDiagnostics(tmp_path: Path) -> None:
    repository = FileRenderJobRepository()
    diagnostics = RenderDiagnostics(
        {"commandAvailable": True, "videoCodec": "libx264"},
        {"profileId": "draft", "width": 854},
        {"status": "failed", "returnCode": 1},
        "ffmpeg stderr tail",
    )
    snapshot = RenderJobSnapshot(
        "job-1",
        "project-1",
        "failed.mp4",
        "failed",
        42.0,
        420,
        1_000,
        None,
        None,
        "RENDER_FAILED",
        "FFmpeg could not render the video.",
        "2026-07-10T00:00:00+00:00",
        "2026-07-10T00:00:01+00:00",
        diagnostics=diagnostics,
    )

    repository.saveJobs(tmp_path, (snapshot,))
    loaded = repository.loadJobs(tmp_path)[0]

    assert loaded.diagnostics is not None
    assert loaded.diagnostics.stderrTail == "ffmpeg stderr tail"
    assert loaded.diagnostics.commandSummary["videoCodec"] == "libx264"


def testRenderJobRepositoryPersistsOutputPreview(tmp_path: Path) -> None:
    repository = FileRenderJobRepository()
    preview = RenderOutputPreview(
        tmp_path / "render" / "previews" / "job-1.jpg",
        "file:///render/previews/job-1.jpg",
        5_000,
        2_048,
        1920,
        1080,
        30,
        "2026-07-10T00:00:00+00:00",
    )
    snapshot = RenderJobSnapshot(
        "job-1",
        "project-1",
        "final.mp4",
        "completed",
        100.0,
        5_000,
        5_000,
        tmp_path / "output" / "final.mp4",
        2_048,
        None,
        None,
        "2026-07-10T00:00:00+00:00",
        "2026-07-10T00:00:01+00:00",
        preview=preview,
    )

    repository.saveJobs(tmp_path, (snapshot,))
    loaded = repository.loadJobs(tmp_path)[0]

    assert loaded.preview is not None
    assert loaded.preview.thumbnailUri == "file:///render/previews/job-1.jpg"
    assert loaded.preview.width == 1920


def testRenderJobRepositoryPersistsReview(tmp_path: Path) -> None:
    repository = FileRenderJobRepository()
    review = RenderReview(
        "accepted",
        "Ready for publishing.",
        "2026-07-10T00:00:00+00:00",
    )
    snapshot = RenderJobSnapshot(
        "job-1",
        "project-1",
        "final.mp4",
        "completed",
        100.0,
        5_000,
        5_000,
        tmp_path / "output" / "final.mp4",
        2_048,
        None,
        None,
        "2026-07-10T00:00:00+00:00",
        "2026-07-10T00:00:01+00:00",
        review=review,
    )

    repository.saveJobs(tmp_path, (snapshot,))
    loaded = repository.loadJobs(tmp_path)[0]

    assert loaded.review is not None
    assert loaded.review.status == "accepted"
    assert loaded.review.note == "Ready for publishing."
