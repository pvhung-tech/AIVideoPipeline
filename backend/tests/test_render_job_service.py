import json
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.media.cache_manifest import MediaCacheManifest
from app.project.project_model import Project
from app.render.ffmpeg_command_builder import FFmpegCommandBuilder
from app.render.models import (
    FFmpegCommand,
    RenderDraft,
    RenderExportSettings,
    RenderJobSnapshot,
    RenderOutputPreview,
    RenderPlan,
)
from app.repositories.file_render_job_repository import FileRenderJobRepository
from app.services.render_job_service import RenderJobService
from app.services.render_service import RenderService
from app.timeline.models import Timeline, TimelineScene


class FakeTimelineService:
    def __init__(self) -> None:
        timestamp = datetime.now(UTC)
        self.timeline = Timeline(
            "timeline",
            (TimelineScene("scene", 1, 0, 1_000),),
            timestamp,
            timestamp,
        )

    def getTimeline(self) -> Timeline:
        return self.timeline


class FakeCacheService:
    def getManifest(self) -> MediaCacheManifest:
        return MediaCacheManifest(())


class FakeProjectService:
    def __init__(self, projectPath: Path) -> None:
        timestamp = datetime.now(UTC)
        self.project = Project("project", "Project", projectPath, timestamp, timestamp)

    def getCurrentProject(self) -> Project:
        return self.project


class FakeStdout:
    def __init__(self, process: "FakeProcess") -> None:
        self.process = process
        self.lines = iter(("out_time_ms=500000\n", "out_time_ms=1000000\n"))

    def __iter__(self) -> "FakeStdout":
        return self

    def __next__(self) -> str:
        if self.process.terminated:
            raise StopIteration
        time.sleep(0.01)
        return next(self.lines)


class FakeStderr:
    def read(self) -> str:
        return ""


class FakeFailingStderr:
    def read(self) -> str:
        return "ffmpeg failed\ninvalid input stream\n"


class FakeProcess:
    created: list["FakeProcess"] = []

    def __init__(self, arguments: tuple[str, ...], **_kwargs: Any) -> None:
        self.arguments = arguments
        self.terminated = False
        self.stdout = FakeStdout(self)
        self.stderr: FakeStderr | FakeFailingStderr = FakeStderr()
        Path(arguments[-1]).write_bytes(b"rendered")
        self.created.append(self)

    def poll(self) -> int | None:
        return 1 if self.terminated else None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self) -> int:
        return 1 if self.terminated else 0


class FakeFailingProcess(FakeProcess):
    def __init__(self, arguments: tuple[str, ...], **kwargs: Any) -> None:
        super().__init__(arguments, **kwargs)
        self.stderr = FakeFailingStderr()

    def wait(self) -> int:
        return 1


def createJobService(tmp_path: Path) -> RenderJobService:
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffprobe = tmp_path / "ffprobe.exe"
    ffmpeg.write_bytes(b"executable")
    ffprobe.write_bytes(b"executable")
    renderService = RenderService(
        FakeTimelineService(),
        FakeCacheService(),
        FakeProjectService(tmp_path),
        FFmpegCommandBuilder(),
        str(ffmpeg),
    )
    return RenderJobService(renderService)


def waitForStatus(
    service: RenderJobService, jobId: str, expected: set[str]
) -> RenderJobSnapshot:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        snapshot = service.getJob(jobId)
        if snapshot.status in expected:
            return snapshot
        time.sleep(0.02)
    return service.getJob(jobId)


def testRenderJobCompletesAndReportsProgress(tmp_path: Path, monkeypatch: Any) -> None:
    FakeProcess.created = []
    monkeypatch.setattr("app.services.render_job_service.subprocess.Popen", FakeProcess)
    service = createJobService(tmp_path)

    started = service.startRender("job.mp4")
    completed = waitForStatus(service, started.jobId, {"completed"})

    assert completed.status == "completed"
    assert completed.progressPercent == 100.0
    assert completed.outputPath == tmp_path / "output" / "job.mp4"
    assert completed.sizeBytes == len(b"rendered")
    assert completed.diagnostics is not None
    assert completed.diagnostics.metrics["status"] == "completed"
    assert completed.diagnostics.metrics["returnCode"] == 0
    assert completed.diagnostics.commandSummary["videoCodec"] == "libx264"
    assert completed.diagnostics.commandSummary["filterGraphLength"] > 0
    assert completed.diagnostics.commandSummary["filterCount"] == 2
    assert completed.diagnostics.commandSummary["overlayFilterCount"] == 0
    assert completed.diagnostics.commandSummary["drawtextFilterCount"] == 0
    assert completed.diagnostics.settingsSnapshot["profileId"] == "standard"
    assert completed.preview is not None
    assert completed.preview.durationMilliseconds == 1_000
    assert completed.preview.sizeBytes == len(b"rendered")
    assert completed.preview.width == 1920
    assert completed.preview.status == "thumbnail_unavailable"


