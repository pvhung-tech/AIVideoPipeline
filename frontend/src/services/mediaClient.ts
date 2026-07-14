export interface MediaCacheManifest {
  schemaVersion: number;
  entries: Array<{
    contentHash: string;
    relativePath: string;
    sizeBytes: number;
    durationMilliseconds: number | null;
    sources?: Array<{
      providerId: string;
      mediaId: string;
      sourceUri: string;
    }>;
  }>;
  totalSizeBytes: number;
}

export type MediaType = "image" | "video";

export interface MediaSearchItem {
  id: string;
  providerId: string;
  mediaType: MediaType;
  title: string;
  sourceUri: string;
  previewUri: string | null;
  fileSizeBytes: number | null;
  modifiedAt: string | null;
  score: number;
  license: string | null;
  sourcePageUri: string | null;
  creator: string | null;
  creatorUri: string | null;
}

export interface MediaProviderError {
  providerId: string;
  code: string;
  message: string;
}

export interface MediaSearchPage {
  providerId: string;
  query: string;
  totalResults: number;
  offset: number;
  limit: number;
  truncated: boolean;
  items: MediaSearchItem[];
  providerErrors: MediaProviderError[];
  deduplication: {
    totalCandidates: number;
    retainedItems: number;
    fingerprintedCandidates: number;
    canonicalDuplicates: number;
    perceptualImageDuplicates: number;
    perceptualVideoDuplicates: number;
    imageHammingThreshold: number;
    videoAverageHammingThreshold: number;
  } | null;
}

export interface CachedMedia {
  mediaId: string;
  providerId: string;
  contentHash: string;
  path: string;
  uri: string;
  sizeBytes: number;
  duplicate: boolean;
  diagnostics: {
    providerId: string;
    duplicate: boolean;
    sizeBytes: number;
    sourceTransferSeconds: number;
    sourceHashSeconds: number;
    sourceFileWriteSeconds: number;
    duplicateCheckSeconds: number;
    fingerprintSeconds: number;
    metadataSeconds: number;
    manifestSeconds: number;
    totalSeconds: number;
    fingerprintDeferred: boolean;
  } | null;
}

export type FingerprintBackfillStatus =
  | "queued"
  | "running"
  | "completed"
  | "cancelled"
  | "failed";

export interface FingerprintBackfillJob {
  jobId: string;
  projectId: string;
  status: FingerprintBackfillStatus;
  totalMedia: number;
  processedMedia: number;
  progressPercent: number;
  updatedMedia: number;
  skippedMedia: number;
  failedCount: number;
  failedContentHashes: string[];
  errorMessage: string | null;
}

interface ApiResponse<TData> {
  success: boolean;
  data: TData | null;
  message: string;
  error: { code: string; message: string } | null;
}

export class MediaApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8765";

export async function listMediaProviders(): Promise<string[]> {
  const result = await request<{ providers: string[] }>("/providers", {
    method: "GET",
  });
  return result.providers;
}

export function searchMedia(options: {
  query: string;
  mediaType: "all" | MediaType;
  providerId: string;
  limit?: number;
  offset?: number;
}): Promise<MediaSearchPage> {
  const params = new URLSearchParams();
  params.set("query", options.query);
  params.set("limit", String(options.limit ?? 24));
  params.set("offset", String(options.offset ?? 0));
  if (options.providerId !== "all") {
    params.set("providerId", options.providerId);
  }
  if (options.mediaType === "all") {
    params.append("mediaType", "image");
    params.append("mediaType", "video");
  } else {
    params.append("mediaType", options.mediaType);
  }
  return request<MediaSearchPage>(`/search?${params.toString()}`, {
    method: "GET",
  });
}

export function cacheMedia(item: MediaSearchItem): Promise<CachedMedia> {
  return request<CachedMedia>("/cache", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      providerId: item.providerId,
      mediaId: item.id,
      sourceUri: item.sourceUri,
      fileName: suggestedFileName(item),
    }),
  });
}

export async function getMediaCacheManifest(): Promise<MediaCacheManifest | null> {
  const response = await fetch(`${apiBaseUrl}/api/media/cache`);
  const payload = (await response.json()) as ApiResponse<MediaCacheManifest>;
  if (!response.ok || !payload.success) {
    const code = payload.error?.code ?? "MEDIA_REQUEST_FAILED";
    if (code === "NO_ACTIVE_PROJECT") {
      return null;
    }
    throw new MediaApiError(
      code,
      payload.error?.message ?? `Media request failed: ${response.status}`,
    );
  }
  return payload.data;
}

export function backfillMediaFingerprints(): Promise<FingerprintBackfillJob> {
  return request<FingerprintBackfillJob>("/cache/fingerprints/backfill", {
    method: "POST",
  });
}

export async function getMediaFingerprintBackfillStatus(): Promise<FingerprintBackfillJob | null> {
  const response = await fetch(`${apiBaseUrl}/api/media/cache/fingerprints/backfill/status`);
  const payload = (await response.json()) as ApiResponse<FingerprintBackfillJob>;
  if (!response.ok || !payload.success) {
    throw new MediaApiError(
      payload.error?.code ?? "MEDIA_FINGERPRINT_BACKFILL_FAILED",
      payload.error?.message ?? "Media fingerprint backfill status failed",
    );
  }
  return payload.data;
}

export function cancelMediaFingerprintBackfill(): Promise<FingerprintBackfillJob> {
  return request<FingerprintBackfillJob>("/cache/fingerprints/backfill/cancel", {
    method: "POST",
  });
}

async function request<TData>(
  path: string,
  init: RequestInit,
): Promise<TData> {
  const response = await fetch(`${apiBaseUrl}/api/media${path}`, init);
  const payload = (await response.json()) as ApiResponse<TData>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new MediaApiError(
      payload.error?.code ?? "MEDIA_REQUEST_FAILED",
      payload.error?.message ?? `Media request failed: ${response.status}`,
    );
  }
  return payload.data;
}

function suggestedFileName(item: MediaSearchItem): string {
  const extension = item.mediaType === "image" ? "jpg" : "mp4";
  return `${item.providerId}-${item.id}.${extension}`.replace(/[^\w.-]/g, "-");
}
