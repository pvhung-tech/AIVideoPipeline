import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Copy,
  Download,
  ExternalLink,
  Film,
  FolderOpen,
  Play,
  Printer,
  RotateCcw,
  Square,
  Star,
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { WorkflowHandoff } from "../components/WorkflowHandoff";
import { WorkspaceGuide } from "../components/WorkspaceGuide";
import { openDesktopPath } from "../services/desktopClient";
import {
  RenderApiError,
  RenderBundleImportReportComparison,
  RenderBundleImportReportDetailSnapshot,
  RenderBundleImportReportDifference,
  RenderBundleImportReportSummary,
  RenderBundleImportComparisonReport,
  RenderBundleImportComparisonReportPreview,
  RenderBundleImportComparisonReportSummary,
  RenderBundleReviewImportDetail,
  RenderBundleReviewImportResult,
  RenderExportSettings,
  RenderJob,
  RenderPreflightGroup,
  RenderPreflightReport,
  RenderProfile,
  RenderProfileId,
  RenderQueueHandoffBundle,
  RenderQueueReportJobStatusFilter,
  RenderQueueReport,
  RenderQueueReportFormat,
  RenderQueueReportReviewFilter,
  RenderReviewStatus,
  StartRenderRequest,
  cancelRenderJob,
  checkRenderPreflight,
  clearRenderJobReview,
  compareRenderBundleImportReports,
  cleanupRenderJobs,
  exportRenderQueueHandoffBundle,
  exportRenderQueueReport,
  exportRenderBundleImportComparisonReport,
  getRenderJob,
  importRenderBundleReviews,
  listRenderBundleImportComparisonReports,
  listRenderBundleImportReports,
  listRenderProfiles,
  listRenderJobs,
  pinRenderBundleImportComparisonReport,
  previewRenderBundleImportComparisonReport,
  reviewRenderJob,
  retryRenderJob,
  resumeRenderJob,
  startRenderJob,
} from "../services/renderClient";

const DEFAULT_OUTPUT_TEMPLATE = "{project}-{datetime}.mp4";
const FAST_PREVIEW_LONG_TIMELINE_MILLISECONDS = 60_000;
type RenderReviewFilter = "all" | "accepted" | "rejected" | "not_reviewed";
type RenderImportDiagnosticsFilter = "all" | "applied" | "skipped";
type RenderImportComparisonFilter = "all" | "changed" | "added" | "removed";
type RenderImportComparisonFormatFilter = "all" | "csv" | "json";
type RenderQueueSort = "newest" | "oldest" | "status";
type RenderQueueSummary = {
  total: number;
  accepted: number;
  rejected: number;
  notReviewed: number;
  completed: number;
  failed: number;
  queued: number;
  preparing: number;
  running: number;
  cancelling: number;
  cancelled: number;
  interrupted: number;
};

const REVIEW_FILTER_OPTIONS: { value: RenderReviewFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "accepted", label: "Accepted" },
  { value: "rejected", label: "Rejected" },
  { value: "not_reviewed", label: "Not reviewed" },
];
const QUEUE_SORT_OPTIONS: { value: RenderQueueSort; label: string }[] = [
  { value: "newest", label: "Newest" },
  { value: "oldest", label: "Oldest" },
  { value: "status", label: "Status" },
];
const REPORT_STATUS_OPTIONS: {
  value: RenderQueueReportJobStatusFilter;
  label: string;
}[] = [
  { value: "all", label: "All statuses" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "queued", label: "Queued" },
  { value: "preparing", label: "Preparing" },
  { value: "running", label: "Running" },
  { value: "cancelled", label: "Cancelled" },
  { value: "interrupted", label: "Interrupted" },
  { value: "cancelling", label: "Cancelling" },
];
const QUEUE_PAGE_SIZES = [5, 10, 25];
const IMPORT_DIAGNOSTICS_FILTER_OPTIONS: {
  value: RenderImportDiagnosticsFilter;
  label: string;
}[] = [
  { value: "all", label: "All imports" },
  { value: "applied", label: "Applied" },
  { value: "skipped", label: "Skipped" },
];
const IMPORT_COMPARISON_FILTER_OPTIONS: {
  value: RenderImportComparisonFilter;
  label: string;
}[] = [
  { value: "all", label: "All changes" },
  { value: "changed", label: "Changed" },
  { value: "added", label: "Added" },
  { value: "removed", label: "Removed" },
];
const IMPORT_COMPARISON_FORMAT_FILTER_OPTIONS: {
  value: RenderImportComparisonFormatFilter;
  label: string;
}[] = [
  { value: "all", label: "All formats" },
  { value: "csv", label: "CSV" },
  { value: "json", label: "JSON" },
];

const DEFAULT_EXPORT_SETTINGS: RenderExportSettings = {
  profileId: "standard",
  width: 1920,
  height: 1080,
  frameRate: 30,
  crf: 18,
  encoderPreset: "medium",
  audioBitrateKbps: 192,
};
const FALLBACK_RENDER_PROFILES: RenderProfile[] = [
  {
    profileId: "fast_preview",
    name: "Fast Preview",
    settings: {
      profileId: "fast_preview",
      width: 640,
      height: 360,
      frameRate: 15,
      crf: 32,
      encoderPreset: "veryfast",
      audioBitrateKbps: 96,
    },
  },
  {
    profileId: "draft",
    name: "Draft",
    settings: {
      profileId: "draft",
      width: 854,
      height: 480,
      frameRate: 24,
      crf: 28,
      encoderPreset: "veryfast",
      audioBitrateKbps: 128,
    },
  },
  { profileId: "standard", name: "Standard", settings: DEFAULT_EXPORT_SETTINGS },
  {
    profileId: "high_quality",
    name: "High Quality",
    settings: {
      profileId: "high_quality",
      width: 1920,
      height: 1080,
      frameRate: 30,
      crf: 16,
      encoderPreset: "slow",
      audioBitrateKbps: 256,
    },
  },
  {
    profileId: "archive",
    name: "Archive",
    settings: {
      profileId: "archive",
      width: 3840,
      height: 2160,
      frameRate: 30,
      crf: 14,
      encoderPreset: "slower",
      audioBitrateKbps: 320,
    },
  },
];

