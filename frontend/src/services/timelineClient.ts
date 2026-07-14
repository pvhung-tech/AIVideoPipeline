export type TimelineMediaType = "image" | "video" | "audio";
export type VisualClipRole = "broll" | "avatar";

export interface MediaClip {
  id: string;
  contentHash: string;
  mediaType: TimelineMediaType;
  startMilliseconds: number;
  endMilliseconds: number;
  layer: number;
  sourceStartMilliseconds: number | null;
  sourceEndMilliseconds: number | null;
  role: VisualClipRole;
}

export interface AudioClip {
  id: string;
  contentHash: string;
  startMilliseconds: number;
  endMilliseconds: number;
  sourceStartMilliseconds: number;
  sourceEndMilliseconds: number;
  volume: number;
  loop: boolean;
  layer: number;
}

export interface SubtitleClip {
  id: string;
  text: string;
  startMilliseconds: number;
  endMilliseconds: number;
  layer: number;
}

export interface TimelineScene {
  sceneId: string;
  order: number;
  startMilliseconds: number;
  endMilliseconds: number;
  mediaClips: MediaClip[];
  subtitleClips: SubtitleClip[];
}

export interface Timeline {
  schemaVersion: number;
  id: string;
  createdAt: string;
  updatedAt: string;
  durationMilliseconds: number;
  scenes: TimelineScene[];
  audioClips: AudioClip[];
}

export interface TimelineMediaAsset {
  contentHash: string;
  mediaType: TimelineMediaType;
  fileName: string;
  uri: string;
  sizeBytes: number;
  providerIds: string[];
  durationMilliseconds: number | null;
}

export interface TimelineMediaAssetPage {
  assets: TimelineMediaAsset[];
  offset: number;
  limit: number | null;
  totalEntries: number;
  hasMore: boolean;
}

interface ApiResponse<TData> {
  success: boolean;
  data: TData | null;
  message: string;
  error: { code: string; message: string } | null;
}

export class TimelineApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8765";

export type MetadataBackfillStatus =
  | "queued"
  | "running"
  | "completed"
  | "cancelled"
  | "failed";

export interface MetadataBackfillJob {
  jobId: string;
  projectId: string;
  status: MetadataBackfillStatus;
  totalVideos: number;
  processedVideos: number;
  progressPercent: number;
  updatedVideos: number;
  skippedVideos: number;
  failedCount: number;
  failedContentHashes: string[];
  errorMessage: string | null;
}

export async function backfillVideoMetadata(): Promise<MetadataBackfillJob> {
  return requestBackfill("", { method: "POST" });
}

export async function getVideoMetadataBackfillStatus(): Promise<MetadataBackfillJob | null> {
  const response = await fetch(`${apiBaseUrl}/api/media/cache/metadata/backfill/status`);
  const payload = (await response.json()) as ApiResponse<MetadataBackfillJob>;
  if (!response.ok || !payload.success) {
    throw new TimelineApiError(payload.error?.code ?? "METADATA_BACKFILL_FAILED", payload.error?.message ?? "Metadata backfill status failed");
  }
  return payload.data;
}

export function cancelVideoMetadataBackfill(): Promise<MetadataBackfillJob> {
  return requestBackfill("/cancel", { method: "POST" });
}

async function requestBackfill(path: string, init: RequestInit): Promise<MetadataBackfillJob> {
  const response = await fetch(`${apiBaseUrl}/api/media/cache/metadata/backfill${path}`, init);
  const payload = (await response.json()) as ApiResponse<MetadataBackfillJob>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new TimelineApiError(payload.error?.code ?? "METADATA_BACKFILL_FAILED", payload.error?.message ?? "Metadata backfill failed");
  }
  return payload.data;
}

export function getTimeline(): Promise<Timeline> {
  return request<Timeline>("", { method: "GET" });
}

export function generateTimeline(): Promise<Timeline> {
  return request<Timeline>("/generate", { method: "POST" });
}

export function saveTimeline(timeline: Timeline): Promise<Timeline> {
  return request<Timeline>("", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(timeline),
  });
}

export async function getTimelineMediaAssetPage(options: {
  offset?: number;
  limit?: number;
} = {}): Promise<TimelineMediaAssetPage> {
  const params = new URLSearchParams();
  if (options.offset !== undefined) {
    params.set("offset", String(options.offset));
  }
  if (options.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  const suffix = params.size ? `?${params.toString()}` : "";
  return request<TimelineMediaAssetPage>(`/media-assets${suffix}`, {
    method: "GET",
  });
}

export async function getTimelineMediaAssets(): Promise<TimelineMediaAsset[]> {
  const result = await getTimelineMediaAssetPage();
  return result.assets;
}

export function assignTimelineMedia(
  sceneId: string,
  contentHash: string | null,
  role: VisualClipRole = "broll",
): Promise<Timeline> {
  return request<Timeline>(`/scenes/${encodeURIComponent(sceneId)}/media`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ contentHash, role }),
  });
}

export function trimTimelineVideo(sceneId: string, sourceStartMilliseconds: number, sourceEndMilliseconds: number, role: VisualClipRole = "broll"): Promise<Timeline> {
  return request<Timeline>(`/scenes/${encodeURIComponent(sceneId)}/media-trim`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sourceStartMilliseconds, sourceEndMilliseconds, role }),
  });
}

export function assignTimelineMusic(contentHash: string | null, volume: number): Promise<Timeline> {
  return request<Timeline>("/music", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ contentHash, volume }),
  });
}

async function request<TData>(
  path: string,
  init: RequestInit,
): Promise<TData> {
  const response = await fetch(`${apiBaseUrl}/api/timeline${path}`, init);
  const payload = (await response.json()) as ApiResponse<TData>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new TimelineApiError(
      payload.error?.code ?? "TIMELINE_REQUEST_FAILED",
      payload.error?.message ?? `Timeline request failed: ${response.status}`,
    );
  }
  return payload.data;
}
