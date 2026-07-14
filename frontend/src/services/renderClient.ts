interface ApiResponse<TData> {
  success: boolean;
  data: TData | null;
  message: string;
  error: { code: string; message: string } | null;
}

export interface RenderResult {
  outputPath: string;
  durationMilliseconds: number;
  sizeBytes: number;
}

export type RenderProfileId =
  | "fast_preview"
  | "draft"
  | "standard"
  | "high_quality"
  | "archive";

export interface RenderExportSettings {
  profileId: RenderProfileId | "custom";
  width: number;
  height: number;
  frameRate: number;
  crf: number;
  encoderPreset:
    | "ultrafast"
    | "superfast"
    | "veryfast"
    | "faster"
    | "fast"
    | "medium"
    | "slow"
    | "slower"
    | "veryslow";
  audioBitrateKbps: number;
}

export interface StartRenderRequest
  extends Omit<RenderExportSettings, "profileId"> {
  profileId: RenderProfileId;
  fileName?: string | null;
  outputNameTemplate: string;
}

export interface RenderProfile {
  profileId: RenderProfileId;
  name: string;
  settings: RenderExportSettings;
}

export interface RenderProfileList {
  profiles: RenderProfile[];
}

export type RenderPreflightStatus = "passed" | "failed" | "skipped";

export interface RenderPreflightCheck {
  code: string;
  message: string;
  status: RenderPreflightStatus;
}

export interface RenderPreflightGroup {
  group: "Tool" | "Timeline" | "Media" | "Output" | string;
  status: RenderPreflightStatus;
  checks: RenderPreflightCheck[];
}

export interface RenderPreflightReport {
  ready: boolean;
  groups: RenderPreflightGroup[];
  outputFileName: string | null;
  durationMilliseconds: number | null;
}

export interface RenderDiagnostics {
  commandSummary: Record<string, string | number | boolean | null>;
  settingsSnapshot: Record<string, string | number | boolean | null>;
  metrics: Record<string, string | number | boolean | null>;
  stderrTail: string | null;
}

export interface RenderOutputPreview {
  thumbnailPath: string | null;
  thumbnailUri: string | null;
  durationMilliseconds: number;
  sizeBytes: number;
  width: number;
  height: number;
  frameRate: number;
  generatedAt: string;
  status: "available" | "thumbnail_unavailable" | string;
  errorMessage: string | null;
}

export type RenderReviewStatus = "accepted" | "rejected";

export interface RenderReview {
  status: RenderReviewStatus;
  note: string | null;
  reviewedAt: string;
}

export type RenderJobStatus =
  | "queued"
  | "preparing"
  | "running"
  | "cancelling"
  | "completed"
  | "cancelled"
  | "failed"
  | "interrupted";

export interface RenderJob {
  jobId: string;
  projectId: string;
  fileName: string;
  status: RenderJobStatus;
  progressPercent: number;
  processedMilliseconds: number;
  durationMilliseconds: number;
  outputPath: string | null;
  sizeBytes: number | null;
  errorCode: string | null;
  errorMessage: string | null;
  exportSettings: RenderExportSettings | null;
  outputNameTemplate: string | null;
  diagnostics: RenderDiagnostics | null;
  preview: RenderOutputPreview | null;
  review: RenderReview | null;
}

export interface RenderJobQueue {
  jobs: RenderJob[];
}

export type RenderQueueReportFormat = "csv" | "json";
export type RenderQueueReportReviewFilter =
  | "all"
  | "accepted"
  | "rejected"
  | "not_reviewed";
export type RenderQueueReportJobStatusFilter = "all" | RenderJobStatus;

export interface RenderQueueReport {
  format: RenderQueueReportFormat;
  reportPath: string;
  jobCount: number;
  generatedAt: string;
  summary: {
    total: number;
    accepted: number;
    rejected: number;
    notReviewed: number;
    completed: number;
    failed: number;
  };
  filters: {
    reviewStatus: RenderQueueReportReviewFilter;
    jobStatus: RenderQueueReportJobStatusFilter;
    dateFrom: string | null;
    dateTo: string | null;
  };
}

export interface RenderQueueHandoffBundle {
  bundlePath: string;
  archivePath: string;
  manifestPath: string;
  csvReportPath: string;
  jsonReportPath: string;
  jobCount: number;
  thumbnailCount: number;
  generatedAt: string;
  summary: RenderQueueReport["summary"];
  filters: RenderQueueReport["filters"];
}

export interface RenderBundleReviewImportDetail {
  jobId: string | null;
  status: "applied" | "skipped" | string;
  decision: RenderReviewStatus | string | null;
  reason: string | null;
}

export interface RenderBundleReviewImportResult {
  manifestPath: string;
  reportPath: string;
  applied: number;
  skipped: number;
  accepted: number;
  rejected: number;
  details: RenderBundleReviewImportDetail[];
}