def testStartRenderDefersFullPlanCreationUntilWorkerPreparation(
    tmp_path: Path, monkeypatch: Any
) -> None:
    FakeProcess.created = []
    monkeypatch.setattr("app.services.render_job_service.subprocess.Popen", FakeProcess)
    service = createJobService(tmp_path)
    renderService = service.renderService
    draftCalls = 0
    planCalls = 0
    planStarted = threading.Event()
    releasePlan = threading.Event()

    def fakeDraft(
        fileName: str | None,
        exportSettings: RenderExportSettings | None,
        _outputNameTemplate: str | None,
    ) -> RenderDraft:
        nonlocal draftCalls
        draftCalls += 1
        settings = exportSettings or RenderExportSettings()
        return RenderDraft(
            "project",
            tmp_path,
            tmp_path / "output" / (fileName or "rendered.mp4"),
            1_000,
            settings,
        )

    def fakePlan(
        fileName: str | None,
        exportSettings: RenderExportSettings | None,
        _outputNameTemplate: str | None,
    ) -> RenderPlan:
        nonlocal planCalls
        planCalls += 1
        planStarted.set()
        releasePlan.wait(2)
        settings = exportSettings or RenderExportSettings()
        outputPath = tmp_path / "output" / (fileName or "rendered.mp4")
        outputPath.parent.mkdir(parents=True, exist_ok=True)
        return RenderPlan(
            "project",
            tmp_path,
            FFmpegCommand(
                ("ffmpeg", str(outputPath.with_suffix(".tmp.mp4"))), outputPath
            ),
            outputPath,
            outputPath.with_suffix(".tmp.mp4"),
            1_000,
            settings,
        )

    monkeypatch.setattr(renderService, "createRenderDraft", fakeDraft)
    monkeypatch.setattr(renderService, "createRenderPlan", fakePlan)

    started = service.startRender("deferred.mp4")

    assert draftCalls == 1
    assert started.status == "queued"
    assert service.jobs[started.jobId].plan is None
    assert planStarted.wait(2)
    preparing = service.getJob(started.jobId)

    assert preparing.status == "preparing"
    assert preparing.progressPercent == 1.0
    assert preparing.diagnostics is not None
    assert preparing.diagnostics.metrics["status"] == "preparing"
    assert planCalls == 1
    releasePlan.set()
    completed = waitForStatus(service, started.jobId, {"completed"})

    assert completed.status == "completed"


def testRenderJobStoresFailureDiagnostics(tmp_path: Path, monkeypatch: Any) -> None:
    FakeProcess.created = []
    monkeypatch.setattr(
        "app.services.render_job_service.subprocess.Popen", FakeFailingProcess
    )
    service = createJobService(tmp_path)

    started = service.startRender("failed.mp4")
    failed = waitForStatus(service, started.jobId, {"failed"})

    assert failed.status == "failed"
    assert failed.diagnostics is not None
    assert failed.diagnostics.metrics["status"] == "failed"
    assert failed.diagnostics.metrics["returnCode"] == 1
    assert failed.diagnostics.stderrTail == "ffmpeg failed\ninvalid input stream\n"


def testRenderJobCanBeCancelled(tmp_path: Path, monkeypatch: Any) -> None:
    FakeProcess.created = []
    monkeypatch.setattr("app.services.render_job_service.subprocess.Popen", FakeProcess)
    service = createJobService(tmp_path)

    started = service.startRender("cancelled.mp4")
    waitForStatus(service, started.jobId, {"running"})
    service.cancelJob(started.jobId)
    cancelled = waitForStatus(service, started.jobId, {"cancelled"})

    assert cancelled.status == "cancelled"
    assert cancelled.errorCode == "RENDER_CANCELLED"
    assert not tuple((tmp_path / "output").glob("*.rendering.mp4"))


