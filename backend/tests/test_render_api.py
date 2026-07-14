from pathlib import Path

from fastapi.testclient import TestClient

from app.config.dependencies import getRenderJobService, getRenderService
from app.main import createApp
from app.render.models import (
    RenderExportSettings,
    RenderJobQueueSnapshot,
    RenderJobSnapshot,
    RenderPreflightCheck,
    RenderPreflightGroup,
    RenderPreflightReport,
    RenderResult,
    RenderReview,
)


class FakeRenderService:
    def checkRenderPreflight(
        self,
        fileName: str | None = "rendered.mp4",
        exportSettings: RenderExportSettings | None = None,
        outputNameTemplate: str | None = None,
    ) -> RenderPreflightReport:
        return RenderPreflightReport(
            True,
            (
                RenderPreflightGroup(
                    "Tool",
                    "passed",
                    (
                        RenderPreflightCheck(
                            "FFMPEG_AVAILABLE", "FFmpeg is available.", "passed"
                        ),
                    ),
                ),
            ),
            "final.mp4",
            5_000,
        )

    def render(
        self,
        fileName: str | None = "rendered.mp4",
        exportSettings: RenderExportSettings | None = None,
        outputNameTemplate: str | None = None,
    ) -> RenderResult:
        resolved = fileName or "Project-20260709-120000.mp4"
        return RenderResult(Path("C:/project/output") / resolved, 5_000, 1_024)