export interface RenderBundleImportReportSummary {
  reportPath: string;
  importedAt: string | null;
  manifestPath: string | null;
  sourceBundlePath: string | null;
  sourceGeneratedAt: string | null;
  applied: number;
  skipped: number;
  accepted: number;
  rejected: number;
  detailCount: number;
}

export interface RenderBundleImportReportList {
  reports: RenderBundleImportReportSummary[];
}

export interface RenderBundleImportReportDetailSnapshot {
  jobId: string | null;
  status: string | null;
  decision: string | null;
  reason: string | null;
}

export interface RenderBundleImportReportDifference {
  jobId: string;
  changeType: "added" | "removed" | "changed" | string;
  base: RenderBundleImportReportDetailSnapshot | null;
  compare: RenderBundleImportReportDetailSnapshot | null;
}

export interface RenderBundleImportReportComparison {
  baseReport: RenderBundleImportReportSummary;
  compareReport: RenderBundleImportReportSummary;
  differenceCount: number;
  differences: RenderBundleImportReportDifference[];
}

export type RenderBundleImportComparisonReportFormat = "csv" | "json";
export type RenderBundleImportComparisonChangeFilter =
  | "all"
  | "changed"
  | "added"
  | "removed";

export interface RenderBundleImportComparisonReport {
  format: RenderBundleImportComparisonReportFormat;
  reportPath: string;
  generatedAt: string;
  changeFilter: RenderBundleImportComparisonChangeFilter;
  differenceCount: number;
  baseReport: Partial<RenderBundleImportReportSummary>;
  compareReport: Partial<RenderBundleImportReportSummary>;
}

export interface RenderBundleImportComparisonReportSummary {
  reportPath: string;
  format: RenderBundleImportComparisonReportFormat;
  generatedAt: string;
  changeFilter: RenderBundleImportComparisonChangeFilter;
  differenceCount: number;
  baseReportPath: string | null;
  compareReportPath: string | null;
  pinned: boolean;
}

export interface RenderBundleImportComparisonReportList {
  reports: RenderBundleImportComparisonReportSummary[];
}

export interface RenderBundleImportComparisonReportPreview {
  report: RenderBundleImportComparisonReportSummary;
  columns: string[];
  rows: Record<string, string>[];
  totalRows: number;
  truncated: boolean;
}

export interface RenderBundleImportComparisonReportPinResult {
  reportPath: string;
  pinned: boolean;
  pinnedCount: number;
}

export class RenderApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8765";

export async function renderTimeline(request: StartRenderRequest): Promise<RenderResult> {
  const response = await fetch(`${apiBaseUrl}/api/render`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  const payload = (await response.json()) as ApiResponse<RenderResult>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new RenderApiError(
      payload.error?.code ?? "RENDER_REQUEST_FAILED",
      payload.error?.message ?? `Render request failed: ${response.status}`,
    );
  }
  return payload.data;
}

export function listRenderProfiles(): Promise<RenderProfileList> {
  return requestRenderProfiles("/profiles", { method: "GET" });
}

export function startRenderJob(request: StartRenderRequest): Promise<RenderJob> {
  return requestRenderJob("/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function checkRenderPreflight(
  request: StartRenderRequest,
): Promise<RenderPreflightReport> {
  return requestRenderPreflight("/preflight", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

async function requestRenderProfiles(
  path: string,
  init: RequestInit,
): Promise<RenderProfileList> {
  const response = await fetch(`${apiBaseUrl}/api/render${path}`, init);
  const payload = (await response.json()) as ApiResponse<RenderProfileList>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new RenderApiError(
      payload.error?.code ?? "RENDER_REQUEST_FAILED",
      payload.error?.message ?? `Render request failed: ${response.status}`,
    );
  }
  return payload.data;
}

async function requestRenderPreflight(
  path: string,
  init: RequestInit,
): Promise<RenderPreflightReport> {
  const response = await fetch(`${apiBaseUrl}/api/render${path}`, init);
  const payload = (await response.json()) as ApiResponse<RenderPreflightReport>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new RenderApiError(
      payload.error?.code ?? "RENDER_REQUEST_FAILED",
      payload.error?.message ?? `Render request failed: ${response.status}`,
    );
  }
  return payload.data;
}

export function getRenderJob(jobId: string): Promise<RenderJob> {
  return requestRenderJob(`/jobs/${encodeURIComponent(jobId)}`, {
    method: "GET",
  });
}

export function listRenderJobs(): Promise<RenderJobQueue> {
  return requestRenderQueue("/jobs", { method: "GET" });
}

export function cancelRenderJob(jobId: string): Promise<RenderJob> {
  return requestRenderJob(`/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
  });
}

export function resumeRenderJob(jobId: string): Promise<RenderJob> {
  return requestRenderJob(`/jobs/${encodeURIComponent(jobId)}/resume`, {
    method: "POST",
  });
}

export function retryRenderJob(jobId: string): Promise<RenderJob> {
  return requestRenderJob(`/jobs/${encodeURIComponent(jobId)}/retry`, {
    method: "POST",
  });
}

export function reviewRenderJob(
  jobId: string,
  status: RenderReviewStatus,
  note: string | null,
): Promise<RenderJob> {
  return requestRenderJob(`/jobs/${encodeURIComponent(jobId)}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, note }),
  });
}

