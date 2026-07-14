import csv
import io
import json
import logging
import shutil
import subprocess
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

from app.project.project_model import Project
from app.render.errors import RenderError
from app.render.models import (
    RenderDiagnostics,
    RenderExportSettings,
    RenderJobQueueSnapshot,
    RenderJobSnapshot,
    RenderOutputPreview,
    RenderPlan,
    RenderResult,
    RenderReview,
)
from app.repositories.file_render_job_repository import FileRenderJobRepository
from app.services.render_service import RenderService

logger = logging.getLogger(__name__)
ACTIVE_STATUSES = {"queued", "preparing", "running", "cancelling"}
RESUMABLE_STATUSES = {"interrupted", "failed", "cancelled"}
REPORT_REVIEW_FILTERS = {"all", "accepted", "rejected", "not_reviewed"}
REPORT_JOB_STATUS_FILTERS = {
    "all",
    "queued",
    "preparing",
    "running",
    "cancelling",
    "completed",
    "cancelled",
    "failed",
    "interrupted",
}
DEFAULT_HISTORY_LIMIT = 100
STDERR_TAIL_LIMIT = 4_000
REPORT_FIELDS = (
    "jobId",
    "fileName",
    "status",
    "reviewStatus",
    "reviewNote",
    "reviewedAt",
    "outputPath",
    "sizeBytes",
    "durationMilliseconds",
    "progressPercent",
    "profileId",
    "resolution",
    "frameRate",
    "createdAt",
    "updatedAt",
    "errorCode",
    "errorMessage",
)
IMPORT_COMPARISON_CHANGE_FILTERS = {"all", "changed", "added", "removed"}
IMPORT_COMPARISON_FIELDS = (
    "jobId",
    "changeType",
    "baseStatus",
    "baseDecision",
    "baseReason",
    "compareStatus",
    "compareDecision",
    "compareReason",
)


@dataclass
class RenderJobState:
    jobId: str
    projectId: str
    fileName: str
    projectPath: Path
    durationMilliseconds: int
    exportSettings: RenderExportSettings
    outputNameTemplate: str | None = None
    status: str = "queued"
    progressPercent: float = 0.0
    processedMilliseconds: int = 0
    outputPath: Path | None = None
    sizeBytes: int | None = None
    errorCode: str | None = None
    errorMessage: str | None = None
    createdAt: str = ""
    updatedAt: str = ""
    diagnostics: RenderDiagnostics | None = None
    preview: RenderOutputPreview | None = None
    review: RenderReview | None = None
    attemptStartedAt: str | None = None
    attemptStartedMonotonic: float | None = None
    plan: RenderPlan | None = None
    process: subprocess.Popen[str] | None = None
    cancelRequested: bool = False

    def snapshot(self) -> RenderJobSnapshot:
        return RenderJobSnapshot(
            self.jobId,
            self.projectId,
            self.fileName,
            self.status,
            self.progressPercent,
            self.processedMilliseconds,
            self.durationMilliseconds,
            self.outputPath,
            self.sizeBytes,
            self.errorCode,
            self.errorMessage,
            self.createdAt,
            self.updatedAt,
            self.exportSettings,
            self.outputNameTemplate,
            self.diagnostics,
            self.preview,
            self.review,
        )