class FakeRenderJobService:
    def startRender(
        self,
        fileName: str | None = "rendered.mp4",
        exportSettings: RenderExportSettings | None = None,
        outputNameTemplate: str | None = None,
    ) -> RenderJobSnapshot:
        return self._snapshot(
            fileName or "Project-20260709-120000.mp4", "running", 25.0
        )

    def getJob(self, jobId: str) -> RenderJobSnapshot:
        return self._snapshot("final.mp4", "completed", 100.0, jobId)

    def listJobs(self) -> RenderJobQueueSnapshot:
        return RenderJobQueueSnapshot((self._snapshot("final.mp4", "queued", 0.0),))

    def cancelJob(self, jobId: str) -> RenderJobSnapshot:
        return self._snapshot("final.mp4", "cancelled", 50.0, jobId)

    def resumeJob(self, jobId: str) -> RenderJobSnapshot:
        return self._snapshot("final.mp4", "queued", 0.0, jobId)

    def retryJob(self, jobId: str) -> RenderJobSnapshot:
        return self._snapshot("final.mp4", "queued", 0.0, jobId)

    def reviewJob(
        self, jobId: str, status: str, note: str | None = None
    ) -> RenderJobSnapshot:
        return RenderJobSnapshot(
            jobId,
            "project-1",
            "final.mp4",
            "completed",
            100.0,
            5_000,
            5_000,
            Path("C:/project/output/final.mp4"),
            1_024,
            None,
            None,
            review=RenderReview(status, note, "2026-07-10T00:00:00+00:00"),
        )

    def clearReviewJob(self, jobId: str) -> RenderJobSnapshot:
        return self._snapshot("final.mp4", "completed", 100.0, jobId)

    def exportQueueReport(
        self,
        reportFormat: str = "csv",
        reviewStatus: str = "all",
        jobStatus: str = "all",
        dateFrom: str | None = None,
        dateTo: str | None = None,
    ) -> dict[str, object]:
        return {
            "format": reportFormat,
            "reportPath": f"C:/project/render/reports/report.{reportFormat}",
            "jobCount": 1,
            "generatedAt": "2026-07-10T00:00:00+00:00",
            "summary": {
                "total": 1,
                "accepted": 0,
                "rejected": 0,
                "notReviewed": 1,
                "completed": 1,
                "failed": 0,
            },
            "filters": {
                "reviewStatus": reviewStatus,
                "jobStatus": jobStatus,
                "dateFrom": dateFrom,
                "dateTo": dateTo,
            },
        }

    def exportQueueHandoffBundle(
        self,
        reviewStatus: str = "all",
        jobStatus: str = "all",
        dateFrom: str | None = None,
        dateTo: str | None = None,
    ) -> dict[str, object]:
        return {
            "bundlePath": "C:/project/render/reports/bundles/bundle",
            "archivePath": "C:/project/render/reports/bundles/bundle.zip",
            "manifestPath": "C:/project/render/reports/bundles/bundle/manifest.json",
            "csvReportPath": (
                "C:/project/render/reports/bundles/bundle/render-queue-report.csv"
            ),
            "jsonReportPath": (
                "C:/project/render/reports/bundles/bundle/render-queue-report.json"
            ),
            "jobCount": 1,
            "thumbnailCount": 1,
            "generatedAt": "2026-07-10T00:00:00+00:00",
            "summary": {
                "total": 1,
                "accepted": 0,
                "rejected": 0,
                "notReviewed": 1,
                "completed": 1,
                "failed": 0,
            },
            "filters": {
                "reviewStatus": reviewStatus,
                "jobStatus": jobStatus,
                "dateFrom": dateFrom,
                "dateTo": dateTo,
            },
        }

    def importBundleReviews(self, manifestPath: str) -> dict[str, object]:
        return {
            "manifestPath": manifestPath,
            "reportPath": (
                "C:/project/render/reports/imports/"
                "render-bundle-import-20260710-000000-abcd1234.json"
            ),
            "applied": 1,
            "skipped": 1,
            "accepted": 1,
            "rejected": 0,
            "details": [
                {
                    "jobId": "job-1",
                    "status": "applied",
                    "decision": "accepted",
                    "reason": None,
                },
                {
                    "jobId": "job-2",
                    "status": "skipped",
                    "decision": "not_reviewed",
                    "reason": "Decision is not accepted or rejected.",
                },
            ],
        }

    def listBundleImportReports(self) -> dict[str, object]:
        return {
            "reports": [
                {
                    "reportPath": (
                        "C:/project/render/reports/imports/"
                        "render-bundle-import-20260710-000000-abcd1234.json"
                    ),
                    "importedAt": "2026-07-10T00:00:00+00:00",
                    "manifestPath": (
                        "C:/project/render/reports/bundles/bundle/manifest.json"
                    ),
                    "sourceBundlePath": "C:/project/render/reports/bundles/bundle",
                    "sourceGeneratedAt": "2026-07-10T00:00:00+00:00",
                    "applied": 1,
                    "skipped": 1,
                    "accepted": 1,
                    "rejected": 0,
                    "detailCount": 2,
                },
            ]
        }

    def compareBundleImportReports(
        self, baseReportPath: str, compareReportPath: str
    ) -> dict[str, object]:
        return {
            "baseReport": {
                "reportPath": baseReportPath,
                "importedAt": "2026-07-10T00:00:00+00:00",
                "manifestPath": None,
                "sourceBundlePath": None,
                "sourceGeneratedAt": None,
                "applied": 1,
                "skipped": 1,
                "accepted": 1,
                "rejected": 0,
                "detailCount": 2,
            },
            "compareReport": {
                "reportPath": compareReportPath,
                "importedAt": "2026-07-10T01:00:00+00:00",
                "manifestPath": None,
                "sourceBundlePath": None,
                "sourceGeneratedAt": None,
                "applied": 1,
                "skipped": 1,
                "accepted": 0,
                "rejected": 1,
                "detailCount": 2,
            },
            "differenceCount": 1,
            "differences": [
                {
                    "jobId": "job-1",
                    "changeType": "changed",
                    "base": {
                        "jobId": "job-1",
                        "status": "applied",
                        "decision": "accepted",
                        "reason": None,
                    },
                    "compare": {
                        "jobId": "job-1",
                        "status": "applied",
                        "decision": "rejected",
                        "reason": None,
                    },
                }
            ],
        }

    def exportBundleImportComparisonReport(
        self,
        baseReportPath: str,
        compareReportPath: str,
        reportFormat: str = "csv",
        changeFilter: str = "all",
    ) -> dict[str, object]:
        return {
            "format": reportFormat,
            "reportPath": (
                "C:/project/render/reports/import-comparisons/"
                f"render-import-comparison.{reportFormat}"
            ),
            "generatedAt": "2026-07-10T02:00:00+00:00",
            "changeFilter": changeFilter,
            "differenceCount": 1,
            "baseReport": {"reportPath": baseReportPath},
            "compareReport": {"reportPath": compareReportPath},
        }

    def listBundleImportComparisonReports(self) -> dict[str, object]:
        return {
            "reports": [
                {
                    "reportPath": (
                        "C:/project/render/reports/import-comparisons/"
                        "render-import-comparison-20260710-020000-changed.json"
                    ),
                    "format": "json",
                    "generatedAt": "2026-07-10T02:00:00+00:00",
                    "changeFilter": "changed",
                    "differenceCount": 1,
                    "baseReportPath": (
                        "C:/project/render/reports/imports/"
                        "render-bundle-import-20260710-000000-abcd1234.json"
                    ),
                    "compareReportPath": (
                        "C:/project/render/reports/imports/"
                        "render-bundle-import-20260710-010000-abcd1234.json"
                    ),
                    "pinned": False,
                }
            ]
        }

    def previewBundleImportComparisonReport(
        self, reportPath: str, maxRows: int = 25
    ) -> dict[str, object]:
        return {
            "report": {
                "reportPath": reportPath,
                "format": "json",
                "generatedAt": "2026-07-10T02:00:00+00:00",
                "changeFilter": "changed",
                "differenceCount": 1,
                "baseReportPath": None,
                "compareReportPath": None,
                "pinned": False,
            },
            "columns": [
                "jobId",
                "changeType",
                "baseStatus",
                "baseDecision",
                "baseReason",
                "compareStatus",
                "compareDecision",
                "compareReason",
            ],
            "rows": [
                {
                    "jobId": "job-1",
                    "changeType": "changed",
                    "baseStatus": "applied",
                    "baseDecision": "accepted",
                    "baseReason": "",
                    "compareStatus": "applied",
                    "compareDecision": "rejected",
                    "compareReason": "",
                }
            ][:maxRows],
            "totalRows": 1,
            "truncated": False,
        }

    def setBundleImportComparisonReportPinned(
        self, reportPath: str, pinned: bool
    ) -> dict[str, object]:
        return {
            "reportPath": reportPath,
            "pinned": pinned,
            "pinnedCount": 1 if pinned else 0,
        }

    def cleanupHistory(self, keepCount: int = 100) -> RenderJobQueueSnapshot:
        return RenderJobQueueSnapshot(
            (self._snapshot(f"kept-{keepCount}.mp4", "completed", 100.0),)
        )

    def _snapshot(
        self,
        fileName: str,
        status: str,
        progress: float,
        jobId: str = "job-1",
    ) -> RenderJobSnapshot:
        return RenderJobSnapshot(
            jobId,
            "project-1",
            fileName,
            status,
            progress,
            2_500,
            5_000,
            Path("C:/project/output/final.mp4") if status == "completed" else None,
            1_024 if status == "completed" else None,
            None,
            None,
        )