export function clearRenderJobReview(jobId: string): Promise<RenderJob> {
  return requestRenderJob(`/jobs/${encodeURIComponent(jobId)}/review`, {
    method: "DELETE",
  });
}

export function cleanupRenderJobs(keepCount = 100): Promise<RenderJobQueue> {
  return requestRenderQueue("/jobs/cleanup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keepCount }),
  });
}

export function exportRenderQueueReport(
  format: RenderQueueReportFormat,
  reviewStatus: RenderQueueReportReviewFilter = "all",
  jobStatus: RenderQueueReportJobStatusFilter = "all",
  dateFrom: string | null = null,
  dateTo: string | null = null,
): Promise<RenderQueueReport> {
  return requestRenderReport("/jobs/report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ format, reviewStatus, jobStatus, dateFrom, dateTo }),
  });
}

export function exportRenderQueueHandoffBundle(
  reviewStatus: RenderQueueReportReviewFilter = "all",
  jobStatus: RenderQueueReportJobStatusFilter = "all",
  dateFrom: string | null = null,
  dateTo: string | null = null,
): Promise<RenderQueueHandoffBundle> {
  return requestRenderBundle("/jobs/report/bundle", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      format: "json",
      reviewStatus,
      jobStatus,
      dateFrom,
      dateTo,
    }),
  });
}

export function importRenderBundleReviews(
  manifestPath: string,
): Promise<RenderBundleReviewImportResult> {
  return requestRenderBundleReviewImport("/jobs/report/bundle/import-review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ manifestPath }),
  });
}

export function listRenderBundleImportReports(): Promise<RenderBundleImportReportList> {
  return requestRenderBundleImportReports("/jobs/report/bundle/imports", {
    method: "GET",
  });
}

export function compareRenderBundleImportReports(
  baseReportPath: string,
  compareReportPath: string,
): Promise<RenderBundleImportReportComparison> {
  return requestRenderBundleImportReportComparison(
    "/jobs/report/bundle/imports/compare",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ baseReportPath, compareReportPath }),
    },
  );
}

export function exportRenderBundleImportComparisonReport(
  baseReportPath: string,
  compareReportPath: string,
  format: RenderBundleImportComparisonReportFormat,
  changeFilter: RenderBundleImportComparisonChangeFilter,
): Promise<RenderBundleImportComparisonReport> {
  return requestRenderBundleImportComparisonReport(
    "/jobs/report/bundle/imports/compare/report",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        baseReportPath,
        compareReportPath,
        format,
        changeFilter,
      }),
    },
  );
}

export function listRenderBundleImportComparisonReports(): Promise<RenderBundleImportComparisonReportList> {
  return requestRenderBundleImportComparisonReports(
    "/jobs/report/bundle/imports/compare/reports",
    { method: "GET" },
  );
}

export function previewRenderBundleImportComparisonReport(
  reportPath: string,
  maxRows = 25,
): Promise<RenderBundleImportComparisonReportPreview> {
  return requestRenderBundleImportComparisonReportPreview(
    "/jobs/report/bundle/imports/compare/reports/preview",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reportPath, maxRows }),
    },
  );
}

export function pinRenderBundleImportComparisonReport(
  reportPath: string,
  pinned: boolean,
): Promise<RenderBundleImportComparisonReportPinResult> {
  return requestRenderBundleImportComparisonReportPin(
    "/jobs/report/bundle/imports/compare/reports/pin",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reportPath, pinned }),
    },
  );
}

async function requestRenderJob(
  path: string,
  init: RequestInit,
): Promise<RenderJob> {
  const response = await fetch(`${apiBaseUrl}/api/render${path}`, init);
  const payload = (await response.json()) as ApiResponse<RenderJob>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new RenderApiError(
      payload.error?.code ?? "RENDER_REQUEST_FAILED",
      payload.error?.message ?? `Render request failed: ${response.status}`,
    );
  }
  return payload.data;
}

async function requestRenderReport(
  path: string,
  init: RequestInit,
): Promise<RenderQueueReport> {
  const response = await fetch(`${apiBaseUrl}/api/render${path}`, init);
  const payload = (await response.json()) as ApiResponse<RenderQueueReport>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new RenderApiError(
      payload.error?.code ?? "RENDER_REQUEST_FAILED",
      payload.error?.message ?? `Render request failed: ${response.status}`,
    );
  }
  return payload.data;
}