def testRenderQueuePersistsAndRunsMultipleJobs(
    tmp_path: Path, monkeypatch: Any
) -> None:
    FakeProcess.created = []
    monkeypatch.setattr("app.services.render_job_service.subprocess.Popen", FakeProcess)
    service = createJobService(tmp_path)

    first = service.startRender("first.mp4")
    second = service.startRender("second.mp4")

    completedFirst = waitForStatus(service, first.jobId, {"completed"})
    completedSecond = waitForStatus(service, second.jobId, {"completed"})
    listed = service.listJobs()

    assert completedFirst.outputPath == tmp_path / "output" / "first.mp4"
    assert completedSecond.outputPath == tmp_path / "output" / "second.mp4"
    assert tuple(job.fileName for job in listed.jobs) == ("first.mp4", "second.mp4")
    assert (tmp_path / "render" / "jobs.json").is_file()


def testRenderJobPersistsExportSettings(tmp_path: Path, monkeypatch: Any) -> None:
    FakeProcess.created = []
    monkeypatch.setattr("app.services.render_job_service.subprocess.Popen", FakeProcess)
    service = createJobService(tmp_path)

    started = service.startRender(
        None,
        RenderExportSettings(1280, 720, 24, 22, "fast", 128),
        "{project}-{date}.mp4",
    )
    completed = waitForStatus(service, started.jobId, {"completed"})
    restored = FileRenderJobRepository().loadJobs(tmp_path)[0]

    assert completed.exportSettings is not None
    assert completed.exportSettings.width == 1280
    assert restored.exportSettings is not None
    assert restored.exportSettings.encoderPreset == "fast"
    assert restored.outputNameTemplate == "{project}-{date}.mp4"
    assert restored.diagnostics is not None
    assert restored.diagnostics.settingsSnapshot["width"] == 1280
    assert restored.preview is not None
    assert restored.preview.width == 1280


def testRenderJobReviewPersistsInHistory(tmp_path: Path, monkeypatch: Any) -> None:
    FakeProcess.created = []
    monkeypatch.setattr("app.services.render_job_service.subprocess.Popen", FakeProcess)
    service = createJobService(tmp_path)

    started = service.startRender("reviewed.mp4")
    completed = waitForStatus(service, started.jobId, {"completed"})
    reviewed = service.reviewJob(
        completed.jobId, "rejected", "Subtitle timing needs adjustment."
    )
    restored = FileRenderJobRepository().loadJobs(tmp_path)[0]

    assert reviewed.review is not None
    assert reviewed.review.status == "rejected"
    assert reviewed.review.note == "Subtitle timing needs adjustment."
    assert restored.review is not None
    assert restored.review.status == "rejected"


def testRenderJobReviewCanBeCleared(tmp_path: Path, monkeypatch: Any) -> None:
    FakeProcess.created = []
    monkeypatch.setattr("app.services.render_job_service.subprocess.Popen", FakeProcess)
    service = createJobService(tmp_path)

    started = service.startRender("review-cleared.mp4")
    completed = waitForStatus(service, started.jobId, {"completed"})
    service.reviewJob(completed.jobId, "accepted", "Ready.")
    cleared = service.clearReviewJob(completed.jobId)
    restored = FileRenderJobRepository().loadJobs(tmp_path)[0]

    assert cleared.review is None
    assert restored.review is None