class RenderJobService:
    def __init__(
        self,
        renderService: RenderService,
        repository: FileRenderJobRepository | None = None,
    ) -> None:
        self.renderService = renderService
        self.repository = repository or FileRenderJobRepository()
        self.lock = threading.RLock()
        self.workerCondition = threading.Condition(self.lock)
        self.jobs: dict[str, RenderJobState] = {}
        self.loadedProjectPath: Path | None = None
        self.workerStarted = False
        self.workerBusy = False

    def startRender(
        self,
        fileName: str | None = "rendered.mp4",
        exportSettings: RenderExportSettings | None = None,
        outputNameTemplate: str | None = None,
    ) -> RenderJobSnapshot:
        draft = self.renderService.createRenderDraft(
            fileName, exportSettings, outputNameTemplate
        )
        resolvedFileName = draft.outputPath.name
        now = self._now()
        with self.workerCondition:
            self._loadProjectQueue(draft.projectPath)
            job = RenderJobState(
                uuid4().hex,
                draft.projectId,
                resolvedFileName,
                draft.projectPath,
                draft.durationMilliseconds,
                draft.exportSettings,
                outputNameTemplate,
                createdAt=now,
                updatedAt=now,
            )
            self.jobs[job.jobId] = job
            self._persistLoadedProject()
            self._ensureWorkerLocked()
            self.workerCondition.notify_all()
            return job.snapshot()

    def listJobs(self) -> RenderJobQueueSnapshot:
        project = self._requireProject()
        with self.lock:
            self._loadProjectQueue(project.path)
            return RenderJobQueueSnapshot(self._sortedSnapshots())

    def getJob(self, jobId: str) -> RenderJobSnapshot:
        project = self._requireProject()
        with self.lock:
            self._loadProjectQueue(project.path)
            return self._requireJob(jobId).snapshot()

    def cancelJob(self, jobId: str) -> RenderJobSnapshot:
        project = self._requireProject()
        with self.workerCondition:
            self._loadProjectQueue(project.path)
            job = self._requireJob(jobId)
            if job.status in {"queued", "preparing"}:
                self._markCancelledLocked(job)
                self._persistLoadedProject()
                return job.snapshot()
            if job.status != "running":
                return job.snapshot()
            job.cancelRequested = True
            job.status = "cancelling"
            job.errorCode = None
            job.errorMessage = None
            job.updatedAt = self._now()
            process = job.process
            self._persistLoadedProject()
        if process and process.poll() is None:
            process.terminate()
        return self.getJob(jobId)

    def resumeJob(self, jobId: str) -> RenderJobSnapshot:
        project = self._requireProject()
        with self.workerCondition:
            self._loadProjectQueue(project.path)
            job = self._requireJob(jobId)
            if job.status not in RESUMABLE_STATUSES:
                raise RenderError(
                    "RENDER_JOB_NOT_RESUMABLE", "Render job cannot be resumed."
                )
            draft = self.renderService.createRenderDraft(
                job.fileName, job.exportSettings, None
            )
            job.status = "queued"
            job.progressPercent = 0.0
            job.processedMilliseconds = 0
            job.durationMilliseconds = draft.durationMilliseconds
            job.outputPath = None
            job.sizeBytes = None
            job.errorCode = None
            job.errorMessage = None
            job.preview = None
            job.review = None
            job.cancelRequested = False
            job.plan = None
            job.updatedAt = self._now()
            self._persistLoadedProject()
            self._ensureWorkerLocked()
            self.workerCondition.notify_all()
            return job.snapshot()

    def retryJob(self, jobId: str) -> RenderJobSnapshot:
        return self.resumeJob(jobId)

    def reviewJob(
        self, jobId: str, status: str, note: str | None = None
    ) -> RenderJobSnapshot:
        project = self._requireProject()
        cleanedNote = note.strip() if isinstance(note, str) else None
        with self.lock:
            self._loadProjectQueue(project.path)
            job = self._requireJob(jobId)
            if job.status != "completed" or job.outputPath is None:
                raise RenderError(
                    "RENDER_JOB_NOT_REVIEWABLE",
                    "Only completed render jobs can be reviewed.",
                )
            job.review = RenderReview(status, cleanedNote or None, self._now())
            job.updatedAt = self._now()
            self._persistLoadedProject()
            return job.snapshot()

    def clearReviewJob(self, jobId: str) -> RenderJobSnapshot:
        project = self._requireProject()
        with self.lock:
            self._loadProjectQueue(project.path)
            job = self._requireJob(jobId)
            if job.status != "completed" or job.outputPath is None:
                raise RenderError(
                    "RENDER_JOB_NOT_REVIEWABLE",
                    "Only completed render jobs can have review cleared.",
                )
            job.review = None
            job.updatedAt = self._now()
            self._persistLoadedProject()
            return job.snapshot()

    def cleanupHistory(
        self, keepCount: int = DEFAULT_HISTORY_LIMIT
    ) -> RenderJobQueueSnapshot:
        project = self._requireProject()
        with self.lock:
            self._loadProjectQueue(project.path)
            self._capHistory(keepCount)
            self._persistLoadedProject()
            return RenderJobQueueSnapshot(self._sortedSnapshots())

    def exportQueueReport(
        self,
        reportFormat: str = "csv",
        reviewStatus: str = "all",
        jobStatus: str = "all",
        dateFrom: str | None = None,
        dateTo: str | None = None,
    ) -> dict[str, Any]:
        if reportFormat not in {"csv", "json"}:
            raise RenderError(
                "INVALID_RENDER_REPORT_FORMAT",
                "Render queue report format must be csv or json.",
            )
        self._validateReportFilters(reviewStatus, jobStatus)
        fromDate = self._parseReportDateBound(dateFrom, False)
        toDate = self._parseReportDateBound(dateTo, True)
        if fromDate and toDate and fromDate > toDate:
            raise RenderError(
                "INVALID_RENDER_REPORT_FILTER",
                "Render queue report date range is invalid.",
            )
        project = self._requireProject()
        generatedAt = self._now()
        with self.lock:
            self._loadProjectQueue(project.path)
            snapshots = self._sortedSnapshots()
            rows = [self._reportRow(snapshot) for snapshot in snapshots]
            rows = self._filterReportRows(
                rows, reviewStatus, jobStatus, fromDate, toDate
            )
        filters = {
            "reviewStatus": reviewStatus,
            "jobStatus": jobStatus,
            "dateFrom": dateFrom,
            "dateTo": dateTo,
        }
        reportPath = self._writeReport(
            project.path, rows, reportFormat, generatedAt, filters
        )
        return {
            "format": reportFormat,
            "reportPath": str(reportPath),
            "jobCount": len(rows),
            "generatedAt": generatedAt,
            "summary": self._reportSummary(rows),
            "filters": filters,
        }

    def exportQueueHandoffBundle(
        self,
        reviewStatus: str = "all",
        jobStatus: str = "all",
        dateFrom: str | None = None,
        dateTo: str | None = None,
    ) -> dict[str, Any]:
        self._validateReportFilters(reviewStatus, jobStatus)
        fromDate = self._parseReportDateBound(dateFrom, False)
        toDate = self._parseReportDateBound(dateTo, True)
        if fromDate and toDate and fromDate > toDate:
            raise RenderError(
                "INVALID_RENDER_REPORT_FILTER",
                "Render queue report date range is invalid.",
            )
        project = self._requireProject()
        generatedAt = self._now()
        with self.lock:
            self._loadProjectQueue(project.path)
            snapshots = self._sortedSnapshots()
            rows = [self._reportRow(snapshot) for snapshot in snapshots]
            rows = self._filterReportRows(
                rows, reviewStatus, jobStatus, fromDate, toDate
            )
            snapshotsById = {snapshot.jobId: snapshot for snapshot in snapshots}
        filters = {
            "reviewStatus": reviewStatus,
            "jobStatus": jobStatus,
            "dateFrom": dateFrom,
            "dateTo": dateTo,
        }
        return self._writeHandoffBundle(
            project.path, rows, snapshotsById, generatedAt, filters
        )

    def importBundleReviews(self, manifestPath: str) -> dict[str, Any]:
        project = self._requireProject()
        resolvedPath = self._resolveBundleManifestPath(project.path, manifestPath)
        importedAt = self._now()
        try:
            manifest = json.loads(resolvedPath.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            logger.warning("Invalid render bundle manifest JSON: %s", resolvedPath)
            raise RenderError(
                "INVALID_RENDER_BUNDLE_MANIFEST",
                "Render bundle manifest is not valid JSON.",
            ) from error
        checklist = manifest.get("reviewerChecklist")
        if not isinstance(checklist, list):
            raise RenderError(
                "INVALID_RENDER_BUNDLE_MANIFEST",
                "Render bundle manifest reviewer checklist is missing.",
            )
        details: list[dict[str, str | None]] = []
        applied = 0
        accepted = 0
        rejected = 0
        with self.lock:
            self._loadProjectQueue(project.path)
            for item in checklist:
                detail = self._applyBundleReviewItem(item)
                details.append(detail)
                if detail["status"] != "applied":
                    continue
                applied += 1
                if detail["decision"] == "accepted":
                    accepted += 1
                if detail["decision"] == "rejected":
                    rejected += 1
            if applied:
                self._persistLoadedProject()
        reportPath = self._writeBundleImportReport(
            project.path,
            resolvedPath,
            manifest,
            importedAt,
            applied,
            len(details) - applied,
            accepted,
            rejected,
            details,
        )
        return {
            "manifestPath": str(resolvedPath),
            "reportPath": str(reportPath),
            "applied": applied,
            "skipped": len(details) - applied,
            "accepted": accepted,
            "rejected": rejected,
            "details": details,
        }

    def listBundleImportReports(self) -> dict[str, Any]:
        project = self._requireProject()
        importsPath = project.path / "render" / "reports" / "imports"
        if not importsPath.is_dir():
            return {"reports": []}
        reports: list[dict[str, Any]] = []
        for reportPath in importsPath.glob("render-bundle-import-*.json"):
            try:
                report = json.loads(reportPath.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.warning("Invalid render bundle import report: %s", reportPath)
                continue
            if not isinstance(report, dict):
                continue
            reports.append(self._bundleImportReportSummary(reportPath, report))
        reports.sort(key=lambda item: str(item["importedAt"]), reverse=True)
        return {"reports": reports}

    def compareBundleImportReports(
        self, baseReportPath: str, compareReportPath: str
    ) -> dict[str, Any]:
        project = self._requireProject()
        basePath = self._resolveBundleImportReportPath(
            project.path, baseReportPath
        )
        comparePath = self._resolveBundleImportReportPath(
            project.path, compareReportPath
        )
        if basePath == comparePath:
            raise RenderError(
                "INVALID_RENDER_IMPORT_REPORT",
                "Choose two different render import reports to compare.",
            )
        baseReport = self._loadBundleImportReport(basePath)
        compareReport = self._loadBundleImportReport(comparePath)
        baseDetails = self._bundleImportDetailsByJobId(baseReport.get("details"))
        compareDetails = self._bundleImportDetailsByJobId(
            compareReport.get("details")
        )
        differences: list[dict[str, Any]] = []
        for jobId in sorted(set(baseDetails) | set(compareDetails)):
            baseDetail = baseDetails.get(jobId)
            compareDetail = compareDetails.get(jobId)
            if self._bundleImportDetailSignature(
                baseDetail
            ) == self._bundleImportDetailSignature(compareDetail):
                continue
            changeType = "changed"
            if baseDetail is None:
                changeType = "added"
            if compareDetail is None:
                changeType = "removed"
            differences.append(
                {
                    "jobId": jobId,
                    "changeType": changeType,
                    "base": baseDetail,
                    "compare": compareDetail,
                }
            )
        return {
            "baseReport": self._bundleImportReportSummary(basePath, baseReport),
            "compareReport": self._bundleImportReportSummary(
                comparePath, compareReport
            ),
            "differenceCount": len(differences),
            "differences": differences,
        }

    def exportBundleImportComparisonReport(
        self,
        baseReportPath: str,
        compareReportPath: str,
        reportFormat: str = "csv",
        changeFilter: str = "all",
    ) -> dict[str, Any]:
        if reportFormat not in {"csv", "json"}:
            raise RenderError(
                "INVALID_RENDER_IMPORT_COMPARISON_REPORT",
                "Render import comparison report format must be csv or json.",
            )
        if changeFilter not in IMPORT_COMPARISON_CHANGE_FILTERS:
            raise RenderError(
                "INVALID_RENDER_IMPORT_COMPARISON_REPORT",
                "Render import comparison change filter is not supported.",
            )
        project = self._requireProject()
        generatedAt = self._now()
        comparison = self.compareBundleImportReports(baseReportPath, compareReportPath)
        differences = [
            difference
            for difference in comparison["differences"]
            if changeFilter == "all" or difference["changeType"] == changeFilter
        ]
        reportPath = self._writeBundleImportComparisonReport(
            project.path,
            comparison,
            differences,
            reportFormat,
            changeFilter,
            generatedAt,
        )
        return {
            "format": reportFormat,
            "reportPath": str(reportPath),
            "generatedAt": generatedAt,
            "changeFilter": changeFilter,
            "differenceCount": len(differences),
            "baseReport": comparison["baseReport"],
            "compareReport": comparison["compareReport"],
        }

    def listBundleImportComparisonReports(self) -> dict[str, Any]:
        project = self._requireProject()
        reportsPath = project.path / "render" / "reports" / "import-comparisons"
        if not reportsPath.is_dir():
            return {"reports": []}
        pinnedReports = self._loadBundleImportComparisonPins(project.path)
        reports: list[dict[str, Any]] = []
        for reportPath in reportsPath.glob("render-import-comparison-*.*"):
            if not reportPath.is_file() or reportPath.suffix not in {".csv", ".json"}:
                continue
            try:
                reports.append(
                    self._bundleImportComparisonReportSummary(
                        reportPath, pinnedReports
                    )
                )
            except (OSError, json.JSONDecodeError, csv.Error):
                logger.warning(
                    "Invalid render import comparison report: %s", reportPath
                )
        reports.sort(
            key=lambda item: (
                bool(item["pinned"]),
                str(item["generatedAt"]),
                str(item["reportPath"]),
            ),
            reverse=True,
        )
        return {"reports": reports}

    def previewBundleImportComparisonReport(
        self, reportPath: str, maxRows: int = 25
    ) -> dict[str, Any]:
        project = self._requireProject()
        resolvedPath = self._resolveBundleImportComparisonReportPath(
            project.path, reportPath
        )
        rowLimit = max(1, min(maxRows, 100))
        pinnedReports = self._loadBundleImportComparisonPins(project.path)
        summary = self._bundleImportComparisonReportSummary(
            resolvedPath, pinnedReports
        )
        if resolvedPath.suffix == ".json":
            rows = self._previewBundleImportComparisonJson(resolvedPath)
        else:
            rows = self._previewBundleImportComparisonCsv(resolvedPath)
        return {
            "report": summary,
            "columns": list(IMPORT_COMPARISON_FIELDS),
            "rows": rows[:rowLimit],
            "totalRows": len(rows),
            "truncated": len(rows) > rowLimit,
        }

    def setBundleImportComparisonReportPinned(
        self, reportPath: str, pinned: bool
    ) -> dict[str, Any]:
        project = self._requireProject()
        resolvedPath = self._resolveBundleImportComparisonReportPath(
            project.path, reportPath
        )
        pinnedReports = self._loadBundleImportComparisonPins(project.path)
        if pinned:
            pinnedReports.add(resolvedPath.name)
        else:
            pinnedReports.discard(resolvedPath.name)
        self._writeBundleImportComparisonPins(project.path, pinnedReports)
        return {
            "reportPath": str(resolvedPath),
            "pinned": pinned,
            "pinnedCount": len(pinnedReports),
        }

    def _workerLoop(self) -> None:
        while True:
            with self.workerCondition:
                job = self._nextQueuedJobLocked()
                if job is None:
                    self.workerBusy = False
                    self.workerCondition.wait()
                    continue
                self.workerBusy = True
                try:
                    self._markPreparingLocked(job)
                except RenderError as error:
                    self._markFailedLocked(job, error.code, error.message)
                    self._persistLoadedProject()
                    continue
                except Exception:
                    logger.exception("Unexpected render job preparation failure.")
                    self._markFailedLocked(
                        job,
                        "RENDER_FAILED",
                        "The render job could not be prepared.",
                    )
                    self._persistLoadedProject()
                    continue
                fileName = job.fileName
                exportSettings = job.exportSettings
            try:
                plan = self.renderService.createRenderPlan(
                    fileName, exportSettings, None
                )
            except RenderError as error:
                with self.workerCondition:
                    self._markFailedLocked(job, error.code, error.message)
                    self._persistLoadedProject()
                continue
            except Exception:
                logger.exception("Unexpected render job preparation failure.")
                with self.workerCondition:
                    self._markFailedLocked(
                        job,
                        "RENDER_FAILED",
                        "The render job could not be prepared.",
                    )
                    self._persistLoadedProject()
                continue
            with self.workerCondition:
                if not self._startPreparedJobLocked(job, plan):
                    continue
            self._runJob(job.jobId)

    def _markPreparingLocked(self, job: RenderJobState) -> None:
        job.status = "preparing"
        job.progressPercent = 1.0
        job.processedMilliseconds = 0
        job.errorCode = None
        job.errorMessage = None
        job.diagnostics = self._diagnostics(job, "preparing", None, None)
        job.updatedAt = self._now()
        self._persistLoadedProject()

    def _startPreparedJobLocked(
        self, job: RenderJobState, plan: RenderPlan
    ) -> bool:
        if job.status == "cancelled":
            plan.temporaryPath.unlink(missing_ok=True)
            self._cleanupTemporaryPlanFiles(plan)
            return False
        job.plan = plan
        job.durationMilliseconds = plan.durationMilliseconds
        job.attemptStartedAt = self._now()
        job.attemptStartedMonotonic = monotonic()
        job.status = "running"
        job.progressPercent = 0.0
        job.processedMilliseconds = 0
        job.errorCode = None
        job.errorMessage = None
        job.diagnostics = self._diagnostics(job, "running", None, None)
        job.updatedAt = self._now()
        self._persistLoadedProject()
        return True

    def _runJob(self, jobId: str) -> None:
        with self.lock:
            job = self._requireJob(jobId)
            plan = job.plan
        if plan is None:
            self._markFailed(jobId, "RENDER_FAILED", "Render plan is unavailable.")
            return
        try:
            returnCode, standardError = self._runProcess(job)
            with self.lock:
                if job.cancelRequested:
                    self._markCancelledLocked(job, standardError, returnCode)
                    self._persistLoadedProject()
                    return
            try:
                result = self.renderService.completeRenderPlan(
                    plan, returnCode, standardError
                )
            except RenderError as error:
                self._markFailed(
                    jobId, error.code, error.message, standardError, returnCode
                )
                return
            self._markCompleted(jobId, result)
        except RenderError as error:
            self._markFailed(jobId, error.code, error.message)
        except Exception:
            logger.exception("Unexpected render job failure.")
            self._markFailed(
                jobId, "RENDER_FAILED", "The render job failed unexpectedly."
            )

    def _runProcess(self, job: RenderJobState) -> tuple[int, str]:
        assert job.plan is not None
        try:
            process = subprocess.Popen(
                job.plan.command.arguments,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as error:
            raise RenderError(
                "RENDER_PROCESS_START_FAILED", "FFmpeg could not be started."
            ) from error
        with self.lock:
            job.process = process
            self._persistLoadedProject()
        assert process.stdout is not None
        for line in process.stdout:
            self._handleProgressLine(job.jobId, line.strip())
            with self.lock:
                if job.cancelRequested and process.poll() is None:
                    process.terminate()
        standardError = process.stderr.read() if process.stderr else ""
        returnCode = process.wait()
        with self.lock:
            job.process = None
            self._persistLoadedProject()
        return returnCode, standardError

    def _handleProgressLine(self, jobId: str, line: str) -> None:
        if not line.startswith("out_time_ms="):
            return
        try:
            processedMilliseconds = max(
                0, int(int(line.removeprefix("out_time_ms=")) / 1_000)
            )
        except ValueError:
            return
        with self.lock:
            job = self.jobs.get(jobId)
            if not job:
                return
            duration = max(1, job.durationMilliseconds)
            job.processedMilliseconds = min(processedMilliseconds, duration)
            job.progressPercent = min(
                99.0, round(job.processedMilliseconds / duration * 100, 2)
            )
            job.updatedAt = self._now()
            self._persistLoadedProject()

    def _markCompleted(self, jobId: str, result: RenderResult) -> None:
        with self.lock:
            job = self._requireJob(jobId)
            job.status = "completed"
            job.progressPercent = 100.0
            job.processedMilliseconds = job.durationMilliseconds
            job.outputPath = result.outputPath
            job.sizeBytes = result.sizeBytes
            job.process = None
            job.preview = self.renderService.createOutputPreview(
                result,
                job.exportSettings,
                job.projectPath / "render" / "previews" / f"{job.jobId}.jpg",
                self._now(),
            )
            job.diagnostics = self._diagnostics(job, "completed", 0, None)
            job.plan = None
            job.updatedAt = self._now()
            self._persistLoadedProject()

    def _markCancelledLocked(
        self,
        job: RenderJobState,
        standardError: str | None = None,
        returnCode: int | None = None,
    ) -> None:
        job.status = "cancelled"
        job.errorCode = "RENDER_CANCELLED"
        job.errorMessage = "Render job was cancelled."
        job.process = None
        job.cancelRequested = False
        job.diagnostics = self._diagnostics(
            job, "cancelled", returnCode, standardError
        )
        job.updatedAt = self._now()
        if job.plan is not None:
            job.plan.temporaryPath.unlink(missing_ok=True)
            self._cleanupTemporaryPlanFiles(job.plan)
        job.plan = None

    def _markFailed(
        self,
        jobId: str,
        code: str,
        message: str,
        standardError: str | None = None,
        returnCode: int | None = None,
    ) -> None:
        with self.lock:
            job = self._requireJob(jobId)
            self._markFailedLocked(job, code, message, standardError, returnCode)
            self._persistLoadedProject()

    def _markFailedLocked(
        self,
        job: RenderJobState,
        code: str,
        message: str,
        standardError: str | None = None,
        returnCode: int | None = None,
    ) -> None:
        job.status = "failed"
        job.errorCode = code
        job.errorMessage = message
        job.process = None
        job.diagnostics = self._diagnostics(job, "failed", returnCode, standardError)
        job.updatedAt = self._now()
        if job.plan is not None:
            job.plan.temporaryPath.unlink(missing_ok=True)
            self._cleanupTemporaryPlanFiles(job.plan)
        job.plan = None

    def _loadProjectQueue(self, projectPath: Path) -> None:
        if self.loadedProjectPath == projectPath:
            return
        snapshots = self.repository.loadJobs(projectPath)
        self.jobs = {
            snapshot.jobId: self._stateFromSnapshot(projectPath, snapshot)
            for snapshot in snapshots
        }
        changed = False
        for job in self.jobs.values():
            if job.status in {"preparing", "running", "cancelling"}:
                job.status = "interrupted"
                job.errorCode = "RENDER_INTERRUPTED"
                job.errorMessage = "Render job was interrupted by backend restart."
                job.diagnostics = self._diagnostics(
                    job,
                    "interrupted",
                    None,
                    "Render job was interrupted by backend restart.",
                )
                job.updatedAt = self._now()
                changed = True
        self.loadedProjectPath = projectPath
        if changed:
            self._persistLoadedProject()
        if any(job.status == "queued" for job in self.jobs.values()):
            with self.workerCondition:
                self._ensureWorkerLocked()
                self.workerCondition.notify_all()

    def _stateFromSnapshot(
        self, projectPath: Path, snapshot: RenderJobSnapshot
    ) -> RenderJobState:
        timestamp = self._now()
        return RenderJobState(
            snapshot.jobId,
            snapshot.projectId,
            snapshot.fileName,
            projectPath,
            snapshot.durationMilliseconds,
            snapshot.exportSettings or RenderExportSettings(),
            snapshot.outputNameTemplate,
            snapshot.status,
            snapshot.progressPercent,
            snapshot.processedMilliseconds,
            snapshot.outputPath,
            snapshot.sizeBytes,
            snapshot.errorCode,
            snapshot.errorMessage,
            snapshot.createdAt or timestamp,
            snapshot.updatedAt or timestamp,
            snapshot.diagnostics,
            snapshot.preview,
            snapshot.review,
        )

    def _diagnostics(
        self,
        job: RenderJobState,
        status: str,
        returnCode: int | None,
        standardError: str | None,
    ) -> RenderDiagnostics:
        finishedAt = (
            self._now()
            if status in {"completed", "failed", "cancelled", "interrupted"}
            else None
        )
        metrics: dict[str, Any] = {
            "status": status,
            "startedAt": job.attemptStartedAt,
            "finishedAt": finishedAt,
            "elapsedMilliseconds": self._elapsedMilliseconds(job),
            "returnCode": returnCode,
            "processedMilliseconds": job.processedMilliseconds,
            "durationMilliseconds": job.durationMilliseconds,
            "progressPercent": job.progressPercent,
            "outputSizeBytes": job.sizeBytes,
        }
        if job.errorCode:
            metrics["errorCode"] = job.errorCode
        return RenderDiagnostics(
            self._commandSummary(job),
            job.exportSettings.toDictionary(),
            metrics,
            self._stderrTail(standardError),
        )

    def _commandSummary(self, job: RenderJobState) -> dict[str, Any]:
        if job.plan is None:
            return {"commandAvailable": False, "outputFileName": job.fileName}
        arguments = job.plan.command.arguments
        filterGraph = self._argumentAfter(arguments, "-filter_complex") or ""
        return {
            "commandAvailable": True,
            "executable": Path(arguments[0]).name if arguments else "",
            "argumentCount": len(arguments),
            "inputCount": sum(1 for argument in arguments if argument == "-i"),
            "filterGraphLength": len(filterGraph),
            "filterCount": self._filterCount(filterGraph),
            "visualFilterCount": filterGraph.count("setpts=PTS-STARTPTS"),
            "overlayFilterCount": filterGraph.count("overlay="),
            "drawtextFilterCount": self._drawtextFilterCount(filterGraph),
            "subtitleFileFilterCount": filterGraph.count("subtitles="),
            "subtitleOverlayFilterCount": filterGraph.count(
                "][subtitleOverlay]overlay="
            ),
            "concatFilterCount": filterGraph.count("concat="),
            "splitFilterCount": filterGraph.count("split="),
            "trimFilterCount": filterGraph.count("trim=duration="),
            "usesProgressPipe": "-progress" in arguments,
            "hasAudio": "-an" not in arguments,
            "videoCodec": self._argumentAfter(arguments, "-c:v"),
            "audioCodec": self._argumentAfter(arguments, "-c:a"),
            "encoderPreset": self._argumentAfter(arguments, "-preset"),
            "crf": self._argumentAfter(arguments, "-crf"),
            "frameRate": self._argumentAfter(arguments, "-r"),
            "outputFileName": Path(arguments[-1]).name if arguments else job.fileName,
        }

    def _filterCount(self, filterGraph: str) -> int:
        if not filterGraph:
            return 0
        return len([segment for segment in filterGraph.split(";") if segment])

    def _drawtextFilterCount(self, filterGraph: str) -> int:
        return filterGraph.count("drawtext=") + filterGraph.count("drawtext@")

    def _cleanupTemporaryPlanFiles(self, plan: RenderPlan) -> None:
        for path in plan.temporaryFiles:
            path.unlink(missing_ok=True)

    def _argumentAfter(self, arguments: tuple[str, ...], flag: str) -> str | None:
        try:
            index = arguments.index(flag)
        except ValueError:
            return None
        nextIndex = index + 1
        return arguments[nextIndex] if nextIndex < len(arguments) else None

    def _stderrTail(self, standardError: str | None) -> str | None:
        if not standardError:
            return None
        return standardError[-STDERR_TAIL_LIMIT:]

    def _elapsedMilliseconds(self, job: RenderJobState) -> int | None:
        if job.attemptStartedMonotonic is None:
            return None
        return max(0, int((monotonic() - job.attemptStartedMonotonic) * 1_000))

    def _persistLoadedProject(self) -> None:
        if self.loadedProjectPath is None:
            return
        self._capHistory(DEFAULT_HISTORY_LIMIT)
        self.repository.saveJobs(self.loadedProjectPath, self._sortedSnapshots())

    def _writeReport(
        self,
        projectPath: Path,
        rows: list[dict[str, Any]],
        reportFormat: str,
        generatedAt: str,
        filters: dict[str, str | None],
    ) -> Path:
        reportsPath = projectPath / "render" / "reports"
        reportsPath.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        suffix = self._reportFileNameSuffix(filters)
        reportPath = reportsPath / (
            f"render-queue-report-{timestamp}{suffix}.{reportFormat}"
        )
        temporaryPath = reportPath.with_name(f".{reportPath.name}.tmp")
        if reportFormat == "csv":
            content = self._reportCsv(rows)
        else:
            content = json.dumps(
                {
                    "generatedAt": generatedAt,
                    "jobCount": len(rows),
                    "summary": self._reportSummary(rows),
                    "filters": filters,
                    "jobs": rows,
                },
                indent=2,
            )
        temporaryPath.write_text(content, encoding="utf-8", newline="")
        temporaryPath.replace(reportPath)
        return reportPath

    def _writeBundleImportComparisonReport(
        self,
        projectPath: Path,
        comparison: dict[str, Any],
        differences: list[dict[str, Any]],
        reportFormat: str,
        changeFilter: str,
        generatedAt: str,
    ) -> Path:
        reportsPath = projectPath / "render" / "reports" / "import-comparisons"
        reportsPath.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        suffix = self._fileNameToken(changeFilter)
        reportPath = reportsPath / (
            f"render-import-comparison-{timestamp}-{suffix}.{reportFormat}"
        )
        temporaryPath = reportPath.with_name(f".{reportPath.name}.tmp")
        rows = self._bundleImportComparisonRows(differences)
        if reportFormat == "csv":
            content = self._bundleImportComparisonCsv(rows)
        else:
            content = json.dumps(
                {
                    "schemaVersion": 1,
                    "generatedAt": generatedAt,
                    "changeFilter": changeFilter,
                    "differenceCount": len(differences),
                    "baseReport": comparison["baseReport"],
                    "compareReport": comparison["compareReport"],
                    "differences": differences,
                },
                indent=2,
            )
        temporaryPath.write_text(content, encoding="utf-8", newline="")
        temporaryPath.replace(reportPath)
        return reportPath

    def _bundleImportComparisonReportSummary(
        self, reportPath: Path, pinnedReports: set[str] | None = None
    ) -> dict[str, Any]:
        reportFormat = reportPath.suffix.lstrip(".")
        generatedAt = self._fileModifiedAt(reportPath)
        changeFilter = self._comparisonFilterFromFileName(reportPath)
        pinnedReports = pinnedReports or set()
        differenceCount = 0
        baseReportPath: str | None = None
        compareReportPath: str | None = None
        if reportFormat == "json":
            report = json.loads(reportPath.read_text(encoding="utf-8"))
            if isinstance(report, dict):
                generatedAt = (
                    self._optionalString(report.get("generatedAt")) or generatedAt
                )
                changeFilter = self._optionalString(
                    report.get("changeFilter")
                ) or changeFilter
                differenceCount = self._reportInt(report.get("differenceCount"))
                baseReportPath = self._comparisonReportPath(report.get("baseReport"))
                compareReportPath = self._comparisonReportPath(
                    report.get("compareReport")
                )
        else:
            with reportPath.open("r", encoding="utf-8", newline="") as handle:
                differenceCount = sum(1 for _ in csv.DictReader(handle))
        if changeFilter not in IMPORT_COMPARISON_CHANGE_FILTERS:
            changeFilter = "all"
        return {
            "reportPath": str(reportPath),
            "format": reportFormat,
            "generatedAt": generatedAt,
            "changeFilter": changeFilter,
            "differenceCount": differenceCount,
            "baseReportPath": baseReportPath,
            "compareReportPath": compareReportPath,
            "pinned": reportPath.name in pinnedReports,
        }

    def _loadBundleImportComparisonPins(self, projectPath: Path) -> set[str]:
        pinsPath = self._bundleImportComparisonPinsPath(projectPath)
        if not pinsPath.is_file():
            return set()
        try:
            data = json.loads(pinsPath.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Invalid render import comparison pins: %s", pinsPath)
            return set()
        pinnedReports = data.get("pinnedReports") if isinstance(data, dict) else None
        if not isinstance(pinnedReports, list):
            return set()
        return {
            item
            for item in pinnedReports
            if isinstance(item, str) and Path(item).name == item
        }

    def _writeBundleImportComparisonPins(
        self, projectPath: Path, pinnedReports: set[str]
    ) -> None:
        pinsPath = self._bundleImportComparisonPinsPath(projectPath)
        pinsPath.parent.mkdir(parents=True, exist_ok=True)
        existingReports = {
            path.name
            for path in pinsPath.parent.glob("render-import-comparison-*.*")
            if path.is_file() and path.suffix in {".csv", ".json"}
        }
        retainedPins = sorted(pinnedReports & existingReports)
        temporaryPath = pinsPath.with_name(f".{pinsPath.name}.tmp")
        temporaryPath.write_text(
            json.dumps(
                {"schemaVersion": 1, "pinnedReports": retainedPins},
                indent=2,
            ),
            encoding="utf-8",
        )
        temporaryPath.replace(pinsPath)

    def _bundleImportComparisonPinsPath(self, projectPath: Path) -> Path:
        return (
            projectPath
            / "render"
            / "reports"
            / "import-comparisons"
            / "favorites.json"
        )

    def _previewBundleImportComparisonJson(
        self, reportPath: Path
    ) -> list[dict[str, str]]:
        report = json.loads(reportPath.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            return []
        differences = report.get("differences")
        if not isinstance(differences, list):
            return []
        normalized = [
            difference
            for difference in differences
            if isinstance(difference, dict)
        ]
        return self._bundleImportComparisonRows(normalized)

    def _previewBundleImportComparisonCsv(
        self, reportPath: Path
    ) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        with reportPath.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                rows.append(
                    {
                        field: self._optionalString(row.get(field)) or ""
                        for field in IMPORT_COMPARISON_FIELDS
                    }
                )
        return rows

    def _comparisonReportPath(self, summary: Any) -> str | None:
        if not isinstance(summary, dict):
            return None
        return self._optionalString(summary.get("reportPath"))

    def _comparisonFilterFromFileName(self, reportPath: Path) -> str:
        token = reportPath.stem.rsplit("-", 1)[-1]
        return token if token in IMPORT_COMPARISON_CHANGE_FILTERS else "all"

    def _fileModifiedAt(self, reportPath: Path) -> str:
        return datetime.fromtimestamp(reportPath.stat().st_mtime, UTC).isoformat()

    def _writeHandoffBundle(
        self,
        projectPath: Path,
        rows: list[dict[str, Any]],
        snapshotsById: dict[str, RenderJobSnapshot],
        generatedAt: str,
        filters: dict[str, str | None],
    ) -> dict[str, Any]:
        bundlesPath = projectPath / "render" / "reports" / "bundles"
        bundlesPath.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        bundlePath = bundlesPath / (
            f"render-handoff-bundle-{timestamp}-{uuid4().hex[:8]}"
            f"{self._reportFileNameSuffix(filters)}"
        )
        bundlePath.mkdir()
        csvPath = bundlePath / "render-queue-report.csv"
        jsonPath = bundlePath / "render-queue-report.json"
        manifestPath = bundlePath / "manifest.json"
        thumbnailsPath = bundlePath / "thumbnails"
        thumbnailsPath.mkdir()
        csvPath.write_text(self._reportCsv(rows), encoding="utf-8", newline="")
        jsonPath.write_text(
            json.dumps(
                {
                    "generatedAt": generatedAt,
                    "jobCount": len(rows),
                    "summary": self._reportSummary(rows),
                    "filters": filters,
                    "jobs": rows,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        thumbnailItems = self._copyBundleThumbnails(rows, snapshotsById, thumbnailsPath)
        manifest = {
            "schemaVersion": 1,
            "generatedAt": generatedAt,
            "bundlePath": str(bundlePath),
            "jobCount": len(rows),
            "thumbnailCount": len(thumbnailItems),
            "filters": filters,
            "summary": self._reportSummary(rows),
            "reports": {
                "csv": str(csvPath),
                "json": str(jsonPath),
            },
            "thumbnails": thumbnailItems,
            "reviewerChecklist": self._bundleReviewerChecklist(rows),
        }
        manifestPath.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        archivePath = Path(
            shutil.make_archive(
                str(bundlePath), "zip", bundlePath.parent, bundlePath.name
            )
        )
        return {
            "bundlePath": str(bundlePath),
            "archivePath": str(archivePath),
            "manifestPath": str(manifestPath),
            "csvReportPath": str(csvPath),
            "jsonReportPath": str(jsonPath),
            "jobCount": len(rows),
            "thumbnailCount": len(thumbnailItems),
            "generatedAt": generatedAt,
            "summary": self._reportSummary(rows),
            "filters": filters,
        }

    def _bundleReviewerChecklist(
        self, rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return [
            {
                "jobId": row["jobId"],
                "fileName": row["fileName"],
                "outputPath": row["outputPath"],
                "reviewStatus": row["reviewStatus"],
                "checks": {
                    "watchOutput": False,
                    "verifyAudio": False,
                    "verifySubtitles": False,
                    "verifyVisuals": False,
                    "confirmMetadata": False,
                },
                "decision": row["reviewStatus"],
                "notes": row["reviewNote"],
            }
            for row in rows
        ]

    def _copyBundleThumbnails(
        self,
        rows: list[dict[str, Any]],
        snapshotsById: dict[str, RenderJobSnapshot],
        thumbnailsPath: Path,
    ) -> list[dict[str, str]]:
        thumbnails: list[dict[str, str]] = []
        for row in rows:
            snapshot = snapshotsById.get(str(row["jobId"]))
            if (
                not snapshot
                or not snapshot.preview
                or not snapshot.preview.thumbnailPath
            ):
                continue
            sourcePath = snapshot.preview.thumbnailPath
            if not sourcePath.is_file():
                continue
            suffix = sourcePath.suffix if sourcePath.suffix else ".jpg"
            targetPath = thumbnailsPath / f"{snapshot.jobId}{suffix}"
            shutil.copy2(sourcePath, targetPath)
            thumbnails.append(
                {
                    "jobId": snapshot.jobId,
                    "fileName": snapshot.fileName,
                    "path": str(targetPath),
                }
            )
        return thumbnails

    def _resolveBundleManifestPath(self, projectPath: Path, manifestPath: str) -> Path:
        path = Path(manifestPath).expanduser()
        if not path.is_absolute():
            path = projectPath / path
        resolvedPath = path.resolve()
        bundlesRoot = (projectPath / "render" / "reports" / "bundles").resolve()
        try:
            resolvedPath.relative_to(bundlesRoot)
        except ValueError as error:
            raise RenderError(
                "INVALID_RENDER_BUNDLE_MANIFEST",
                "Render bundle manifest must be inside the active project "
                "bundle folder.",
            ) from error
        if resolvedPath.name != "manifest.json" or not resolvedPath.is_file():
            raise RenderError(
                "INVALID_RENDER_BUNDLE_MANIFEST",
                "Render bundle manifest was not found.",
            )
        return resolvedPath

    def _resolveBundleImportReportPath(
        self, projectPath: Path, reportPath: str
    ) -> Path:
        path = Path(reportPath).expanduser()
        if not path.is_absolute():
            path = projectPath / path
        resolvedPath = path.resolve()
        importsRoot = (projectPath / "render" / "reports" / "imports").resolve()
        try:
            resolvedPath.relative_to(importsRoot)
        except ValueError as error:
            raise RenderError(
                "INVALID_RENDER_IMPORT_REPORT",
                "Render import report must be inside the active project "
                "import audit folder.",
            ) from error
        if resolvedPath.suffix != ".json" or not resolvedPath.is_file():
            raise RenderError(
                "INVALID_RENDER_IMPORT_REPORT",
                "Render import report was not found.",
            )
        return resolvedPath

    def _resolveBundleImportComparisonReportPath(
        self, projectPath: Path, reportPath: str
    ) -> Path:
        path = Path(reportPath).expanduser()
        if not path.is_absolute():
            path = projectPath / path
        resolvedPath = path.resolve()
        reportsRoot = (
            projectPath / "render" / "reports" / "import-comparisons"
        ).resolve()
        try:
            resolvedPath.relative_to(reportsRoot)
        except ValueError as error:
            raise RenderError(
                "INVALID_RENDER_IMPORT_COMPARISON_REPORT",
                "Render import comparison report must be inside the active "
                "project comparison report folder.",
            ) from error
        if resolvedPath.suffix not in {".csv", ".json"} or not resolvedPath.is_file():
            raise RenderError(
                "INVALID_RENDER_IMPORT_COMPARISON_REPORT",
                "Render import comparison report was not found.",
            )
        return resolvedPath

    def _loadBundleImportReport(self, reportPath: Path) -> dict[str, Any]:
        try:
            report = json.loads(reportPath.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            logger.warning("Invalid render bundle import report: %s", reportPath)
            raise RenderError(
                "INVALID_RENDER_IMPORT_REPORT",
                "Render import report is not valid JSON.",
            ) from error
        if not isinstance(report, dict):
            raise RenderError(
                "INVALID_RENDER_IMPORT_REPORT",
                "Render import report is not an object.",
            )
        return report

    def _writeBundleImportReport(
        self,
        projectPath: Path,
        manifestPath: Path,
        manifest: dict[str, Any],
        importedAt: str,
        applied: int,
        skipped: int,
        accepted: int,
        rejected: int,
        details: list[dict[str, str | None]],
    ) -> Path:
        importsPath = projectPath / "render" / "reports" / "imports"
        importsPath.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        reportPath = importsPath / (
            f"render-bundle-import-{timestamp}-{uuid4().hex[:8]}.json"
        )
        temporaryPath = reportPath.with_name(f".{reportPath.name}.tmp")
        report = {
            "schemaVersion": 1,
            "importedAt": importedAt,
            "manifestPath": str(manifestPath),
            "sourceBundlePath": manifest.get("bundlePath"),
            "sourceGeneratedAt": manifest.get("generatedAt"),
            "applied": applied,
            "skipped": skipped,
            "accepted": accepted,
            "rejected": rejected,
            "details": details,
        }
        temporaryPath.write_text(json.dumps(report, indent=2), encoding="utf-8")
        temporaryPath.replace(reportPath)
        return reportPath

    def _bundleImportReportSummary(
        self, reportPath: Path, report: dict[str, Any]
    ) -> dict[str, Any]:
        details = report.get("details")
        detailCount = len(details) if isinstance(details, list) else 0
        return {
            "reportPath": str(reportPath),
            "importedAt": report.get("importedAt"),
            "manifestPath": report.get("manifestPath"),
            "sourceBundlePath": report.get("sourceBundlePath"),
            "sourceGeneratedAt": report.get("sourceGeneratedAt"),
            "applied": self._reportInt(report.get("applied")),
            "skipped": self._reportInt(report.get("skipped")),
            "accepted": self._reportInt(report.get("accepted")),
            "rejected": self._reportInt(report.get("rejected")),
            "detailCount": detailCount,
        }

    def _bundleImportDetailsByJobId(
        self, details: Any
    ) -> dict[str, dict[str, str | None]]:
        if not isinstance(details, list):
            return {}
        indexed: dict[str, dict[str, str | None]] = {}
        for index, item in enumerate(details):
            if not isinstance(item, dict):
                continue
            rawJobId = item.get("jobId")
            jobId = rawJobId.strip() if isinstance(rawJobId, str) else ""
            key = jobId or f"missing:{index + 1}"
            indexed[key] = {
                "jobId": jobId or None,
                "status": self._optionalString(item.get("status")),
                "decision": self._optionalString(item.get("decision")),
                "reason": self._optionalString(item.get("reason")),
            }
        return indexed

    def _bundleImportDetailSignature(
        self, detail: dict[str, str | None] | None
    ) -> tuple[str | None, str | None, str | None] | None:
        if detail is None:
            return None
        return (detail["status"], detail["decision"], detail["reason"])

    def _optionalString(self, value: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    def _reportInt(self, value: Any) -> int:
        return value if isinstance(value, int) else 0

    def _applyBundleReviewItem(self, item: Any) -> dict[str, str | None]:
        if not isinstance(item, dict):
            return {
                "jobId": None,
                "status": "skipped",
                "decision": None,
                "reason": "Checklist item is not an object.",
            }
        jobId = item.get("jobId")
        decision = item.get("decision")
        if not isinstance(jobId, str) or not jobId.strip():
            return {
                "jobId": None,
                "status": "skipped",
                "decision": str(decision) if decision is not None else None,
                "reason": "Checklist item has no jobId.",
            }
        cleanedJobId = jobId.strip()
        if decision not in {"accepted", "rejected"}:
            return {
                "jobId": cleanedJobId,
                "status": "skipped",
                "decision": str(decision) if decision is not None else None,
                "reason": "Decision is not accepted or rejected.",
            }
        job = self.jobs.get(cleanedJobId)
        if job is None:
            return {
                "jobId": cleanedJobId,
                "status": "skipped",
                "decision": decision,
                "reason": "Render job was not found in this project.",
            }
        if job.status != "completed" or job.outputPath is None:
            return {
                "jobId": cleanedJobId,
                "status": "skipped",
                "decision": decision,
                "reason": "Render job is not reviewable.",
            }
        note = item.get("notes")
        cleanedNote = note.strip() if isinstance(note, str) else None
        now = self._now()
        job.review = RenderReview(decision, cleanedNote or None, now)
        job.updatedAt = now
        return {
            "jobId": cleanedJobId,
            "status": "applied",
            "decision": decision,
            "reason": None,
        }

    def _reportFileNameSuffix(self, filters: dict[str, str | None]) -> str:
        segments: list[str] = []
        reviewStatus = filters.get("reviewStatus")
        jobStatus = filters.get("jobStatus")
        dateFrom = filters.get("dateFrom")
        dateTo = filters.get("dateTo")
        if reviewStatus and reviewStatus != "all":
            segments.extend(("review", self._fileNameToken(reviewStatus)))
        if jobStatus and jobStatus != "all":
            segments.extend(("status", self._fileNameToken(jobStatus)))
        if dateFrom or dateTo:
            segments.append(self._fileNameToken(dateFrom or "start"))
            segments.append("to")
            segments.append(self._fileNameToken(dateTo or "latest"))
        return f"-{'-'.join(segments)}" if segments else "-all-history"

    def _fileNameToken(self, value: str) -> str:
        token = "".join(
            character.lower()
            for character in value
            if character.isalnum() or character in {"-", "_"}
        )
        return token.replace("_", "-")[:48] or "all"

    def _reportCsv(self, rows: list[dict[str, Any]]) -> str:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=REPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        return buffer.getvalue()

    def _bundleImportComparisonCsv(self, rows: list[dict[str, Any]]) -> str:
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer, fieldnames=IMPORT_COMPARISON_FIELDS, extrasaction="ignore"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        return buffer.getvalue()

    def _bundleImportComparisonRows(
        self, differences: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for difference in differences:
            base = difference.get("base")
            compare = difference.get("compare")
            rows.append(
                {
                    "jobId": str(difference.get("jobId") or ""),
                    "changeType": str(difference.get("changeType") or ""),
                    "baseStatus": self._comparisonValue(base, "status"),
                    "baseDecision": self._comparisonValue(base, "decision"),
                    "baseReason": self._comparisonValue(base, "reason"),
                    "compareStatus": self._comparisonValue(compare, "status"),
                    "compareDecision": self._comparisonValue(compare, "decision"),
                    "compareReason": self._comparisonValue(compare, "reason"),
                }
            )
        return rows

    def _comparisonValue(self, detail: Any, key: str) -> str:
        if not isinstance(detail, dict):
            return ""
        value = detail.get(key)
        return "" if value is None else str(value)

    def _reportRow(self, snapshot: RenderJobSnapshot) -> dict[str, Any]:
        settings = snapshot.exportSettings
        review = snapshot.review
        return {
            "jobId": snapshot.jobId,
            "fileName": snapshot.fileName,
            "status": snapshot.status,
            "reviewStatus": review.status if review else "not_reviewed",
            "reviewNote": review.note if review else "",
            "reviewedAt": review.reviewedAt if review else "",
            "outputPath": str(snapshot.outputPath) if snapshot.outputPath else "",
            "sizeBytes": snapshot.sizeBytes if snapshot.sizeBytes is not None else "",
            "durationMilliseconds": snapshot.durationMilliseconds,
            "progressPercent": snapshot.progressPercent,
            "profileId": settings.profileId if settings else "",
            "resolution": f"{settings.width}x{settings.height}" if settings else "",
            "frameRate": settings.frameRate if settings else "",
            "createdAt": snapshot.createdAt or "",
            "updatedAt": snapshot.updatedAt or "",
            "errorCode": snapshot.errorCode or "",
            "errorMessage": snapshot.errorMessage or "",
        }

    def _reportSummary(self, rows: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "total": len(rows),
            "accepted": sum(1 for row in rows if row["reviewStatus"] == "accepted"),
            "rejected": sum(1 for row in rows if row["reviewStatus"] == "rejected"),
            "notReviewed": sum(
                1 for row in rows if row["reviewStatus"] == "not_reviewed"
            ),
            "completed": sum(1 for row in rows if row["status"] == "completed"),
            "failed": sum(1 for row in rows if row["status"] == "failed"),
        }

    def _validateReportFilters(self, reviewStatus: str, jobStatus: str) -> None:
        if reviewStatus not in REPORT_REVIEW_FILTERS:
            raise RenderError(
                "INVALID_RENDER_REPORT_FILTER",
                "Render queue report review filter is not supported.",
            )
        if jobStatus not in REPORT_JOB_STATUS_FILTERS:
            raise RenderError(
                "INVALID_RENDER_REPORT_FILTER",
                "Render queue report status filter is not supported.",
            )

    def _filterReportRows(
        self,
        rows: list[dict[str, Any]],
        reviewStatus: str,
        jobStatus: str,
        dateFrom: datetime | None,
        dateTo: datetime | None,
    ) -> list[dict[str, Any]]:
        return [
            row
            for row in rows
            if (reviewStatus == "all" or row["reviewStatus"] == reviewStatus)
            and (jobStatus == "all" or row["status"] == jobStatus)
            and self._matchesReportDateRange(row, dateFrom, dateTo)
        ]

    def _matchesReportDateRange(
        self,
        row: dict[str, Any],
        dateFrom: datetime | None,
        dateTo: datetime | None,
    ) -> bool:
        if dateFrom is None and dateTo is None:
            return True
        rowDate = self._parseReportTimestamp(row["updatedAt"] or row["createdAt"])
        if rowDate is None:
            return False
        if dateFrom and rowDate < dateFrom:
            return False
        return not (dateTo and rowDate >= dateTo)

    def _parseReportDateBound(
        self, value: str | None, exclusiveEnd: bool
    ) -> datetime | None:
        if value is None or value == "":
            return None
        try:
            if len(value) == 10:
                parsed = datetime.fromisoformat(value).replace(tzinfo=UTC)
                return parsed + timedelta(days=1) if exclusiveEnd else parsed
            parsedTimestamp = self._parseReportTimestamp(value)
        except ValueError as error:
            raise RenderError(
                "INVALID_RENDER_REPORT_FILTER",
                "Render queue report date filter is invalid.",
            ) from error
        if parsedTimestamp is None:
            raise RenderError(
                "INVALID_RENDER_REPORT_FILTER",
                "Render queue report date filter is invalid.",
            )
        return parsedTimestamp

    def _parseReportTimestamp(self, value: str) -> datetime | None:
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _capHistory(self, keepCount: int) -> None:
        keepCount = max(0, keepCount)
        active = [job for job in self.jobs.values() if job.status in ACTIVE_STATUSES]
        history = [
            job for job in self.jobs.values() if job.status not in ACTIVE_STATUSES
        ]
        retainedHistory = sorted(
            history, key=lambda item: item.updatedAt or item.createdAt
        )[-keepCount:]
        retained = {job.jobId: job for job in (*active, *retainedHistory)}
        self.jobs = retained

    def _sortedSnapshots(self) -> tuple[RenderJobSnapshot, ...]:
        return tuple(
            job.snapshot()
            for job in sorted(self.jobs.values(), key=lambda item: item.createdAt)
        )

    def _nextQueuedJobLocked(self) -> RenderJobState | None:
        queued = [job for job in self.jobs.values() if job.status == "queued"]
        if not queued:
            return None
        return sorted(queued, key=lambda item: item.createdAt)[0]

    def _ensureWorkerLocked(self) -> None:
        if self.workerStarted:
            return
        self.workerStarted = True
        threading.Thread(
            target=self._workerLoop,
            name="render-queue-worker",
            daemon=True,
        ).start()

    def _requireJob(self, jobId: str) -> RenderJobState:
        job = self.jobs.get(jobId)
        if job is None:
            raise RenderError("RENDER_JOB_NOT_FOUND", "Render job was not found.")
        return job

    def _requireProject(self) -> Project:
        project = self.renderService.projectService.getCurrentProject()
        if project is None:
            raise RenderError("NO_ACTIVE_PROJECT", "No project is currently open.")
        return project

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()