async function requestRenderBundle(
  path: string,
  init: RequestInit,
): Promise<RenderQueueHandoffBundle> {
  const response = await fetch(`${apiBaseUrl}/api/render${path}`, init);
  const payload = (await response.json()) as ApiResponse<RenderQueueHandoffBundle>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new RenderApiError(
      payload.error?.code ?? "RENDER_REQUEST_FAILED",
      payload.error?.message ?? `Render request failed: ${response.status}`,
    );
  }
  return payload.data;
}

async function requestRenderBundleReviewImport(
  path: string,
  init: RequestInit,
): Promise<RenderBundleReviewImportResult> {
  const response = await fetch(`${apiBaseUrl}/api/render${path}`, init);
  const payload =
    (await response.json()) as ApiResponse<RenderBundleReviewImportResult>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new RenderApiError(
      payload.error?.code ?? "RENDER_REQUEST_FAILED",
      payload.error?.message ?? `Render request failed: ${response.status}`,
    );
  }
  return payload.data;
}

async function requestRenderBundleImportReports(
  path: string,
  init: RequestInit,
): Promise<RenderBundleImportReportList> {
  const response = await fetch(`${apiBaseUrl}/api/render${path}`, init);
  const payload =
    (await response.json()) as ApiResponse<RenderBundleImportReportList>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new RenderApiError(
      payload.error?.code ?? "RENDER_REQUEST_FAILED",
      payload.error?.message ?? `Render request failed: ${response.status}`,
    );
  }
  return payload.data;
}

async function requestRenderBundleImportReportComparison(
  path: string,
  init: RequestInit,
): Promise<RenderBundleImportReportComparison> {
  const response = await fetch(`${apiBaseUrl}/api/render${path}`, init);
  const payload =
    (await response.json()) as ApiResponse<RenderBundleImportReportComparison>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new RenderApiError(
      payload.error?.code ?? "RENDER_REQUEST_FAILED",
      payload.error?.message ?? `Render request failed: ${response.status}`,
    );
  }
  return payload.data;
}

async function requestRenderBundleImportComparisonReport(
  path: string,
  init: RequestInit,
): Promise<RenderBundleImportComparisonReport> {
  const response = await fetch(`${apiBaseUrl}/api/render${path}`, init);
  const payload =
    (await response.json()) as ApiResponse<RenderBundleImportComparisonReport>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new RenderApiError(
      payload.error?.code ?? "RENDER_REQUEST_FAILED",
      payload.error?.message ?? `Render request failed: ${response.status}`,
    );
  }
  return payload.data;
}

async function requestRenderBundleImportComparisonReports(
  path: string,
  init: RequestInit,
): Promise<RenderBundleImportComparisonReportList> {
  const response = await fetch(`${apiBaseUrl}/api/render${path}`, init);
  const payload =
    (await response.json()) as ApiResponse<RenderBundleImportComparisonReportList>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new RenderApiError(
      payload.error?.code ?? "RENDER_REQUEST_FAILED",
      payload.error?.message ?? `Render request failed: ${response.status}`,
    );
  }
  return payload.data;
}

async function requestRenderBundleImportComparisonReportPreview(
  path: string,
  init: RequestInit,
): Promise<RenderBundleImportComparisonReportPreview> {
  const response = await fetch(`${apiBaseUrl}/api/render${path}`, init);
  const payload =
    (await response.json()) as ApiResponse<RenderBundleImportComparisonReportPreview>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new RenderApiError(
      payload.error?.code ?? "RENDER_REQUEST_FAILED",
      payload.error?.message ?? `Render request failed: ${response.status}`,
    );
  }
  return payload.data;
}

async function requestRenderBundleImportComparisonReportPin(
  path: string,
  init: RequestInit,
): Promise<RenderBundleImportComparisonReportPinResult> {
  const response = await fetch(`${apiBaseUrl}/api/render${path}`, init);
  const payload =
    (await response.json()) as ApiResponse<RenderBundleImportComparisonReportPinResult>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new RenderApiError(
      payload.error?.code ?? "RENDER_REQUEST_FAILED",
      payload.error?.message ?? `Render request failed: ${response.status}`,
    );
  }
  return payload.data;
}

async function requestRenderQueue(
  path: string,
  init: RequestInit,
): Promise<RenderJobQueue> {
  const response = await fetch(`${apiBaseUrl}/api/render${path}`, init);
  const payload = (await response.json()) as ApiResponse<RenderJobQueue>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new RenderApiError(
      payload.error?.code ?? "RENDER_REQUEST_FAILED",
      payload.error?.message ?? `Render request failed: ${response.status}`,
    );
  }
  return payload.data;
}