export function RenderPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [outputNameTemplate, setOutputNameTemplate] = useState(DEFAULT_OUTPUT_TEMPLATE);
  const [profiles, setProfiles] = useState<RenderProfile[]>(FALLBACK_RENDER_PROFILES);
  const [selectedProfileId, setSelectedProfileId] =
    useState<RenderProfileId>("standard");
  const [exportSettings, setExportSettings] =
    useState<RenderExportSettings>(DEFAULT_EXPORT_SETTINGS);
  const [isRendering, setIsRendering] = useState(false);
  const [message, setMessage] = useState("Ready to render the active timeline.");
  const [job, setJob] = useState<RenderJob | null>(null);
  const [jobs, setJobs] = useState<RenderJob[]>([]);
  const [preflightReport, setPreflightReport] =
    useState<RenderPreflightReport | null>(null);
  const [isPreflightChecking, setIsPreflightChecking] = useState(false);
  const [showToolSetupHint, setShowToolSetupHint] = useState(false);
  const [reviewNote, setReviewNote] = useState("");
  const [reviewFilter, setReviewFilter] = useState<RenderReviewFilter>("all");
  const [queueSort, setQueueSort] = useState<RenderQueueSort>("newest");
  const [queueSearch, setQueueSearch] = useState("");
  const [queuePage, setQueuePage] = useState(1);
  const [queuePageSize, setQueuePageSize] = useState(10);
  const [queueReport, setQueueReport] = useState<RenderQueueReport | null>(null);
  const [handoffBundle, setHandoffBundle] =
    useState<RenderQueueHandoffBundle | null>(null);
  const [reviewImportManifestPath, setReviewImportManifestPath] = useState("");
  const [reviewImportSummary, setReviewImportSummary] = useState("");
  const [reviewImportResult, setReviewImportResult] =
    useState<RenderBundleReviewImportResult | null>(null);
  const [reviewImportReports, setReviewImportReports] = useState<
    RenderBundleImportReportSummary[]
  >([]);
  const [compareBaseReportPath, setCompareBaseReportPath] = useState("");
  const [compareTargetReportPath, setCompareTargetReportPath] = useState("");
  const [importReportComparison, setImportReportComparison] =
    useState<RenderBundleImportReportComparison | null>(null);
  const [importComparisonReport, setImportComparisonReport] =
    useState<RenderBundleImportComparisonReport | null>(null);
  const [importComparisonReports, setImportComparisonReports] = useState<
    RenderBundleImportComparisonReportSummary[]
  >([]);
  const [importComparisonReportPreview, setImportComparisonReportPreview] =
    useState<RenderBundleImportComparisonReportPreview | null>(null);
  const [importComparisonHistorySearch, setImportComparisonHistorySearch] =
    useState("");
  const [importComparisonHistoryFilter, setImportComparisonHistoryFilter] =
    useState<RenderImportComparisonFilter>("all");
  const [importComparisonHistoryFormat, setImportComparisonHistoryFormat] =
    useState<RenderImportComparisonFormatFilter>("all");
  const [showPinnedImportComparisonReports, setShowPinnedImportComparisonReports] =
    useState(false);
  const [importComparisonFilter, setImportComparisonFilter] =
    useState<RenderImportComparisonFilter>("all");
  const [reviewImportDiagnosticsFilter, setReviewImportDiagnosticsFilter] =
    useState<RenderImportDiagnosticsFilter>("all");
  const [reportReviewFilter, setReportReviewFilter] =
    useState<RenderQueueReportReviewFilter>("all");
  const [reportJobStatusFilter, setReportJobStatusFilter] =
    useState<RenderQueueReportJobStatusFilter>("all");
  const [reportDateFrom, setReportDateFrom] = useState("");
  const [reportDateTo, setReportDateTo] = useState("");
  const [selectedJobIds, setSelectedJobIds] = useState<Set<string>>(
    () => new Set(),
  );

  useEffect(() => {
    void loadQueue();
    void loadProfiles();
    void loadImportReports();
    void loadImportComparisonReports();
  }, [location.search]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void runPreflight(false);
    }, 300);
    return () => window.clearTimeout(timeoutId);
  }, [outputNameTemplate, selectedProfileId, exportSettings]);

  useEffect(() => {
    if (!job || !["queued", "preparing", "running", "cancelling"].includes(job.status)) {
      return;
    }
    const intervalId = window.setInterval(() => {
      void refreshJob(job.jobId);
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, [job?.jobId, job?.status]);

  useEffect(() => {
    setReviewNote(job?.review?.note ?? "");
  }, [job?.jobId, job?.review?.note]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsRendering(true);
    setJob(null);
    setMessage("Checking render readiness...");
    try {
      const report = await runPreflight(true);
      if (!report.ready) {
        setMessage("Fix preflight issues before rendering.");
        setIsRendering(false);
        return;
      }
      setMessage("Starting render job...");
      const started = await startRenderJob({
        ...renderRequest(),
      });
      setJob(started);
      setJobs((current) => [...current, started]);
      setMessage(messageForJob(started));
    } catch (error) {
      const fallback = "Render failed";
      setMessage(error instanceof RenderApiError ? error.message : fallback);
      setIsRendering(false);
    }
  }

  async function runPreflight(updateMessage: boolean) {
    setIsPreflightChecking(true);
    try {
      const report = await checkRenderPreflight(renderRequest());
      setPreflightReport(report);
      if (updateMessage) {
        setMessage(
          report.ready
            ? "Render preflight passed."
            : "Fix preflight issues before rendering.",
        );
      }
      return report;
    } catch (error) {
      const failedReport = preflightFailureReport(
        error instanceof RenderApiError ? error.message : "Preflight unavailable",
      );
      setPreflightReport(failedReport);
      if (updateMessage) {
        setMessage(failedReport.groups[0]?.checks[0]?.message ?? "Preflight failed");
      }
      return failedReport;
    } finally {
      setIsPreflightChecking(false);
    }
  }

  function renderRequest(): StartRenderRequest {
    return {
      ...exportSettings,
      profileId: selectedProfileId,
      fileName: null,
      outputNameTemplate: outputNameTemplate.trim() || DEFAULT_OUTPUT_TEMPLATE,
    };
  }

  async function refreshJob(jobId: string) {
    try {
      const updated = await getRenderJob(jobId);
      setJob(updated);
      setJobs((current) =>
        current.map((item) => (item.jobId === updated.jobId ? updated : item)),
      );
      setMessage(messageForJob(updated));
      setIsRendering(["queued", "preparing", "running", "cancelling"].includes(updated.status));
    } finally {
      // Polling should not replace the last known job state with a transient error.
    }
  }

  async function cancelCurrentJob() {
    if (!job) return;
    setMessage("Cancelling render...");
    const cancelled = await cancelRenderJob(job.jobId);
    setJob(cancelled);
    setJobs((current) =>
      current.map((item) => (item.jobId === cancelled.jobId ? cancelled : item)),
    );
    setMessage(messageForJob(cancelled));
    setIsRendering(["queued", "preparing", "running", "cancelling"].includes(cancelled.status));
  }

  async function loadQueue() {
    try {
      const queue = await listRenderJobs();
      setJobs(queue.jobs);
      const requestedJob = requestedReviewJob(queue.jobs, location.search);
      const selected = requestedJob ?? latestMatchingJob(queue.jobs, reviewFilter);
      setJob(selected);
      setIsRendering(
        selected
          ? ["queued", "preparing", "running", "cancelling"].includes(selected.status)
          : false,
      );
      if (selected) {
        setMessage(
          requestedJob ? `Ready to review ${requestedJob.fileName}` : messageForJob(selected),
        );
      }
    } catch (error) {
      setMessage(error instanceof RenderApiError ? error.message : "Render queue unavailable");
    }
  }

  async function loadProfiles() {
    try {
      const loaded = await listRenderProfiles();
      setProfiles(loaded.profiles);
    } finally {
      // Built-in profiles remain available when the backend is still warming up.
    }
  }

  async function loadImportReports() {
    try {
      const history = await listRenderBundleImportReports();
      setReviewImportReports(history.reports);
      setCompareBaseReportPath((current) =>
        current || history.reports[1]?.reportPath || history.reports[0]?.reportPath || "",
      );
      setCompareTargetReportPath((current) =>
        current || history.reports[0]?.reportPath || "",
      );
    } finally {
      // Import history is supplementary; render controls stay available.
    }
  }

  async function loadImportComparisonReports() {
    try {
      const history = await listRenderBundleImportComparisonReports();
      setImportComparisonReports(history.reports);
      setImportComparisonReportPreview((current) =>
        current &&
        history.reports.some(
          (report) => report.reportPath === current.report.reportPath,
        )
          ? current
          : null,
      );
    } finally {
      // Comparison report history is optional and should not block rendering.
    }
  }

  function selectProfile(profileId: RenderProfileId) {
    const profile = profiles.find((item) => item.profileId === profileId);
    setSelectedProfileId(profileId);
    if (profile) {
      setExportSettings(profile.settings);
    }
  }

  async function resumeCurrentJob() {
    if (!job) return;
    setMessage("Resuming render...");
    const resumed = await resumeRenderJob(job.jobId);
    setJob(resumed);
    setJobs((current) =>
      current.map((item) => (item.jobId === resumed.jobId ? resumed : item)),
    );
    setMessage(messageForJob(resumed));
    setIsRendering(["queued", "preparing", "running", "cancelling"].includes(resumed.status));
  }

  async function retryCurrentJob() {
    if (!job) return;
    setMessage("Retrying render...");
    const retried = await retryRenderJob(job.jobId);
    setJob(retried);
    setJobs((current) =>
      current.map((item) => (item.jobId === retried.jobId ? retried : item)),
    );
    setMessage(messageForJob(retried));
    setIsRendering(["queued", "preparing", "running", "cancelling"].includes(retried.status));
  }

  async function cleanupQueueHistory() {
    const queue = await cleanupRenderJobs(100);
    setJobs(queue.jobs);
    const selected =
      queue.jobs.find(
        (item) =>
          item.jobId === job?.jobId && matchesReviewFilter(item, reviewFilter),
      ) ?? latestMatchingJob(queue.jobs, reviewFilter);
    setJob(selected);
    setMessage(selected ? messageForJob(selected) : "Render history cleaned");
  }

  async function exportQueueReport(format: RenderQueueReportFormat) {
    setMessage(`Exporting ${format.toUpperCase()} render queue report...`);
    const report = await exportRenderQueueReport(
      format,
      reportReviewFilter,
      reportJobStatusFilter,
      reportDateFrom || null,
      reportDateTo || null,
    );
    setQueueReport(report);
    setMessage(
      `Render queue ${format.toUpperCase()} report exported with ${report.jobCount} jobs.`,
    );
  }

  async function exportHandoffBundle() {
    setMessage("Creating render handoff bundle...");
    const bundle = await exportRenderQueueHandoffBundle(
      reportReviewFilter,
      reportJobStatusFilter,
      reportDateFrom || null,
      reportDateTo || null,
    );
    setHandoffBundle(bundle);
    setReviewImportManifestPath(bundle.manifestPath);
    setReviewImportSummary("");
    setReviewImportResult(null);
    setReviewImportDiagnosticsFilter("all");
    setMessage(
      `Render handoff bundle created with ${bundle.jobCount} jobs and ${bundle.thumbnailCount} thumbnails.`,
    );
  }

  async function importBundleReviews() {
    const manifestPath = reviewImportManifestPath.trim();
    if (!manifestPath) {
      setMessage("Choose a bundle manifest before importing reviews.");
      return;
    }
    setMessage("Importing render reviews from bundle manifest...");
    const result = await importRenderBundleReviews(manifestPath);
    setReviewImportManifestPath(result.manifestPath);
    setReviewImportSummary(
      `${result.applied} applied, ${result.skipped} skipped`,
    );
    setReviewImportResult(result);
    setImportReportComparison(null);
    setImportComparisonReport(null);
    setImportComparisonFilter("all");
    setReviewImportDiagnosticsFilter(result.skipped > 0 ? "skipped" : "all");
    await loadQueue();
    await loadImportReports();
    setMessage(
      `Imported ${result.applied} render reviews (${result.accepted} accepted, ${result.rejected} rejected).`,
    );
  }

  function resetReportFilters() {
    setReportReviewFilter("all");
    setReportJobStatusFilter("all");
    setReportDateFrom("");
    setReportDateTo("");
    setMessage("Render report filters reset.");
  }

  async function openOutputFile() {
    if (!job?.outputPath) return;
    await openDesktopPath(job.outputPath);
  }

  async function openOutputFolder() {
    if (!job?.outputPath) return;
    await openDesktopPath(parentPath(job.outputPath));
  }

  async function openReportFile() {
    if (!queueReport) return;
    await openDesktopPath(queueReport.reportPath);
  }

  async function openReportFolder() {
    if (!queueReport) return;
    await openDesktopPath(parentPath(queueReport.reportPath));
  }

  async function openBundleFolder() {
    if (!handoffBundle) return;
    await openDesktopPath(handoffBundle.bundlePath);
  }

  async function openBundleArchive() {
    if (!handoffBundle) return;
    await openDesktopPath(handoffBundle.archivePath);
  }

  async function copyReportPath() {
    if (!queueReport) return;
    if (!navigator.clipboard) {
      setMessage("Clipboard is not available in this desktop webview.");
      return;
    }
    await navigator.clipboard.writeText(queueReport.reportPath);
    setMessage("Render report path copied.");
  }

  async function copyBundlePath() {
    if (!handoffBundle) return;
    if (!navigator.clipboard) {
      setMessage("Clipboard is not available in this desktop webview.");
      return;
    }
    await navigator.clipboard.writeText(handoffBundle.bundlePath);
    setMessage("Render handoff bundle path copied.");
  }

  async function copyBundleArchivePath() {
    if (!handoffBundle) return;
    if (!navigator.clipboard) {
      setMessage("Clipboard is not available in this desktop webview.");
      return;
    }
    await navigator.clipboard.writeText(handoffBundle.archivePath);
    setMessage("Render handoff bundle zip path copied.");
  }

  async function copySkippedImportDiagnostics() {
    if (!reviewImportResult) return;
    if (!navigator.clipboard) {
      setMessage("Clipboard is not available in this desktop webview.");
      return;
    }
    const skippedDetails = importDiagnosticDetails(
      reviewImportResult,
      "skipped",
    );
    await navigator.clipboard.writeText(importDiagnosticsCsv(skippedDetails));
    setMessage(`Copied ${skippedDetails.length} skipped import diagnostics.`);
  }

  async function copyImportReportPath() {
    if (!reviewImportResult) return;
    if (!navigator.clipboard) {
      setMessage("Clipboard is not available in this desktop webview.");
      return;
    }
    await navigator.clipboard.writeText(reviewImportResult.reportPath);
    setMessage("Render import diagnostics report path copied.");
  }

  async function openImportReport() {
    if (!reviewImportResult) return;
    await openDesktopPath(reviewImportResult.reportPath);
  }

  async function copyImportReportHistoryPath(reportPath: string) {
    if (!navigator.clipboard) {
      setMessage("Clipboard is not available in this desktop webview.");
      return;
    }
    await navigator.clipboard.writeText(reportPath);
    setMessage("Render import history report path copied.");
  }

  async function openImportReportHistory(reportPath: string) {
    await openDesktopPath(reportPath);
  }

  async function copyImportComparisonReportPath() {
    if (!importComparisonReport) return;
    if (!navigator.clipboard) {
      setMessage("Clipboard is not available in this desktop webview.");
      return;
    }
    await navigator.clipboard.writeText(importComparisonReport.reportPath);
    setMessage("Render import comparison report path copied.");
  }

  async function openImportComparisonReport() {
    if (!importComparisonReport) return;
    await openDesktopPath(importComparisonReport.reportPath);
  }

  async function copyImportComparisonReportHistoryPath(reportPath: string) {
    if (!navigator.clipboard) {
      setMessage("Clipboard is not available in this desktop webview.");
      return;
    }
    await navigator.clipboard.writeText(reportPath);
    setMessage("Render import comparison history report path copied.");
  }

  async function openImportComparisonReportHistory(reportPath: string) {
    await openDesktopPath(reportPath);
  }

  async function previewImportComparisonReportHistory(reportPath: string) {
    setMessage("Loading comparison report preview...");
    const preview = await previewRenderBundleImportComparisonReport(reportPath);
    setImportComparisonReportPreview(preview);
    setMessage(
      `Preview loaded with ${preview.rows.length} of ${preview.totalRows} rows.`,
    );
  }

  async function copyImportComparisonPreviewCsv() {
    if (!importComparisonReportPreview) return;
    if (!navigator.clipboard) {
      setMessage("Clipboard is not available in this desktop webview.");
      return;
    }
    await navigator.clipboard.writeText(
      importComparisonPreviewCsv(importComparisonReportPreview),
    );
    setMessage("Comparison preview CSV copied.");
  }

  function downloadImportComparisonPreviewCsv() {
    if (!importComparisonReportPreview) return;
    downloadTextFile(
      importComparisonPreviewFileName(importComparisonReportPreview),
      importComparisonPreviewCsv(importComparisonReportPreview),
      "text/csv;charset=utf-8",
    );
    setMessage("Comparison preview CSV downloaded.");
  }

  function printImportComparisonPreview() {
    if (!importComparisonReportPreview) return;
    window.print();
    setMessage("Comparison preview sent to print.");
  }

  async function pinImportComparisonReportHistory(
    reportPath: string,
    pinned: boolean,
  ) {
    setMessage(pinned ? "Pinning comparison report..." : "Unpinning comparison report...");
    const result = await pinRenderBundleImportComparisonReport(reportPath, pinned);
    await loadImportComparisonReports();
    setImportComparisonReportPreview((current) =>
      current?.report.reportPath === result.reportPath
        ? {
            ...current,
            report: { ...current.report, pinned: result.pinned },
          }
        : current,
    );
    setMessage(
      result.pinned
        ? "Comparison report pinned."
        : "Comparison report unpinned.",
    );
  }

  async function compareImportReports() {
    if (!compareBaseReportPath || !compareTargetReportPath) {
      setMessage("Choose two import reports before comparing.");
      return;
    }
    if (compareBaseReportPath === compareTargetReportPath) {
      setMessage("Choose two different import reports to compare.");
      return;
    }
    setMessage("Comparing render import audit reports...");
    const comparison = await compareRenderBundleImportReports(
      compareBaseReportPath,
      compareTargetReportPath,
    );
    setImportReportComparison(comparison);
    setImportComparisonReport(null);
    setImportComparisonFilter("all");
    setMessage(
      `Compared import reports: ${comparison.differenceCount} differences.`,
    );
  }

  async function exportImportComparison(format: "csv" | "json") {
    if (!importReportComparison) return;
    setMessage(`Saving comparison ${format.toUpperCase()} report...`);
    const report = await exportRenderBundleImportComparisonReport(
      importReportComparison.baseReport.reportPath,
      importReportComparison.compareReport.reportPath,
      format,
      importComparisonFilter,
    );
    setImportComparisonReport(report);
    await loadImportComparisonReports();
    setMessage(
      `Saved ${report.differenceCount} ${report.changeFilter} comparison differences as ${format.toUpperCase()}.`,
    );
  }

  function downloadSkippedImportDiagnostics() {
    if (!reviewImportResult) return;
    const skippedDetails = importDiagnosticDetails(
      reviewImportResult,
      "skipped",
    );
    downloadTextFile(
      "render-import-skipped-diagnostics.csv",
      importDiagnosticsCsv(skippedDetails),
      "text/csv;charset=utf-8",
    );
    setMessage(`Downloaded ${skippedDetails.length} skipped diagnostics.`);
  }

  async function saveReview(status: RenderReviewStatus) {
    if (!job) return;
    setMessage("Saving render review...");
    const reviewed = await reviewRenderJob(
      job.jobId,
      status,
      reviewNote.trim() || null,
    );
    const updatedJobs = jobs.map((item) =>
      item.jobId === reviewed.jobId ? reviewed : item,
    );
    setJobs(updatedJobs);
    const selected = matchesReviewFilter(reviewed, reviewFilter)
      ? reviewed
      : latestMatchingJob(updatedJobs, reviewFilter);
    setJob(selected);
    setMessage(
      selected ? `Render ${status}.` : `Render ${status}. No jobs match filter.`,
    );
  }

  async function clearCurrentReview() {
    if (!job?.review) return;
    setMessage("Reverting render review...");
    const cleared = await clearRenderJobReview(job.jobId);
    const updatedJobs = jobs.map((item) =>
      item.jobId === cleared.jobId ? cleared : item,
    );
    setJobs(updatedJobs);
    const selected = matchesReviewFilter(cleared, reviewFilter)
      ? cleared
      : latestMatchingJob(updatedJobs, reviewFilter);
    setJob(selected);
    setMessage(
      selected ? "Render review reverted." : "Render review reverted. No jobs match filter.",
    );
  }

  async function saveBulkReview(status: RenderReviewStatus) {
    const targets = jobs.filter(
      (item) => selectedJobIds.has(item.jobId) && canReviewJob(item),
    );
    if (targets.length === 0) {
      setMessage("Select completed outputs before bulk review.");
      return;
    }
    setMessage(`Saving ${targets.length} render reviews...`);
    const reviewedJobs: RenderJob[] = [];
    for (const target of targets) {
      reviewedJobs.push(await reviewRenderJob(target.jobId, status, null));
    }
    const reviewedById = new Map(
      reviewedJobs.map((item) => [item.jobId, item] as const),
    );
    const updatedJobs = jobs.map((item) => reviewedById.get(item.jobId) ?? item);
    setJobs(updatedJobs);
    setSelectedJobIds((current) => {
      const next = new Set(current);
      for (const target of targets) next.delete(target.jobId);
      return next;
    });
    const selected =
      (job ? updatedJobs.find((item) => item.jobId === job.jobId) : null) ??
      latestMatchingJob(updatedJobs, reviewFilter);
    const visibleSelected =
      selected && matchesReviewFilter(selected, reviewFilter)
        ? selected
        : latestMatchingJob(updatedJobs, reviewFilter);
    setJob(visibleSelected);
    setMessage(`${targets.length} render output${targets.length === 1 ? "" : "s"} ${status}.`);
  }

  async function clearBulkReview() {
    const targets = jobs.filter(
      (item) => selectedJobIds.has(item.jobId) && canClearReviewJob(item),
    );
    if (targets.length === 0) {
      setMessage("Select reviewed outputs before reverting review.");
      return;
    }
    setMessage(`Reverting ${targets.length} render reviews...`);
    const clearedJobs: RenderJob[] = [];
    for (const target of targets) {
      clearedJobs.push(await clearRenderJobReview(target.jobId));
    }
    const clearedById = new Map(
      clearedJobs.map((item) => [item.jobId, item] as const),
    );
    const updatedJobs = jobs.map((item) => clearedById.get(item.jobId) ?? item);
    setJobs(updatedJobs);
    setSelectedJobIds((current) => {
      const next = new Set(current);
      for (const target of targets) next.delete(target.jobId);
      return next;
    });
    const selected =
      (job ? updatedJobs.find((item) => item.jobId === job.jobId) : null) ??
      latestMatchingJob(updatedJobs, reviewFilter);
    const visibleSelected =
      selected && matchesReviewFilter(selected, reviewFilter)
        ? selected
        : latestMatchingJob(updatedJobs, reviewFilter);
    setJob(visibleSelected);
    setMessage(`${targets.length} render review${targets.length === 1 ? "" : "s"} reverted.`);
  }

  function handleReviewFilterChange(filter: RenderReviewFilter) {
    setReviewFilter(filter);
    setQueuePage(1);
    if (job && matchesReviewFilter(job, filter)) return;
    const selected = latestMatchingJob(jobs, filter);
    setJob(selected);
    setMessage(selected ? messageForJob(selected) : "No jobs match this filter.");
  }

  function handleQueueSearch(value: string) {
    setQueueSearch(value);
    setQueuePage(1);
  }

  function handleQueueSort(sort: RenderQueueSort) {
    setQueueSort(sort);
    setQueuePage(1);
  }

  function handleQueuePageSize(size: number) {
    setQueuePageSize(size);
    setQueuePage(1);
  }

  function toggleJobSelection(jobId: string, checked: boolean) {
    setSelectedJobIds((current) => {
      const next = new Set(current);
      if (checked) next.add(jobId);
      else next.delete(jobId);
      return next;
    });
  }

  function selectVisibleReviewableJobs() {
    setSelectedJobIds((current) => {
      const next = new Set(current);
      for (const item of pagedJobs) {
        if (canReviewJob(item)) next.add(item.jobId);
      }
      return next;
    });
  }

  function handlePreflightFix(group: RenderPreflightGroup) {
    if (group.group === "Tool") {
      setShowToolSetupHint(true);
      setMessage("Configure FFmpeg and FFprobe, then run preflight again.");
      return;
    }
    if (group.group === "Timeline") {
      navigate("/timeline");
      return;
    }
    if (group.group === "Media") {
      navigate("/timeline");
      return;
    }
    if (group.group === "Output") {
      navigate("/projects");
      return;
    }
  }

  const progress = job?.progressPercent ?? 0;
  const canCancel = job ? ["queued", "preparing", "running"].includes(job.status) : false;
  const canResume = job
    ? ["interrupted", "failed", "cancelled"].includes(job.status)
    : false;
  const fastPreviewProfile = profiles.find(
    (profile) => profile.profileId === "fast_preview",
  );
  const shouldSuggestFastPreview = Boolean(
    fastPreviewProfile &&
      preflightReport?.ready &&
      selectedProfileId !== "fast_preview" &&
      (preflightReport.durationMilliseconds ?? 0) >=
        FAST_PREVIEW_LONG_TIMELINE_MILLISECONDS,
  );
  const canRetry = job?.status === "failed";
  const hasOutput = Boolean(job?.outputPath);
  const canReview = job?.status === "completed" && hasOutput;
  const playbackUri = job ? fileUriFromPath(job.outputPath) : null;
  const queueSummary = summarizeRenderQueue(jobs);
  const filteredJobs = jobs.filter((item) => matchesReviewFilter(item, reviewFilter));
  const searchedJobs = filterRenderJobsBySearch(filteredJobs, queueSearch);
  const sortedFilteredJobs = sortRenderJobs(searchedJobs, queueSort);
  const pageCount = Math.max(1, Math.ceil(sortedFilteredJobs.length / queuePageSize));
  const activeQueuePage = Math.min(queuePage, pageCount);
  const pageStart = (activeQueuePage - 1) * queuePageSize;
  const pagedJobs = sortedFilteredJobs.slice(pageStart, pageStart + queuePageSize);
  const pageEnd = pageStart + pagedJobs.length;
  const selectedReviewableCount = jobs.filter(
    (item) => selectedJobIds.has(item.jobId) && canReviewJob(item),
  ).length;
  const selectedReviewedCount = jobs.filter(
    (item) => selectedJobIds.has(item.jobId) && canClearReviewJob(item),
  ).length;
  const visibleReviewableCount = pagedJobs.filter(canReviewJob).length;
  const visibleImportComparisonDifferences = importReportComparison
    ? filteredImportReportDifferences(
        importReportComparison,
        importComparisonFilter,
      )
    : [];
  const visibleImportComparisonReports = filterImportComparisonReports(
    importComparisonReports,
    importComparisonHistorySearch,
    importComparisonHistoryFilter,
    importComparisonHistoryFormat,
    showPinnedImportComparisonReports,
  );
  const renderGuide = guideForPreflight(preflightReport);

  return (
    <section className="renderWorkspace" aria-label="Render workspace">
      <header className="timelineToolbar">
        <div>
          <h2>MP4 render</h2>
          <p className="timelineMessage" role="status">
            {message}
          </p>
        </div>
      </header>

      <WorkflowHandoff
        current="Render"
        nextLabel="Review dashboard"
        nextTo="/projects"
        note="After render completes, return to the dashboard to review output status."
      />

      {renderGuide && (
        <WorkspaceGuide
          actionLabel={renderGuide.actionLabel}
          message={renderGuide.message}
          title={renderGuide.title}
          to={renderGuide.to}
          tone="warning"
        />
      )}

      <div className="renderGrid">
        <form
          className="renderPanel"
          id="render-monitor"
          onSubmit={(event) => void submit(event)}
        >
          <div className="renderPanelHeading">
            <Film aria-hidden="true" size={20} />
            <h3>Output</h3>
          </div>
          <label>
            Naming template
            <input
              maxLength={124}
              minLength={1}
              required
              type="text"
              value={outputNameTemplate}
              onChange={(event) => setOutputNameTemplate(event.target.value)}
            />
          </label>
          <div className="renderSettingsGrid">
            <label>
              Profile
              <select
                value={selectedProfileId}
                onChange={(event) =>
                  selectProfile(event.target.value as RenderProfileId)
                }
              >
                {profiles.map((profile) => (
                  <option key={profile.profileId} value={profile.profileId}>
                    {profile.name}
                  </option>
                ))}
              </select>
            </label>
            {shouldSuggestFastPreview && fastPreviewProfile && (
              <div className="renderProfileHint">
                <div>
                  <strong>Long timeline detected</strong>
                  <span>
                    Fast Preview lowers resolution and FPS for quicker review renders.
                  </span>
                </div>
                <button
                  className="secondaryButton"
                  type="button"
                  onClick={() => selectProfile(fastPreviewProfile.profileId)}
                >
                  Use Fast Preview
                </button>
              </div>
            )}
            <label>
              Resolution
              <select
                value={`${exportSettings.width}x${exportSettings.height}`}
                onChange={(event) => {
                  const [width, height] = event.target.value.split("x").map(Number);
                  setExportSettings((current) => ({ ...current, width, height }));
                }}
              >
                <option value="640x360">640x360</option>
                <option value="854x480">854x480</option>
                <option value="1280x720">1280x720</option>
                <option value="1920x1080">1920x1080</option>
                <option value="2560x1440">2560x1440</option>
                <option value="3840x2160">3840x2160</option>
              </select>
            </label>
            <label>
              FPS
              <select
                value={exportSettings.frameRate}
                onChange={(event) =>
                  setExportSettings((current) => ({
                    ...current,
                    frameRate: Number(event.target.value),
                  }))
                }
              >
                <option value={15}>15</option>
                <option value={24}>24</option>
                <option value={30}>30</option>
                <option value={60}>60</option>
              </select>
            </label>
            <label>
              CRF
              <input
                max={51}
                min={0}
                type="number"
                value={exportSettings.crf}
                onChange={(event) =>
                  setExportSettings((current) => ({
                    ...current,
                    crf: Number(event.target.value),
                  }))
                }
              />
            </label>
            <label>
              Preset
              <select
                value={exportSettings.encoderPreset}
                onChange={(event) =>
                  setExportSettings((current) => ({
                    ...current,
                    encoderPreset: event.target.value as RenderExportSettings["encoderPreset"],
                  }))
                }
              >
                <option value="veryfast">veryfast</option>
                <option value="fast">fast</option>
                <option value="medium">medium</option>
                <option value="slow">slow</option>
                <option value="slower">slower</option>
              </select>
            </label>
            <label>
              Audio
              <select
                value={exportSettings.audioBitrateKbps}
                onChange={(event) =>
                  setExportSettings((current) => ({
                    ...current,
                    audioBitrateKbps: Number(event.target.value),
                  }))
                }
              >
                <option value={96}>96 kbps</option>
                <option value={128}>128 kbps</option>
                <option value={192}>192 kbps</option>
                <option value={256}>256 kbps</option>
                <option value={320}>320 kbps</option>
              </select>
            </label>
          </div>
          <div className="toolbarActions">
            <button
              className="secondaryButton"
              disabled={isRendering}
              type="button"
              onClick={() => {
                setOutputNameTemplate(DEFAULT_OUTPUT_TEMPLATE);
                setSelectedProfileId("standard");
                setExportSettings(DEFAULT_EXPORT_SETTINGS);
                setJob(null);
                setPreflightReport(null);
                setMessage("Ready to render the active timeline.");
                setIsRendering(false);
              }}
            >
              <RotateCcw aria-hidden="true" size={16} />
              Reset
            </button>
            <button
              className="primaryButton"
              disabled={isPreflightChecking || preflightReport?.ready === false}
              type="submit"
            >
              <Play aria-hidden="true" size={16} />
              {isRendering ? "Queue MP4" : "Render MP4"}
            </button>
            <button
              className="secondaryButton"
              disabled={!canCancel}
              type="button"
              onClick={() => void cancelCurrentJob()}
            >
              <Square aria-hidden="true" size={16} />
              Cancel
            </button>
            <button
              className="secondaryButton"
              disabled={!canResume}
              type="button"
              onClick={() => void resumeCurrentJob()}
            >
              <Play aria-hidden="true" size={16} />
              Resume
            </button>
            <button
              className="secondaryButton"
              disabled={!canRetry}
              type="button"
              onClick={() => void retryCurrentJob()}
            >
              <RotateCcw aria-hidden="true" size={16} />
              Retry
            </button>
          </div>
          <div className="renderProgress">
            <progress max="100" value={progress} />
            <span>{progress.toFixed(1)}%</span>
          </div>
        </form>

        <div className="renderPanel renderResultPanel">
          <div className="renderPanelHeading">
            <Film aria-hidden="true" size={20} />
            <h3>Result</h3>
        </div>
        {job ? (
          <>
            {playbackUri ? (
              <div className="renderPlayback" aria-label="Rendered MP4 preview">
                <video
                  aria-label="Rendered MP4 playback"
                  className="renderPlaybackVideo"
                  controls
                  poster={job.preview?.thumbnailUri ?? undefined}
                  preload="metadata"
                  src={playbackUri}
                />
                {job.preview && (
                  <div className="renderPlaybackDetails">
                    {job.preview.thumbnailUri ? (
                      <img
                        alt="Render preview thumbnail"
                        className="renderPlaybackThumb"
                        src={job.preview.thumbnailUri}
                      />
                    ) : (
                      <div className="renderPlaybackThumbPlaceholder">
                        No thumbnail
                      </div>
                    )}
                    <div className="renderPreviewMeta">
                      <strong>{formatPreviewMetadata(job)}</strong>
                      <span>{formatPreviewGeneratedAt(job.preview.generatedAt)}</span>
                    </div>
                  </div>
                )}
                {job.preview?.errorMessage && (
                  <small className="renderPreviewWarning">
                    {job.preview.errorMessage}
                  </small>
                )}
              </div>
            ) : (
              job.preview && (
                <div className="renderPreview" aria-label="Render output preview">
                  {job.preview.thumbnailUri ? (
                    <img
                      alt="Render preview thumbnail"
                      className="renderPreviewImage"
                      src={job.preview.thumbnailUri}
                    />
                  ) : (
                    <div className="renderPreviewPlaceholder">
                      Preview thumbnail unavailable
                    </div>
                  )}
                  <div className="renderPreviewMeta">
                    <strong>{formatPreviewMetadata(job)}</strong>
                    <span>{formatPreviewGeneratedAt(job.preview.generatedAt)}</span>
                  </div>
                  {job.preview.errorMessage && (
                    <small className="renderPreviewWarning">
                      {job.preview.errorMessage}
                    </small>
                  )}
                </div>
              )
            )}
            <div className="renderReviewPanel" aria-label="Render review">
              <div className="renderReviewHeader">
                <strong>{formatReviewStatus(job)}</strong>
                <span>{formatReviewedAt(job)}</span>
              </div>
              <label>
                Review notes
                <textarea
                  maxLength={1000}
                  rows={3}
                  value={reviewNote}
                  onChange={(event) => setReviewNote(event.target.value)}
                />
              </label>
              <div className="toolbarActions renderReviewActions">
                {job.review && (
                  <button
                    className="secondaryButton"
                    type="button"
                    onClick={() => navigate("/projects")}
                  >
                    Return to Dashboard
                  </button>
                )}
                <button
                  className="secondaryButton"
                  disabled={!job.review}
                  type="button"
                  onClick={() => void clearCurrentReview()}
                >
                  <RotateCcw aria-hidden="true" size={16} />
                  Revert review
                </button>
                <button
                  className="secondaryButton"
                  disabled={!canReview}
                  type="button"
                  onClick={() => void saveReview("rejected")}
                >
                  <AlertTriangle aria-hidden="true" size={16} />
                  Reject
                </button>
                <button
                  className="primaryButton"
                  disabled={!canReview}
                  type="button"
                  onClick={() => void saveReview("accepted")}
                >
                  <CheckCircle2 aria-hidden="true" size={16} />
                  Accept
                </button>
              </div>
            </div>
            <dl className="renderFacts">
              <div>
                <dt>Status</dt>
                <dd>{job.status}</dd>
              </div>
              <div>
                <dt>Path</dt>
                <dd>{job.outputPath ?? "Pending"}</dd>
              </div>
              <div>
                <dt>Duration</dt>
                <dd>{formatDuration(job.durationMilliseconds)}</dd>
              </div>
              <div>
                <dt>Size</dt>
                <dd>{job.sizeBytes === null ? "Pending" : formatBytes(job.sizeBytes)}</dd>
              </div>
              {job.exportSettings && (
                <div>
                  <dt>Export</dt>
                  <dd>{formatExportSettings(job.exportSettings)}</dd>
                </div>
              )}
              {job.errorMessage && (
                <div>
                  <dt>Error</dt>
                  <dd>{job.errorMessage}</dd>
                </div>
              )}
              {job.diagnostics && (
                <>
                  <div>
                    <dt>Command</dt>
                    <dd>{formatCommandSummary(job)}</dd>
                  </div>
                  <div>
                    <dt>Metrics</dt>
                    <dd>{formatRenderMetrics(job)}</dd>
                  </div>
                  {job.diagnostics.stderrTail && (
                    <div>
                      <dt>FFmpeg stderr</dt>
                      <dd className="diagnosticText">{job.diagnostics.stderrTail}</dd>
                    </div>
                  )}
                </>
              )}
            </dl>
          </>
          ) : (
            <p className="timelineMessage">Rendered output will appear here.</p>
          )}
          <div className="toolbarActions renderOutputActions">
            <button
              className="secondaryButton"
              disabled={!hasOutput}
              type="button"
              onClick={() => void openOutputFile()}
            >
              <ExternalLink aria-hidden="true" size={16} />
              Open file
            </button>
            <button
              className="secondaryButton"
              disabled={!hasOutput}
              type="button"
              onClick={() => void openOutputFolder()}
            >
              <FolderOpen aria-hidden="true" size={16} />
              Open folder
            </button>
          </div>
        </div>
      </div>

      <div className="renderPanel preflightPanel">
        <div className="renderPanelHeading">
          <Film aria-hidden="true" size={20} />
          <h3>Preflight</h3>
          <button
            className="secondaryButton"
            disabled={isPreflightChecking}
            type="button"
            onClick={() => void runPreflight(true)}
          >
            <RotateCcw aria-hidden="true" size={16} />
            Check
          </button>
        </div>
        <div className="preflightGrid">
          {preflightGroups(preflightReport).map((group) => (
            <div className={`preflightGroup ${group.status}`} key={group.group}>
              <div className="preflightGroupHeader">
                {iconForPreflight(group.status)}
                <strong>{group.group}</strong>
                <span>{labelForPreflight(group.status)}</span>
              </div>
              <ul>
                {group.checks.map((check) => (
                  <li key={`${group.group}-${check.code}`}>{check.message}</li>
                ))}
              </ul>
              {group.status !== "passed" && (
                <button
                  className="preflightFixButton"
                  type="button"
                  onClick={() => handlePreflightFix(group)}
                >
                  {preflightActionLabel(group.group)}
                </button>
              )}
            </div>
          ))}
        </div>
        {showToolSetupHint && (
          <div className="toolSetupHint" role="note">
            <strong>Tool setup</strong>
            <span>
              Set `FFMPEG_PATH` to `ffmpeg.exe` and keep `ffprobe.exe` in the
              same folder, or add both tools to `PATH`, then restart the backend.
            </span>
          </div>
        )}
      </div>

      {jobs.length > 0 && (
        <div className="renderPanel renderQueuePanel" id="render-queue">
          <div className="renderPanelHeading">
            <Film aria-hidden="true" size={20} />
            <h3>Queue</h3>
            <button
              className="secondaryButton"
              type="button"
              onClick={() => void cleanupQueueHistory()}
            >
              <RotateCcw aria-hidden="true" size={16} />
              Cleanup
            </button>
          </div>
          <div className="renderQueueReport" aria-label="Render queue report">
            <div>
              <strong>Report</strong>
              <span>
                {queueReport
                  ? `${queueReport.format.toUpperCase()} · ${queueReport.jobCount} jobs`
                  : "Export durable queue history for handoff"}
              </span>
              {queueReport && (
                <small className="renderQueueReportMeta">
                  Last export: {formatReportFilters(queueReport)}
                </small>
              )}
              {handoffBundle && (
                <small className="renderQueueReportMeta">
                  Bundle: {handoffBundle.jobCount} jobs,{" "}
                  {handoffBundle.thumbnailCount} thumbnails, zip ready
                </small>
              )}
              {reviewImportSummary && (
                <small className="renderQueueReportMeta">
                  Review import: {reviewImportSummary}
                </small>
              )}
            </div>
            <div className="renderQueueSummary" aria-label="Render review summary">
              <div>
                <strong>{queueSummary.total}</strong>
                <span>Total outputs</span>
              </div>
              <div>
                <strong>{queueSummary.accepted}</strong>
                <span>Accepted outputs</span>
              </div>
              <div>
                <strong>{queueSummary.rejected}</strong>
                <span>Rejected outputs</span>
              </div>
              <div>
                <strong>{queueSummary.notReviewed}</strong>
                <span>Not reviewed outputs</span>
              </div>
              <div>
                <strong>{queueSummary.completed}</strong>
                <span>Completed jobs</span>
              </div>
              <div>
                <strong>{queueSummary.failed}</strong>
                <span>Failed jobs</span>
              </div>
              <div>
                <strong>
                  {queueSummary.queued +
                    queueSummary.preparing +
                    queueSummary.running +
                    queueSummary.cancelling}
                </strong>
                <span>Active jobs</span>
              </div>
              <div>
                <strong>{queueSummary.cancelled + queueSummary.interrupted}</strong>
                <span>Stopped jobs</span>
              </div>
            </div>
            <div className="renderQueueReportFilters">
              <label>
                Review
                <select
                  value={reportReviewFilter}
                  onChange={(event) =>
                    setReportReviewFilter(
                      event.target.value as RenderQueueReportReviewFilter,
                    )
                  }
                >
                  {REVIEW_FILTER_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Status
                <select
                  value={reportJobStatusFilter}
                  onChange={(event) =>
                    setReportJobStatusFilter(
                      event.target.value as RenderQueueReportJobStatusFilter,
                    )
                  }
                >
                  {REPORT_STATUS_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                From
                <input
                  type="date"
                  value={reportDateFrom}
                  onChange={(event) => setReportDateFrom(event.target.value)}
                />
              </label>
              <label>
                To
                <input
                  type="date"
                  value={reportDateTo}
                  onChange={(event) => setReportDateTo(event.target.value)}
                />
              </label>
              <button
                className="secondaryButton reportFilterReset"
                type="button"
                onClick={resetReportFilters}
              >
                <RotateCcw aria-hidden="true" size={16} />
                Reset filters
              </button>
              <label className="bundleManifestPathField">
                Manifest path
                <input
                  type="text"
                  value={reviewImportManifestPath}
                  onChange={(event) =>
                    setReviewImportManifestPath(event.target.value)
                  }
                  placeholder="Bundle manifest.json"
                />
              </label>
            </div>
            <div className="renderQueueReportActions">
              <button
                className="secondaryButton"
                type="button"
                onClick={() => void exportHandoffBundle()}
              >
                Create bundle
              </button>
              <button
                className="secondaryButton"
                disabled={!handoffBundle}
                type="button"
                onClick={() => void copyBundlePath()}
              >
                <Copy aria-hidden="true" size={16} />
                Copy bundle path
              </button>
              <button
                className="secondaryButton"
                disabled={!handoffBundle}
                type="button"
                onClick={() => void openBundleFolder()}
              >
                <FolderOpen aria-hidden="true" size={16} />
                Open bundle
              </button>
              <button
                className="secondaryButton"
                disabled={!handoffBundle}
                type="button"
                onClick={() => void copyBundleArchivePath()}
              >
                <Copy aria-hidden="true" size={16} />
                Copy zip path
              </button>
              <button
                className="secondaryButton"
                disabled={!handoffBundle}
                type="button"
                onClick={() => void openBundleArchive()}
              >
                <ExternalLink aria-hidden="true" size={16} />
                Open zip
              </button>
              <button
                className="secondaryButton"
                disabled={!reviewImportManifestPath.trim()}
                type="button"
                onClick={() => void importBundleReviews()}
              >
                <CheckCircle2 aria-hidden="true" size={16} />
                Import reviews
              </button>
              <button
                className="secondaryButton"
                type="button"
                onClick={() => void exportQueueReport("csv")}
              >
                Export CSV
              </button>
              <button
                className="secondaryButton"
                type="button"
                onClick={() => void exportQueueReport("json")}
              >
                Export JSON
              </button>
              <button
                className="secondaryButton"
                disabled={!queueReport}
                type="button"
                onClick={() => void copyReportPath()}
              >
                <Copy aria-hidden="true" size={16} />
                Copy path
              </button>
              <button
                className="secondaryButton"
                disabled={!queueReport}
                type="button"
                onClick={() => void openReportFile()}
              >
                <ExternalLink aria-hidden="true" size={16} />
                Open report
              </button>
              <button
                className="secondaryButton"
                disabled={!queueReport}
                type="button"
                onClick={() => void openReportFolder()}
              >
                <FolderOpen aria-hidden="true" size={16} />
                Open folder
              </button>
            </div>
            {reviewImportResult && (
              <div
                className="renderImportDiagnostics"
                aria-label="Render review import diagnostics"
              >
                <div className="renderImportDiagnosticsHeader">
                  <strong>Import diagnostics</strong>
                  <span>
                    {reviewImportResult.applied} applied,{" "}
                    {reviewImportResult.skipped} skipped
                  </span>
                  <small>{reviewImportResult.reportPath}</small>
                </div>
                <div className="renderImportDiagnosticsTools">
                  <label>
                    Filter
                    <select
                      aria-label="Import diagnostics filter"
                      value={reviewImportDiagnosticsFilter}
                      onChange={(event) =>
                        setReviewImportDiagnosticsFilter(
                          event.target.value as RenderImportDiagnosticsFilter,
                        )
                      }
                    >
                      {IMPORT_DIAGNOSTICS_FILTER_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    className="secondaryButton"
                    disabled={reviewImportResult.skipped === 0}
                    type="button"
                    onClick={() => void copySkippedImportDiagnostics()}
                  >
                    <Copy aria-hidden="true" size={16} />
                    Copy skipped
                  </button>
                  <button
                    className="secondaryButton"
                    disabled={reviewImportResult.skipped === 0}
                    type="button"
                    onClick={downloadSkippedImportDiagnostics}
                  >
                    <Download aria-hidden="true" size={16} />
                    Export skipped CSV
                  </button>
                  <button
                    className="secondaryButton"
                    type="button"
                    onClick={() => void copyImportReportPath()}
                  >
                    <Copy aria-hidden="true" size={16} />
                    Copy import report
                  </button>
                  <button
                    className="secondaryButton"
                    type="button"
                    onClick={() => void openImportReport()}
                  >
                    <ExternalLink aria-hidden="true" size={16} />
                    Open import report
                  </button>
                </div>
                <div className="renderImportDiagnosticsRows">
                  {importDiagnosticDetails(
                    reviewImportResult,
                    reviewImportDiagnosticsFilter,
                  ).map((detail, index) => (
                    <div
                      className={`renderImportDiagnosticRow ${
                        detail.status === "applied"
                          ? "renderImportDiagnosticRowApplied"
                          : "renderImportDiagnosticRowSkipped"
                      }`}
                      key={`${detail.jobId ?? "missing"}-${index}`}
                    >
                      <span>{detail.jobId ?? "Missing jobId"}</span>
                      <span>{formatImportDecision(detail.decision)}</span>
                      <strong>{formatImportStatus(detail.status)}</strong>
                      <small>{detail.reason ?? "Applied to render history."}</small>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div
              className="renderImportHistory"
              aria-label="Render import audit history"
            >
              <div className="renderImportDiagnosticsHeader">
                <strong>Import audit history</strong>
                <span>{reviewImportReports.length} reports</span>
              </div>
              <div className="renderImportDiagnosticsTools">
                <label>
                  Base report
                  <select
                    value={compareBaseReportPath}
                    onChange={(event) => {
                      setCompareBaseReportPath(event.target.value);
                      setImportReportComparison(null);
                      setImportComparisonReport(null);
                    }}
                  >
                    {reviewImportReports.map((report) => (
                      <option key={report.reportPath} value={report.reportPath}>
                        {formatImportReportOption(report)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Compare report
                  <select
                    value={compareTargetReportPath}
                    onChange={(event) => {
                      setCompareTargetReportPath(event.target.value);
                      setImportReportComparison(null);
                      setImportComparisonReport(null);
                    }}
                  >
                    {reviewImportReports.map((report) => (
                      <option key={report.reportPath} value={report.reportPath}>
                        {formatImportReportOption(report)}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  className="secondaryButton"
                  disabled={reviewImportReports.length < 2}
                  type="button"
                  onClick={() => void compareImportReports()}
                >
                  Compare reports
                </button>
                <button
                  className="secondaryButton"
                  type="button"
                  onClick={() => void loadImportReports()}
                >
                  <RotateCcw aria-hidden="true" size={16} />
                  Refresh history
                </button>
              </div>
              {reviewImportReports.length > 0 ? (
                <div className="renderImportHistoryRows">
                  {reviewImportReports.map((report) => (
                    <div
                      className="renderImportHistoryRow"
                      key={report.reportPath}
                    >
                      <div>
                        <strong>{formatImportReportDate(report.importedAt)}</strong>
                        <span>
                          {report.applied} applied, {report.skipped} skipped,{" "}
                          {report.accepted} accepted, {report.rejected} rejected
                        </span>
                        <small>{report.reportPath}</small>
                      </div>
                      <div className="renderImportHistoryActions">
                        <button
                          className="secondaryButton"
                          type="button"
                          onClick={() =>
                            void copyImportReportHistoryPath(report.reportPath)
                          }
                        >
                          <Copy aria-hidden="true" size={16} />
                          Copy report
                        </button>
                        <button
                          className="secondaryButton"
                          type="button"
                          onClick={() =>
                            void openImportReportHistory(report.reportPath)
                          }
                        >
                          <ExternalLink aria-hidden="true" size={16} />
                          Open
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <small className="renderQueueReportMeta">
                  No import audit reports yet.
                </small>
              )}
              {importReportComparison && (
                <div className="renderImportComparison">
                  <div className="renderImportDiagnosticsHeader">
                    <strong>
                      Comparison: {importReportComparison.differenceCount} differences
                    </strong>
                    <small>
                      {formatImportReportDate(
                        importReportComparison.baseReport.importedAt,
                      )}{" "}
                      to{" "}
                      {formatImportReportDate(
                        importReportComparison.compareReport.importedAt,
                      )}
                    </small>
                  </div>
                  <div className="renderImportComparisonTools">
                    <label>
                      Difference filter
                      <select
                        value={importComparisonFilter}
                        onChange={(event) =>
                          setImportComparisonFilter(
                            event.target.value as RenderImportComparisonFilter,
                          )
                        }
                      >
                        {IMPORT_COMPARISON_FILTER_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      className="secondaryButton"
                      type="button"
                      onClick={() => exportImportComparison("csv")}
                    >
                      Export diff CSV
                    </button>
                    <button
                      className="secondaryButton"
                      type="button"
                      onClick={() => exportImportComparison("json")}
                    >
                      Export diff JSON
                    </button>
                    <span>{visibleImportComparisonDifferences.length} visible</span>
                  </div>
                  {importComparisonReport && (
                    <div className="renderImportComparisonReport">
                      <div>
                        <strong>
                          Saved {importComparisonReport.format.toUpperCase()} report
                        </strong>
                        <span>
                          {importComparisonReport.differenceCount}{" "}
                          {importComparisonReport.changeFilter} differences
                        </span>
                        <small>{importComparisonReport.reportPath}</small>
                      </div>
                      <div className="renderImportHistoryActions">
                        <button
                          className="secondaryButton"
                          type="button"
                          onClick={() => void copyImportComparisonReportPath()}
                        >
                          <Copy aria-hidden="true" size={16} />
                          Copy report
                        </button>
                        <button
                          className="secondaryButton"
                          type="button"
                          onClick={() => void openImportComparisonReport()}
                        >
                          <ExternalLink aria-hidden="true" size={16} />
                          Open report
                        </button>
                      </div>
                    </div>
                  )}
                  <div
                    className="renderImportComparisonHistory"
                    aria-label="Render import comparison report history"
                  >
                    <div className="renderImportDiagnosticsHeader">
                      <strong>Comparison report history</strong>
                      <span>
                        {visibleImportComparisonReports.length} /{" "}
                        {importComparisonReports.length} reports
                      </span>
                    </div>
                    <div className="renderImportComparisonHistoryTools">
                      <label>
                        Search reports
                        <input
                          placeholder="Path, format, date"
                          type="search"
                          value={importComparisonHistorySearch}
                          onChange={(event) =>
                            setImportComparisonHistorySearch(event.target.value)
                          }
                        />
                      </label>
                      <label>
                        Change
                        <select
                          value={importComparisonHistoryFilter}
                          onChange={(event) =>
                            setImportComparisonHistoryFilter(
                              event.target.value as RenderImportComparisonFilter,
                            )
                          }
                        >
                          {IMPORT_COMPARISON_FILTER_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Format
                        <select
                          value={importComparisonHistoryFormat}
                          onChange={(event) =>
                            setImportComparisonHistoryFormat(
                              event.target.value as RenderImportComparisonFormatFilter,
                            )
                          }
                        >
                          {IMPORT_COMPARISON_FORMAT_FILTER_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="renderImportComparisonPinnedToggle">
                        <input
                          checked={showPinnedImportComparisonReports}
                          type="checkbox"
                          onChange={(event) =>
                            setShowPinnedImportComparisonReports(
                              event.target.checked,
                            )
                          }
                        />
                        Pinned only
                      </label>
                      <button
                        className="secondaryButton"
                        type="button"
                        onClick={() => void loadImportComparisonReports()}
                      >
                        <RotateCcw aria-hidden="true" size={16} />
                        Refresh reports
                      </button>
                    </div>
                    {visibleImportComparisonReports.length > 0 ? (
                      <div className="renderImportHistoryRows">
                        {visibleImportComparisonReports.map((report) => (
                          <div
                            className="renderImportHistoryRow"
                            key={report.reportPath}
                          >
                            <div>
                              <strong>
                                {report.format.toUpperCase()} -{" "}
                                {report.differenceCount} differences
                              </strong>
                              <span>
                                {formatImportComparisonReportDate(
                                  report.generatedAt,
                                )}{" "}
                                - {formatImportChangeType(report.changeFilter)}
                                {report.pinned ? " - Pinned" : ""}
                              </span>
                              <small>{report.reportPath}</small>
                            </div>
                            <div className="renderImportHistoryActions">
                              <button
                                className="secondaryButton"
                                type="button"
                                onClick={() =>
                                  void pinImportComparisonReportHistory(
                                    report.reportPath,
                                    !report.pinned,
                                  )
                                }
                              >
                                <Star aria-hidden="true" size={16} />
                                {report.pinned ? "Unpin" : "Pin"}
                              </button>
                              <button
                                className="secondaryButton"
                                type="button"
                                onClick={() =>
                                  void previewImportComparisonReportHistory(
                                    report.reportPath,
                                  )
                                }
                              >
                                Preview
                              </button>
                              <button
                                className="secondaryButton"
                                type="button"
                                onClick={() =>
                                  void copyImportComparisonReportHistoryPath(
                                    report.reportPath,
                                  )
                                }
                              >
                                <Copy aria-hidden="true" size={16} />
                                Copy report
                              </button>
                              <button
                                className="secondaryButton"
                                type="button"
                                onClick={() =>
                                  void openImportComparisonReportHistory(
                                    report.reportPath,
                                  )
                                }
                              >
                                <ExternalLink aria-hidden="true" size={16} />
                                Open
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <small className="renderQueueReportMeta">
                        No comparison reports match this view.
                      </small>
                    )}
                    {importComparisonReportPreview && (
                      <div className="renderImportComparisonPreview">
                        <div className="renderImportDiagnosticsHeader">
                          <strong>
                            Preview{" "}
                            {importComparisonReportPreview.report.format.toUpperCase()}
                          </strong>
                          <span>
                            {importComparisonReportPreview.rows.length} of{" "}
                            {importComparisonReportPreview.totalRows} rows
                          </span>
                        </div>
                        <small>{importComparisonReportPreview.report.reportPath}</small>
                        <div className="renderImportComparisonPreviewActions">
                          <button
                            className="secondaryButton"
                            type="button"
                            onClick={() => void copyImportComparisonPreviewCsv()}
                          >
                            <Copy aria-hidden="true" size={16} />
                            Copy preview CSV
                          </button>
                          <button
                            className="secondaryButton"
                            type="button"
                            onClick={downloadImportComparisonPreviewCsv}
                          >
                            <Download aria-hidden="true" size={16} />
                            Download preview CSV
                          </button>
                          <button
                            className="secondaryButton"
                            type="button"
                            onClick={printImportComparisonPreview}
                          >
                            <Printer aria-hidden="true" size={16} />
                            Print preview
                          </button>
                        </div>
                        <div className="renderImportComparisonPreviewTable">
                          <table>
                            <thead>
                              <tr>
                                {importComparisonReportPreview.columns.map(
                                  (column) => (
                                    <th key={column}>{column}</th>
                                  ),
                                )}
                              </tr>
                            </thead>
                            <tbody>
                              {importComparisonReportPreview.rows.map(
                                (row, index) => (
                                  <tr key={`${row.jobId}-${index}`}>
                                    {importComparisonReportPreview.columns.map(
                                      (column) => (
                                        <td key={column}>{row[column] ?? ""}</td>
                                      ),
                                    )}
                                  </tr>
                                ),
                              )}
                            </tbody>
                          </table>
                        </div>
                        {importComparisonReportPreview.truncated && (
                          <small className="renderQueueReportMeta">
                            Preview is limited to the first rows.
                          </small>
                        )}
                      </div>
                    )}
                  </div>
                  {visibleImportComparisonDifferences.length > 0 ? (
                    <div className="renderImportComparisonRows">
                      {visibleImportComparisonDifferences.map((difference) => (
                        <div
                          className="renderImportComparisonRow"
                          key={difference.jobId}
                        >
                          <strong>{difference.jobId}</strong>
                          <span>{formatImportChangeType(difference.changeType)}</span>
                          <small>{formatImportDetailSnapshot(difference.base)}</small>
                          <small>
                            {formatImportDetailSnapshot(difference.compare)}
                          </small>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <small className="renderQueueReportMeta">
                      No comparison differences match this filter.
                    </small>
                  )}
                </div>
              )}
            </div>
          </div>
          <div className="renderQueueFilters" aria-label="Review filter">
            {REVIEW_FILTER_OPTIONS.map((option) => (
              <button
                className={
                  reviewFilter === option.value
                    ? "queueFilterSegment selected"
                    : "queueFilterSegment"
                }
                key={option.value}
                type="button"
                onClick={() => handleReviewFilterChange(option.value)}
              >
                {option.label}
                <span>{countJobsForReviewFilter(jobs, option.value)}</span>
              </button>
            ))}
          </div>
          <div className="renderQueueTools">
            <label className="queueSearchField">
              Search
              <input
                placeholder="File, status, path"
                type="search"
                value={queueSearch}
                onChange={(event) => handleQueueSearch(event.target.value)}
              />
            </label>
            <label>
              Sort
              <select
                value={queueSort}
                onChange={(event) =>
                  handleQueueSort(event.target.value as RenderQueueSort)
                }
              >
                {QUEUE_SORT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Page size
              <select
                value={queuePageSize}
                onChange={(event) => handleQueuePageSize(Number(event.target.value))}
              >
                {QUEUE_PAGE_SIZES.map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </select>
            </label>
            <div className="renderQueueBulkActions">
              <span>
                {selectedReviewableCount} selected / {visibleReviewableCount} visible
              </span>
              <button
                className="secondaryButton"
                disabled={visibleReviewableCount === 0}
                type="button"
                onClick={selectVisibleReviewableJobs}
              >
                Select visible
              </button>
              <button
                className="secondaryButton"
                disabled={selectedJobIds.size === 0}
                type="button"
                onClick={() => setSelectedJobIds(new Set())}
              >
                Clear
              </button>
              <button
                className="secondaryButton"
                disabled={selectedReviewedCount === 0}
                type="button"
                onClick={() => void clearBulkReview()}
              >
                <RotateCcw aria-hidden="true" size={16} />
                Revert selected
              </button>
              <button
                className="secondaryButton"
                disabled={selectedReviewableCount === 0}
                type="button"
                onClick={() => void saveBulkReview("rejected")}
              >
                <AlertTriangle aria-hidden="true" size={16} />
                Reject selected
              </button>
              <button
                className="primaryButton"
                disabled={selectedReviewableCount === 0}
                type="button"
                onClick={() => void saveBulkReview("accepted")}
              >
                <CheckCircle2 aria-hidden="true" size={16} />
                Accept selected
              </button>
            </div>
          </div>
          <div className="renderQueuePager">
            <span>
              Showing {sortedFilteredJobs.length === 0 ? 0 : pageStart + 1}-{pageEnd} of{" "}
              {sortedFilteredJobs.length}
            </span>
            <div className="renderQueuePagerActions">
              <button
                className="secondaryButton"
                disabled={activeQueuePage <= 1}
                type="button"
                onClick={() => setQueuePage((current) => Math.max(1, current - 1))}
              >
                Previous
              </button>
              <span>
                Page {activeQueuePage} / {pageCount}
              </span>
              <button
                className="secondaryButton"
                disabled={activeQueuePage >= pageCount}
                type="button"
                onClick={() =>
                  setQueuePage((current) => Math.min(pageCount, current + 1))
                }
              >
                Next
              </button>
            </div>
          </div>
          <div className="renderQueueList">
            {pagedJobs.length > 0 ? (
              pagedJobs.map((item) => (
                <div className="queueItemShell" key={item.jobId}>
                  <label className="queueSelect">
                    <input
                      aria-label={`Select ${item.fileName}`}
                      checked={selectedJobIds.has(item.jobId)}
                      disabled={!canReviewJob(item)}
                      type="checkbox"
                      onChange={(event) =>
                        toggleJobSelection(item.jobId, event.target.checked)
                      }
                    />
                  </label>
                  <button
                    className={
                      item.jobId === job?.jobId
                        ? "queueItem selected"
                        : "queueItem"
                    }
                    type="button"
                    onClick={() => {
                      setJob(item);
                      setMessage(messageForJob(item));
                      setIsRendering(
                        ["queued", "preparing", "running", "cancelling"].includes(
                          item.status,
                        ),
                      );
                    }}
                  >
                    <strong>{item.fileName}</strong>
                    <span>{item.status}</span>
                    <small>
                      {item.progressPercent.toFixed(1)}% {formatQueueSettings(item)}{" "}
                      {formatQueueReview(item)}
                    </small>
                  </button>
                </div>
              ))
            ) : (
              <p className="timelineMessage">No render jobs match this queue view.</p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function parentPath(path: string): string {
  const index = Math.max(path.lastIndexOf("\\"), path.lastIndexOf("/"));
  return index > 0 ? path.slice(0, index) : path;
}

function fileUriFromPath(path: string | null): string | null {
  if (!path) return null;
  if (path.startsWith("file://")) return path;
  if (path.startsWith("\\\\")) {
    return `file:${encodeFilePath(path.replace(/\\/g, "/"))}`;
  }
  const normalized = path.replace(/\\/g, "/");
  if (/^[A-Za-z]:\//.test(normalized)) {
    return `file:///${encodeFilePath(normalized)}`;
  }
  if (normalized.startsWith("/")) {
    return `file://${encodeFilePath(normalized)}`;
  }
  return null;
}

function encodeFilePath(path: string): string {
  return encodeURI(path).replace(/#/g, "%23").replace(/\?/g, "%3F");
}

function preflightGroups(
  report: RenderPreflightReport | null,
): RenderPreflightGroup[] {
  if (report) return report.groups;
  return ["Tool", "Timeline", "Media", "Output"].map((group) => ({
    group,
    status: "skipped",
    checks: [
      {
        code: `${group.toUpperCase()}_PENDING`,
        message: "Waiting for preflight check.",
        status: "skipped",
      },
    ],
  }));
}

function preflightFailureReport(message: string): RenderPreflightReport {
  return {
    ready: false,
    outputFileName: null,
    durationMilliseconds: null,
    groups: [
      {
        group: "Tool",
        status: "failed",
        checks: [{ code: "PREFLIGHT_UNAVAILABLE", message, status: "failed" }],
      },
      ...["Timeline", "Media", "Output"].map((group) => ({
        group,
        status: "skipped" as const,
        checks: [
          {
            code: `${group.toUpperCase()}_SKIPPED`,
            message: "Preflight service is unavailable.",
            status: "skipped" as const,
          },
        ],
      })),
    ],
  };
}

function guideForPreflight(report: RenderPreflightReport | null) {
  if (!report || report.ready) return null;
  const failedGroup = report.groups.find((group) => group.status === "failed");
  if (!failedGroup) return null;
  if (failedGroup.group === "Tool") {
    return {
      actionLabel: "Open Settings",
      message: "FFmpeg or FFprobe is missing. Open Settings for setup hints, then run preflight again.",
      title: "Render tools need setup",
      to: "/settings",
    };
  }
  if (failedGroup.group === "Timeline") {
    return {
      actionLabel: "Open Timeline",
      message: "Render needs a valid timeline with duration and layers. Generate or fix the timeline before queueing MP4 output.",
      title: "Timeline needed before render",
      to: "/timeline",
    };
  }
  if (failedGroup.group === "Media") {
    return {
      actionLabel: "Open Media",
      message: "One or more timeline media assets are missing. Search, download, or reassign media before rendering.",
      title: "Media needs attention",
      to: "/media",
    };
  }
  return {
    actionLabel: "Open Project",
    message: "Render output cannot be written yet. Check the active project and output location.",
    title: "Output needs attention",
    to: "/projects",
  };
}

function iconForPreflight(status: RenderPreflightGroup["status"]) {
  if (status === "passed") return <CheckCircle2 aria-hidden="true" size={16} />;
  if (status === "failed") return <AlertTriangle aria-hidden="true" size={16} />;
  return <CircleDashed aria-hidden="true" size={16} />;
}

function labelForPreflight(status: RenderPreflightGroup["status"]): string {
  if (status === "passed") return "Ready";
  if (status === "failed") return "Needs fix";
  return "Pending";
}

function preflightActionLabel(group: string): string {
  if (group === "Tool") return "Setup hint";
  if (group === "Timeline") return "Open Timeline";
  if (group === "Media") return "Open media picker";
  if (group === "Output") return "Open Project";
  return "Fix";
}

function messageForJob(job: RenderJob): string {
  if (job.status === "completed") return "Render completed";
  if (job.status === "cancelled") return "Render cancelled";
  if (job.status === "failed") return job.errorMessage ?? "Render failed";
  if (job.status === "interrupted") return "Render interrupted";
  if (job.status === "cancelling") return "Cancelling render...";
  if (job.status === "preparing") return "Preparing subtitles...";
  if (job.status === "queued") return "Render queued";
  return `Rendering ${job.progressPercent.toFixed(1)}%`;
}

function formatExportSettings(settings: RenderExportSettings): string {
  const profile = settings.profileId === "custom" ? "Custom" : profileLabel(settings.profileId);
  return `${profile}, ${settings.width}x${settings.height}, ${settings.frameRate} FPS, CRF ${settings.crf}, ${settings.encoderPreset}, ${settings.audioBitrateKbps} kbps`;
}

function formatQueueSettings(job: RenderJob): string {
  return job.exportSettings
    ? `${profileLabel(job.exportSettings.profileId)} ${job.exportSettings.width}x${job.exportSettings.height}`
    : "";
}

function formatQueueReview(job: RenderJob): string {
  if (!job.review) return "";
  return job.review.status === "accepted" ? "Accepted" : "Rejected";
}

function canReviewJob(job: RenderJob): boolean {
  return job.status === "completed" && Boolean(job.outputPath);
}

function canClearReviewJob(job: RenderJob): boolean {
  return canReviewJob(job) && Boolean(job.review);
}

function matchesReviewFilter(
  job: RenderJob,
  filter: RenderReviewFilter,
): boolean {
  if (filter === "all") return true;
  if (filter === "not_reviewed") return !job.review;
  return job.review?.status === filter;
}

function countJobsForReviewFilter(
  jobs: RenderJob[],
  filter: RenderReviewFilter,
): number {
  return jobs.filter((item) => matchesReviewFilter(item, filter)).length;
}

function summarizeRenderQueue(jobs: RenderJob[]): RenderQueueSummary {
  return {
    total: jobs.length,
    accepted: jobs.filter((item) => item.review?.status === "accepted").length,
    rejected: jobs.filter((item) => item.review?.status === "rejected").length,
    notReviewed: jobs.filter((item) => !item.review).length,
    completed: jobs.filter((item) => item.status === "completed").length,
    failed: jobs.filter((item) => item.status === "failed").length,
    queued: jobs.filter((item) => item.status === "queued").length,
    preparing: jobs.filter((item) => item.status === "preparing").length,
    running: jobs.filter((item) => item.status === "running").length,
    cancelling: jobs.filter((item) => item.status === "cancelling").length,
    cancelled: jobs.filter((item) => item.status === "cancelled").length,
    interrupted: jobs.filter((item) => item.status === "interrupted").length,
  };
}

function formatReportFilters(report: RenderQueueReport): string {
  return [
    `Review ${labelForReportReview(report.filters.reviewStatus)}`,
    `Status ${labelForReportStatus(report.filters.jobStatus)}`,
    `Date ${formatReportDateRange(report.filters.dateFrom, report.filters.dateTo)}`,
  ].join(", ");
}

function labelForReportReview(filter: RenderQueueReportReviewFilter): string {
  return (
    REVIEW_FILTER_OPTIONS.find((option) => option.value === filter)?.label ?? filter
  );
}

function labelForReportStatus(filter: RenderQueueReportJobStatusFilter): string {
  return (
    REPORT_STATUS_OPTIONS.find((option) => option.value === filter)?.label ??
    filter
  );
}

function formatReportDateRange(
  dateFrom: string | null,
  dateTo: string | null,
): string {
  if (dateFrom && dateTo) return `${dateFrom} to ${dateTo}`;
  if (dateFrom) return `from ${dateFrom}`;
  if (dateTo) return `until ${dateTo}`;
  return "All dates";
}

function formatImportDecision(decision: string | null): string {
  if (decision === "accepted") return "Accepted";
  if (decision === "rejected") return "Rejected";
  if (decision === "not_reviewed") return "Not reviewed";
  return decision || "No decision";
}

function formatImportStatus(status: string): string {
  if (status === "applied") return "Applied";
  if (status === "skipped") return "Skipped";
  return status;
}

function formatImportReportDate(importedAt: string | null): string {
  if (!importedAt) return "Unknown import time";
  return importedAt;
}

function formatImportComparisonReportDate(generatedAt: string | null): string {
  if (!generatedAt) return "Unknown report time";
  return generatedAt;
}

function formatImportReportOption(report: RenderBundleImportReportSummary): string {
  return `${formatImportReportDate(report.importedAt)} (${report.applied} applied, ${report.skipped} skipped)`;
}

function formatImportChangeType(changeType: string): string {
  if (changeType === "added") return "Added";
  if (changeType === "removed") return "Removed";
  if (changeType === "changed") return "Changed";
  return changeType;
}

function formatImportDetailSnapshot(
  detail: RenderBundleImportReportDetailSnapshot | null,
): string {
  if (!detail) return "Not present in this report.";
  return [
    `Status ${detail.status ? formatImportStatus(detail.status) : "None"}`,
    `Decision ${formatImportDecision(detail.decision)}`,
    `Reason ${detail.reason ?? "None"}`,
  ].join(", ");
}

function filteredImportReportDifferences(
  comparison: RenderBundleImportReportComparison,
  filter: RenderImportComparisonFilter,
): RenderBundleImportReportDifference[] {
  if (filter === "all") return comparison.differences;
  return comparison.differences.filter(
    (difference) => difference.changeType === filter,
  );
}

function filterImportComparisonReports(
  reports: RenderBundleImportComparisonReportSummary[],
  search: string,
  changeFilter: RenderImportComparisonFilter,
  formatFilter: RenderImportComparisonFormatFilter,
  pinnedOnly: boolean,
): RenderBundleImportComparisonReportSummary[] {
  const normalized = search.trim().toLowerCase();
  return reports.filter((report) => {
    if (pinnedOnly && !report.pinned) {
      return false;
    }
    if (changeFilter !== "all" && report.changeFilter !== changeFilter) {
      return false;
    }
    if (formatFilter !== "all" && report.format !== formatFilter) {
      return false;
    }
    if (!normalized) return true;
    return importComparisonReportSearchText(report).includes(normalized);
  });
}

function importComparisonReportSearchText(
  report: RenderBundleImportComparisonReportSummary,
): string {
  return [
    report.reportPath,
    report.format,
    report.generatedAt,
    report.changeFilter,
    report.pinned ? "pinned" : "not pinned",
    report.baseReportPath ?? "",
    report.compareReportPath ?? "",
  ]
    .join(" ")
    .toLowerCase();
}

function importDiagnosticDetails(
  result: RenderBundleReviewImportResult,
  filter: RenderImportDiagnosticsFilter,
): RenderBundleReviewImportDetail[] {
  if (filter === "all") return result.details;
  return result.details.filter((detail) => detail.status === filter);
}

function importDiagnosticsCsv(
  details: RenderBundleReviewImportDetail[],
): string {
  const rows = details.map((detail) =>
    [
      detail.jobId ?? "",
      detail.status,
      detail.decision ?? "",
      detail.reason ?? "",
    ]
      .map(csvCell)
      .join(","),
  );
  return ["jobId,status,decision,reason", ...rows].join("\n");
}

function importComparisonPreviewCsv(
  preview: RenderBundleImportComparisonReportPreview,
): string {
  const rows = preview.rows.map((row) =>
    preview.columns.map((column) => csvCell(row[column] ?? "")).join(","),
  );
  return [preview.columns.join(","), ...rows].join("\n");
}

function importComparisonPreviewFileName(
  preview: RenderBundleImportComparisonReportPreview,
): string {
  const sourceName = preview.report.reportPath
    .replace(/\\/g, "/")
    .split("/")
    .pop()
    ?.replace(/\.(csv|json)$/i, "");
  return `${sourceName || "render-import-comparison-preview"}-preview.csv`;
}

function csvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

function downloadTextFile(
  fileName: string,
  content: string,
  type: string,
): void {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

function filterRenderJobsBySearch(jobs: RenderJob[], search: string): RenderJob[] {
  const normalized = search.trim().toLowerCase();
  if (!normalized) return jobs;
  return jobs.filter((job) => renderJobSearchText(job).includes(normalized));
}

function renderJobSearchText(job: RenderJob): string {
  return [
    job.fileName,
    job.status,
    job.outputPath ?? "",
    job.errorMessage ?? "",
    formatQueueReview(job),
    job.exportSettings ? formatExportSettings(job.exportSettings) : "",
  ]
    .join(" ")
    .toLowerCase();
}

function latestMatchingJob(
  jobs: RenderJob[],
  filter: RenderReviewFilter,
): RenderJob | null {
  for (let index = jobs.length - 1; index >= 0; index -= 1) {
    if (matchesReviewFilter(jobs[index], filter)) return jobs[index];
  }
  return null;
}

function requestedReviewJob(jobs: RenderJob[], search: string): RenderJob | null {
  const jobId = new URLSearchParams(search).get("reviewJob");
  if (!jobId) return null;
  return jobs.find((job) => job.jobId === jobId) ?? null;
}

function sortRenderJobs(jobs: RenderJob[], sort: RenderQueueSort): RenderJob[] {
  const indexed = jobs.map((job, index) => ({ job, index }));
  if (sort === "newest") {
    return indexed.sort((left, right) => right.index - left.index).map(({ job }) => job);
  }
  if (sort === "oldest") {
    return indexed.sort((left, right) => left.index - right.index).map(({ job }) => job);
  }
  return indexed
    .sort((left, right) => {
      const statusDiff = statusSortRank(left.job) - statusSortRank(right.job);
      if (statusDiff !== 0) return statusDiff;
      return left.job.fileName.localeCompare(right.job.fileName);
    })
    .map(({ job }) => job);
}

function statusSortRank(job: RenderJob): number {
  if (job.status === "running") return 0;
  if (job.status === "preparing") return 1;
  if (job.status === "queued") return 2;
  if (job.status === "cancelling") return 3;
  if (job.status === "failed") return 4;
  if (job.status === "interrupted") return 5;
  if (job.status === "completed" && !job.review) return 6;
  if (job.review?.status === "rejected") return 7;
  if (job.review?.status === "accepted") return 8;
  if (job.status === "completed") return 9;
  return 10;
}

function formatReviewStatus(job: RenderJob): string {
  if (!job.review) return "Not reviewed";
  return job.review.status === "accepted" ? "Accepted" : "Rejected";
}

function formatReviewedAt(job: RenderJob): string {
  if (!job.review) return "Mark this output after review";
  const date = new Date(job.review.reviewedAt);
  if (Number.isNaN(date.getTime())) return "Review saved";
  return `Review saved ${date.toLocaleString()}`;
}

function formatPreviewMetadata(job: RenderJob): string {
  const preview = job.preview;
  if (!preview) return "Preview pending";
  return `${preview.width}x${preview.height}, ${preview.frameRate} FPS, ${formatDuration(preview.durationMilliseconds)}, ${formatBytes(preview.sizeBytes)}`;
}

function formatPreviewGeneratedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Preview metadata saved";
  return `Preview saved ${date.toLocaleString()}`;
}

function formatCommandSummary(job: RenderJob): string {
  const summary = job.diagnostics?.commandSummary;
  if (!summary || summary.commandAvailable === false) return "Unavailable";
  const executable = String(summary.executable ?? "ffmpeg");
  const inputs = Number(summary.inputCount ?? 0);
  const codec = String(summary.videoCodec ?? "video");
  const preset = String(summary.encoderPreset ?? "");
  return `${executable}, ${inputs} input${inputs === 1 ? "" : "s"}, ${codec} ${preset}`.trim();
}

function formatRenderMetrics(job: RenderJob): string {
  const metrics = job.diagnostics?.metrics;
  if (!metrics) return "Pending";
  const elapsed = typeof metrics.elapsedMilliseconds === "number"
    ? `${(metrics.elapsedMilliseconds / 1000).toFixed(1)}s`
    : "pending";
  const returnCode = metrics.returnCode === null ? "n/a" : String(metrics.returnCode);
  return `${elapsed}, return ${returnCode}, ${job.progressPercent.toFixed(1)}%`;
}

function profileLabel(profileId: RenderExportSettings["profileId"]): string {
  if (profileId === "high_quality") return "High Quality";
  if (profileId === "fast_preview") return "Fast Preview";
  if (profileId === "draft") return "Draft";
  if (profileId === "archive") return "Archive";
  if (profileId === "standard") return "Standard";
  return "Custom";
}

function formatDuration(milliseconds: number): string {
  const seconds = Math.round(milliseconds / 1000);
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