def testRenderQueueReportExportsReviewHistory(
    tmp_path: Path, monkeypatch: Any
) -> None:
    FakeProcess.created = []
    monkeypatch.setattr("app.services.render_job_service.subprocess.Popen", FakeProcess)
    service = createJobService(tmp_path)

    started = service.startRender("reported.mp4")
    completed = waitForStatus(service, started.jobId, {"completed"})
    service.reviewJob(completed.jobId, "accepted", "Ready for handoff.")
    unreviewed = service.startRender("not-reviewed.mp4")
    waitForStatus(service, unreviewed.jobId, {"completed"})
    csvReport = service.exportQueueReport(
        "csv", "accepted", "completed", "2000-01-01", "2999-01-01"
    )
    jsonReport = service.exportQueueReport(
        "json", "accepted", "completed", "2000-01-01", "2999-01-01"
    )

    csvPath = Path(str(csvReport["reportPath"]))
    jsonPath = Path(str(jsonReport["reportPath"]))
    assert csvReport["jobCount"] == 1
    assert csvReport["summary"]["accepted"] == 1
    assert "review-accepted-status-completed-2000-01-01-to-2999-01-01" in csvPath.name
    assert "review-accepted-status-completed-2000-01-01-to-2999-01-01" in jsonPath.name
    assert csvReport["filters"] == {
        "reviewStatus": "accepted",
        "jobStatus": "completed",
        "dateFrom": "2000-01-01",
        "dateTo": "2999-01-01",
    }
    assert csvPath.exists()
    assert "reported.mp4" in csvPath.read_text(encoding="utf-8")
    assert "not-reviewed.mp4" not in csvPath.read_text(encoding="utf-8")
    assert "Ready for handoff." in csvPath.read_text(encoding="utf-8")
    assert jsonPath.exists()
    assert "reported.mp4" in jsonPath.read_text(encoding="utf-8")
    assert "not-reviewed.mp4" not in jsonPath.read_text(encoding="utf-8")
    assert '"filters"' in jsonPath.read_text(encoding="utf-8")


def testRenderQueueReportFiltersByUpdatedDate(tmp_path: Path) -> None:
    FileRenderJobRepository().saveJobs(
        tmp_path,
        (
            RenderJobSnapshot(
                "old-job",
                "project",
                "old.mp4",
                "completed",
                100.0,
                1_000,
                1_000,
                Path("C:/project/output/old.mp4"),
                1_024,
                None,
                None,
                "2026-07-09T00:00:00+00:00",
                "2026-07-09T12:00:00+00:00",
            ),
            RenderJobSnapshot(
                "new-job",
                "project",
                "new.mp4",
                "completed",
                100.0,
                1_000,
                1_000,
                Path("C:/project/output/new.mp4"),
                1_024,
                None,
                None,
                "2026-07-10T00:00:00+00:00",
                "2026-07-10T12:00:00+00:00",
            ),
        ),
    )
    service = createJobService(tmp_path)

    report = service.exportQueueReport("csv", "all", "all", "2026-07-10", "2026-07-10")
    reportText = Path(str(report["reportPath"])).read_text(encoding="utf-8")

    assert report["jobCount"] == 1
    assert "new.mp4" in reportText
    assert "old.mp4" not in reportText


def testRenderQueueHandoffBundleIncludesReportsManifestAndThumbnails(
    tmp_path: Path,
) -> None:
    previewPath = tmp_path / "render" / "previews" / "job-reviewed.jpg"
    previewPath.parent.mkdir(parents=True, exist_ok=True)
    previewPath.write_bytes(b"thumbnail")
    FileRenderJobRepository().saveJobs(
        tmp_path,
        (
            RenderJobSnapshot(
                "job-reviewed",
                "project",
                "reviewed.mp4",
                "completed",
                100.0,
                1_000,
                1_000,
                tmp_path / "output" / "reviewed.mp4",
                1_024,
                None,
                None,
                "2026-07-10T00:00:00+00:00",
                "2026-07-10T12:00:00+00:00",
                RenderExportSettings(),
                None,
                None,
                RenderOutputPreview(
                    previewPath,
                    previewPath.resolve().as_uri(),
                    1_000,
                    1_024,
                    1920,
                    1080,
                    30,
                    "2026-07-10T12:00:00+00:00",
                ),
            ),
        ),
    )
    service = createJobService(tmp_path)

    bundle = service.exportQueueHandoffBundle(
        "all", "completed", "2026-07-10", "2026-07-10"
    )
    bundlePath = Path(str(bundle["bundlePath"]))
    archivePath = Path(str(bundle["archivePath"]))
    manifestPath = Path(str(bundle["manifestPath"]))

    assert bundle["jobCount"] == 1
    assert bundle["thumbnailCount"] == 1
    assert bundlePath.is_dir()
    assert archivePath.is_file()
    assert archivePath.suffix == ".zip"
    assert (bundlePath / "render-queue-report.csv").is_file()
    assert (bundlePath / "render-queue-report.json").is_file()
    assert (bundlePath / "thumbnails" / "job-reviewed.jpg").read_bytes() == b"thumbnail"
    manifest = json.loads(manifestPath.read_text(encoding="utf-8"))
    assert manifest["summary"]["completed"] == 1
    assert manifest["thumbnails"][0]["jobId"] == "job-reviewed"
    assert manifest["reviewerChecklist"][0]["jobId"] == "job-reviewed"
    assert manifest["reviewerChecklist"][0]["checks"]["watchOutput"] is False


