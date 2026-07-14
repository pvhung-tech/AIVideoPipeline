export interface SceneAnalysisResult {
  sceneId: string;
  sourceTextHash: string;
  description: string;
  category: string;
  keywords: string[];
  providerId: string;
  model: string;
  promptVersion: number;
  analyzedAt: string;
}

export interface SceneAnalysisCollection {
  schemaVersion: number;
  updatedAt: string;
  resultCount: number;
  results: SceneAnalysisResult[];
}

export interface SceneAnalysisFailure {
  sceneId: string;
  code: string;
  message: string;
}

export interface SceneBatchAnalysisResult {
  totalScenes: number;
  successCount: number;
  failureCount: number;
  skippedCount: number;
  results: SceneAnalysisResult[];
  failures: SceneAnalysisFailure[];
  skippedSceneIds: string[];
}

export interface AnalyzeScenesOptions {
  contentType: string;
  language: string;
  providerId: string | null;
  model: string | null;
  reanalyze: boolean;
}

interface ApiResponse<TData> {
  success: boolean;
  data: TData | null;
  message: string;
  error: { code: string; message: string } | null;
}

export class AIAnalysisApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8765";

export async function listSceneAnalyses(): Promise<SceneAnalysisCollection | null> {
  const response = await fetch(`${apiBaseUrl}/api/ai/scenes/analysis`);
  const payload = (await response.json()) as ApiResponse<SceneAnalysisCollection>;
  if (!response.ok || !payload.success) {
    const code = payload.error?.code ?? "AI_ANALYSIS_REQUEST_FAILED";
    if (code === "NO_ACTIVE_PROJECT") {
      return null;
    }
    throw new AIAnalysisApiError(
      code,
      payload.error?.message ?? `AI analysis request failed: ${response.status}`,
    );
  }
  return payload.data;
}

export function analyzeScenesBatch(
  options: AnalyzeScenesOptions,
): Promise<SceneBatchAnalysisResult> {
  return request<SceneBatchAnalysisResult>("/scenes/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contentType: options.contentType,
      language: options.language,
      providerId: options.providerId,
      model: options.model,
      reanalyze: options.reanalyze,
    }),
  });
}

async function request<TData>(
  path: string,
  init: RequestInit,
): Promise<TData> {
  const response = await fetch(`${apiBaseUrl}/api/ai${path}`, init);
  const payload = (await response.json()) as ApiResponse<TData>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new AIAnalysisApiError(
      payload.error?.code ?? "AI_ANALYSIS_REQUEST_FAILED",
      payload.error?.message ?? `AI analysis request failed: ${response.status}`,
    );
  }
  return payload.data;
}