def testRenderApiReturnsOutputMetadata() -> None:
    app = createApp()
    app.dependency_overrides[getRenderService] = FakeRenderService
    client = TestClient(app)

    response = client.post("/api/render", json={"fileName": "final.mp4"})

    assert response.status_code == 200
    assert response.json()["data"]["outputPath"].endswith("final.mp4")
    assert response.json()["data"]["durationMilliseconds"] == 5_000


def testRenderApiAcceptsExportSettingsAndTemplate() -> None:
    app = createApp()
    app.dependency_overrides[getRenderJobService] = FakeRenderJobService
    client = TestClient(app)

    response = client.post(
        "/api/render/jobs",
        json={
            "outputNameTemplate": "{project}-{datetime}.mp4",
            "width": 1280,
            "height": 720,
            "frameRate": 24,
            "crf": 22,
            "encoderPreset": "fast",
            "audioBitrateKbps": 128,
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "running"


def testRenderApiReturnsPreflightReport() -> None:
    app = createApp()
    app.dependency_overrides[getRenderService] = FakeRenderService
    client = TestClient(app)

    response = client.post("/api/render/preflight", json={"fileName": "final.mp4"})

    assert response.status_code == 200
    assert response.json()["data"]["ready"] is True
    assert response.json()["data"]["groups"][0]["group"] == "Tool"


def testRenderApiListsNamedProfiles() -> None:
    app = createApp()
    client = TestClient(app)

    response = client.get("/api/render/profiles")

    assert response.status_code == 200
    profiles = response.json()["data"]["profiles"]
    assert [profile["profileId"] for profile in profiles] == [
        "fast_preview",
        "draft",
        "standard",
        "high_quality",
        "archive",
    ]
    assert profiles[0]["settings"]["profileId"] == "fast_preview"
    assert profiles[0]["settings"]["width"] == 640


def testRenderJobApiReturnsProgressAndCancelState() -> None:
    app = createApp()
    app.dependency_overrides[getRenderJobService] = FakeRenderJobService
    client = TestClient(app)

    started = client.post("/api/render/jobs", json={"fileName": "final.mp4"})
    listed = client.get("/api/render/jobs")
    loaded = client.get("/api/render/jobs/job-1")
    resumed = client.post("/api/render/jobs/job-1/resume")
    retried = client.post("/api/render/jobs/job-1/retry")
    cancelled = client.post("/api/render/jobs/job-1/cancel")
    reviewed = client.post(
        "/api/render/jobs/job-1/review",
        json={"status": "accepted", "note": "Looks ready."},
    )
    cleared = client.delete("/api/render/jobs/job-1/review")
    report = client.post(
        "/api/render/jobs/report",
        json={
            "format": "csv",
            "reviewStatus": "accepted",
            "jobStatus": "completed",
            "dateFrom": "2026-07-10",
            "dateTo": "2026-07-10",
        },
    )
    bundle = client.post(
        "/api/render/jobs/report/bundle",
        json={
            "format": "json",
            "reviewStatus": "accepted",
            "jobStatus": "completed",
            "dateFrom": "2026-07-10",
            "dateTo": "2026-07-10",
        },
    )
    imported = client.post(
        "/api/render/jobs/report/bundle/import-review",
        json={
            "manifestPath": ("C:/project/render/reports/bundles/bundle/manifest.json")
        },
    )
    imports = client.get("/api/render/jobs/report/bundle/imports")
    comparison = client.post(
        "/api/render/jobs/report/bundle/imports/compare",
        json={
            "baseReportPath": (
                "C:/project/render/reports/imports/"
                "render-bundle-import-20260710-000000-abcd1234.json"
            ),
            "compareReportPath": (
                "C:/project/render/reports/imports/"
                "render-bundle-import-20260710-010000-abcd1234.json"
            ),
        },
    )
    comparisonReport = client.post(
        "/api/render/jobs/report/bundle/imports/compare/report",
        json={
            "baseReportPath": (
                "C:/project/render/reports/imports/"
                "render-bundle-import-20260710-000000-abcd1234.json"
            ),
            "compareReportPath": (
                "C:/project/render/reports/imports/"
                "render-bundle-import-20260710-010000-abcd1234.json"
            ),
            "format": "json",
            "changeFilter": "changed",
        },
    )
    comparisonReports = client.get(
        "/api/render/jobs/report/bundle/imports/compare/reports"
    )
    comparisonPreview = client.post(
        "/api/render/jobs/report/bundle/imports/compare/reports/preview",
        json={
            "reportPath": (
                "C:/project/render/reports/import-comparisons/"
                "render-import-comparison-20260710-020000-changed.json"
            ),
            "maxRows": 10,
        },
    )
    comparisonPin = client.post(
        "/api/render/jobs/report/bundle/imports/compare/reports/pin",
        json={
            "reportPath": (
                "C:/project/render/reports/import-comparisons/"
                "render-import-comparison-20260710-020000-changed.json"
            ),
            "pinned": True,
        },
    )
    cleaned = client.post("/api/render/jobs/cleanup", json={"keepCount": 3})

    assert started.status_code == 200
    assert started.json()["data"]["status"] == "running"
    assert started.json()["data"]["progressPercent"] == 25.0
    assert listed.json()["data"]["jobs"][0]["status"] == "queued"
    assert loaded.json()["data"]["status"] == "completed"
    assert loaded.json()["data"]["outputPath"].endswith("final.mp4")
    assert resumed.json()["data"]["status"] == "queued"
    assert retried.json()["data"]["status"] == "queued"
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert reviewed.json()["data"]["review"]["status"] == "accepted"
    assert reviewed.json()["data"]["review"]["note"] == "Looks ready."
    assert cleared.json()["data"]["review"] is None
    assert report.json()["data"]["format"] == "csv"
    assert report.json()["data"]["jobCount"] == 1
    assert report.json()["data"]["filters"] == {
        "reviewStatus": "accepted",
        "jobStatus": "completed",
        "dateFrom": "2026-07-10",
        "dateTo": "2026-07-10",
    }
    assert bundle.json()["data"]["bundlePath"].endswith("/bundle")
    assert bundle.json()["data"]["thumbnailCount"] == 1
    assert imported.json()["data"]["applied"] == 1
    assert imported.json()["data"]["skipped"] == 1
    assert imported.json()["data"]["reportPath"].endswith(".json")
    assert imports.json()["data"]["reports"][0]["applied"] == 1
    assert comparison.json()["data"]["differenceCount"] == 1
    assert comparison.json()["data"]["differences"][0]["changeType"] == "changed"
    assert comparisonReport.json()["data"]["format"] == "json"
    assert comparisonReport.json()["data"]["changeFilter"] == "changed"
    assert comparisonReport.json()["data"]["reportPath"].endswith(".json")
    assert comparisonReports.json()["data"]["reports"][0]["format"] == "json"
    assert comparisonReports.json()["data"]["reports"][0]["changeFilter"] == "changed"
    assert comparisonPreview.json()["data"]["rows"][0]["jobId"] == "job-1"
    assert comparisonPreview.json()["data"]["totalRows"] == 1
    assert comparisonPin.json()["data"]["pinned"] is True
    assert comparisonPin.json()["data"]["pinnedCount"] == 1
    assert cleaned.json()["data"]["jobs"][0]["fileName"] == "kept-3.mp4"