def testImportBundleReviewsAppliesReviewerChecklistToHistory(
    tmp_path: Path,
) -> None:
    repository = FileRenderJobRepository()
    repository.saveJobs(
        tmp_path,
        (
            RenderJobSnapshot(
                "job-reviewable",
                "project",
                "reviewable.mp4",
                "completed",
                100.0,
                1_000,
                1_000,
                tmp_path / "output" / "reviewable.mp4",
                1_024,
                None,
                None,
                "2026-07-10T00:00:00+00:00",
                "2026-07-10T00:00:00+00:00",
            ),
            RenderJobSnapshot(
                "job-skipped",
                "project",
                "skipped.mp4",
                "completed",
                100.0,
                1_000,
                1_000,
                tmp_path / "output" / "skipped.mp4",
                1_024,
                None,
                None,
                "2026-07-10T00:00:00+00:00",
                "2026-07-10T00:00:00+00:00",
            ),
        ),
    )
    manifestPath = (
        tmp_path / "render" / "reports" / "bundles" / "bundle" / "manifest.json"
    )
    manifestPath.parent.mkdir(parents=True)
    manifestPath.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "reviewerChecklist": [
                    {
                        "jobId": "job-reviewable",
                        "decision": "accepted",
                        "notes": "Approved by reviewer.",
                    },
                    {
                        "jobId": "job-skipped",
                        "decision": "not_reviewed",
                        "notes": "Still pending.",
                    },
                    {
                        "jobId": "job-missing",
                        "decision": "rejected",
                        "notes": "Wrong project.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    service = createJobService(tmp_path)

    result = service.importBundleReviews(str(manifestPath))
    snapshots = {snapshot.jobId: snapshot for snapshot in repository.loadJobs(tmp_path)}

    assert result["applied"] == 1
    assert result["skipped"] == 2
    assert result["accepted"] == 1
    assert result["rejected"] == 0
    reportPath = Path(str(result["reportPath"]))
    report = json.loads(reportPath.read_text(encoding="utf-8"))
    assert reportPath.is_file()
    assert reportPath.parent == tmp_path / "render" / "reports" / "imports"
    assert report["manifestPath"] == str(manifestPath)
    assert report["applied"] == 1
    assert report["skipped"] == 2
    assert report["details"][0]["jobId"] == "job-reviewable"
    history = service.listBundleImportReports()
    assert history["reports"][0]["reportPath"] == str(reportPath)
    assert history["reports"][0]["applied"] == 1
    assert history["reports"][0]["skipped"] == 2
    assert history["reports"][0]["detailCount"] == 3
    assert snapshots["job-reviewable"].review is not None
    assert snapshots["job-reviewable"].review.status == "accepted"
    assert snapshots["job-reviewable"].review.note == "Approved by reviewer."
    assert snapshots["job-skipped"].review is None


def testCompareBundleImportReportsShowsDecisionAndReasonChanges(
    tmp_path: Path,
) -> None:
    importsPath = tmp_path / "render" / "reports" / "imports"
    importsPath.mkdir(parents=True)
    basePath = importsPath / "render-bundle-import-20260710-000000-base.json"
    comparePath = importsPath / "render-bundle-import-20260710-010000-next.json"
    basePath.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "importedAt": "2026-07-10T00:00:00+00:00",
                "applied": 1,
                "skipped": 1,
                "accepted": 1,
                "rejected": 0,
                "details": [
                    {
                        "jobId": "job-reviewable",
                        "status": "applied",
                        "decision": "accepted",
                        "reason": None,
                    },
                    {
                        "jobId": "job-skipped",
                        "status": "skipped",
                        "decision": "not_reviewed",
                        "reason": "Decision is not accepted or rejected.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    comparePath.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "importedAt": "2026-07-10T01:00:00+00:00",
                "applied": 0,
                "skipped": 2,
                "accepted": 0,
                "rejected": 0,
                "details": [
                    {
                        "jobId": "job-reviewable",
                        "status": "skipped",
                        "decision": "rejected",
                        "reason": "Render job is not reviewable.",
                    },
                    {
                        "jobId": "job-skipped",
                        "status": "skipped",
                        "decision": "not_reviewed",
                        "reason": "Decision is not accepted or rejected.",
                    },
                    {
                        "jobId": "job-new",
                        "status": "applied",
                        "decision": "accepted",
                        "reason": None,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    service = createJobService(tmp_path)

    comparison = service.compareBundleImportReports(str(basePath), str(comparePath))

    differences = {
        difference["jobId"]: difference for difference in comparison["differences"]
    }
    assert comparison["differenceCount"] == 2
    assert differences["job-reviewable"]["changeType"] == "changed"
    assert differences["job-reviewable"]["base"]["decision"] == "accepted"
    assert differences["job-reviewable"]["compare"]["decision"] == "rejected"
    assert differences["job-reviewable"]["compare"]["reason"] == (
        "Render job is not reviewable."
    )
    assert differences["job-new"]["changeType"] == "added"
    assert comparison["baseReport"]["reportPath"] == str(basePath)
    assert comparison["compareReport"]["reportPath"] == str(comparePath)

    csvReport = service.exportBundleImportComparisonReport(
        str(basePath), str(comparePath), "csv", "added"
    )
    csvPath = Path(str(csvReport["reportPath"]))
    csvText = csvPath.read_text(encoding="utf-8")
    assert csvReport["format"] == "csv"
    assert csvReport["changeFilter"] == "added"
    assert csvReport["differenceCount"] == 1
    assert csvPath.parent == tmp_path / "render" / "reports" / "import-comparisons"
    assert "job-new" in csvText
    assert "job-reviewable" not in csvText

    jsonReport = service.exportBundleImportComparisonReport(
        str(basePath), str(comparePath), "json", "changed"
    )
    jsonPath = Path(str(jsonReport["reportPath"]))
    jsonContent = json.loads(jsonPath.read_text(encoding="utf-8"))
    assert jsonReport["format"] == "json"
    assert jsonReport["changeFilter"] == "changed"
    assert jsonContent["schemaVersion"] == 1
    assert jsonContent["differenceCount"] == 1
    assert jsonContent["differences"][0]["jobId"] == "job-reviewable"

    reportHistory = service.listBundleImportComparisonReports()
    reportsByFormat = {
        str(report["format"]): report for report in reportHistory["reports"]
    }
    assert set(reportsByFormat) == {"csv", "json"}
    assert reportsByFormat["csv"]["changeFilter"] == "added"
    assert reportsByFormat["csv"]["differenceCount"] == 1
    assert reportsByFormat["csv"]["baseReportPath"] is None
    assert reportsByFormat["json"]["changeFilter"] == "changed"
    assert reportsByFormat["json"]["differenceCount"] == 1
    assert reportsByFormat["json"]["baseReportPath"] == str(basePath)
    assert reportsByFormat["json"]["compareReportPath"] == str(comparePath)
    assert reportsByFormat["json"]["pinned"] is False

    pinResult = service.setBundleImportComparisonReportPinned(str(jsonPath), True)
    pinnedHistory = service.listBundleImportComparisonReports()
    assert pinResult["pinned"] is True
    assert pinResult["pinnedCount"] == 1
    assert pinnedHistory["reports"][0]["reportPath"] == str(jsonPath)
    assert pinnedHistory["reports"][0]["pinned"] is True

    unpinResult = service.setBundleImportComparisonReportPinned(str(jsonPath), False)
    assert unpinResult["pinned"] is False
    assert unpinResult["pinnedCount"] == 0

    csvPreview = service.previewBundleImportComparisonReport(str(csvPath), 1)
    assert csvPreview["rows"][0]["jobId"] == "job-new"
    assert csvPreview["totalRows"] == 1
    assert csvPreview["truncated"] is False

    jsonPreview = service.previewBundleImportComparisonReport(str(jsonPath), 1)
    assert jsonPreview["rows"][0]["jobId"] == "job-reviewable"
    assert jsonPreview["rows"][0]["compareDecision"] == "rejected"
    assert jsonPreview["totalRows"] == 1


def testRenderJobReviewRequiresCompletedOutput(tmp_path: Path) -> None:
    repository = FileRenderJobRepository()
    repository.saveJobs(
        tmp_path,
        (
            RenderJobSnapshot(
                "job-failed",
                "project",
                "failed.mp4",
                "failed",
                0.0,
                0,
                1_000,
                None,
                None,
                None,
                None,
                "2026-07-09T00:00:00+00:00",
                "2026-07-09T00:00:00+00:00",
            ),
        ),
    )
    service = createJobService(tmp_path)

    with pytest.raises(Exception) as error:
        service.reviewJob("job-failed", "accepted", None)

    assert getattr(error.value, "code", "") == "RENDER_JOB_NOT_REVIEWABLE"


def testRunningJobRestoresAsInterrupted(tmp_path: Path, monkeypatch: Any) -> None:
    FakeProcess.created = []
    monkeypatch.setattr("app.services.render_job_service.subprocess.Popen", FakeProcess)
    repository = FileRenderJobRepository()
    repository.saveJobs(
        tmp_path,
        (
            RenderJobSnapshot(
                "job-restart",
                "project",
                "restart.mp4",
                "running",
                42.0,
                420,
                1_000,
                None,
                None,
                None,
                None,
                "2026-07-09T00:00:00+00:00",
                "2026-07-09T00:00:01+00:00",
            ),
        ),
    )
    service = createJobService(tmp_path)

    restored = service.listJobs().jobs[0]
    resumed = service.resumeJob(restored.jobId)
    completed = waitForStatus(service, resumed.jobId, {"completed"})

    assert restored.status == "interrupted"
    assert restored.errorCode == "RENDER_INTERRUPTED"
    assert resumed.status == "queued"
    assert completed.status == "completed"


def testPreparingJobRestoresAsInterrupted(tmp_path: Path, monkeypatch: Any) -> None:
    FakeProcess.created = []
    monkeypatch.setattr("app.services.render_job_service.subprocess.Popen", FakeProcess)
    repository = FileRenderJobRepository()
    repository.saveJobs(
        tmp_path,
        (
            RenderJobSnapshot(
                "job-preparing-restart",
                "project",
                "preparing-restart.mp4",
                "preparing",
                1.0,
                0,
                1_000,
                None,
                None,
                None,
                None,
                "2026-07-09T00:00:00+00:00",
                "2026-07-09T00:00:01+00:00",
            ),
        ),
    )
    service = createJobService(tmp_path)

    restored = service.listJobs().jobs[0]

    assert restored.status == "interrupted"
    assert restored.errorCode == "RENDER_INTERRUPTED"


def testCleanupKeepsActiveJobsAndRecentHistory(tmp_path: Path) -> None:
    repository = FileRenderJobRepository()
    jobs = tuple(
        RenderJobSnapshot(
            f"job-{index}",
            "project",
            f"history-{index}.mp4",
            "completed",
            100.0,
            1_000,
            1_000,
            tmp_path / "output" / f"history-{index}.mp4",
            1_000,
            None,
            None,
            f"2026-07-09T00:00:{index:02d}+00:00",
            f"2026-07-09T00:00:{index:02d}+00:00",
        )
        for index in range(4)
    ) + (
        RenderJobSnapshot(
            "job-active",
            "project",
            "active.mp4",
            "queued",
            0.0,
            0,
            1_000,
            None,
            None,
            None,
            None,
            "2026-07-09T00:00:10+00:00",
            "2026-07-09T00:00:10+00:00",
        ),
    )
    repository.saveJobs(tmp_path, jobs)
    service = createJobService(tmp_path)

    cleaned = service.cleanupHistory(2)
    fileNames = tuple(job.fileName for job in cleaned.jobs)

    assert fileNames == ("history-2.mp4", "history-3.mp4", "active.mp4")


def testRenderJobDoesNotPersistWhenPreflightFails(
    tmp_path: Path, monkeypatch: Any
) -> None:
    service = createJobService(tmp_path)
    (tmp_path / "ffprobe.exe").unlink()
    monkeypatch.setattr("app.services.render_service.shutil.which", lambda _name: None)

    with pytest.raises(Exception) as error:
        service.startRender("preflight-fail.mp4")

    assert getattr(error.value, "code", "") == "FFPROBE_NOT_FOUND"
    assert not (tmp_path / "render" / "jobs.json").exists()
