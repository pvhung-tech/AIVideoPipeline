export interface ScriptScene {
  id: string;
  order: number;
  text: string;
  startMilliseconds: number | null;
  endMilliseconds: number | null;
}

export interface SceneCollection {
  schemaVersion: number;
  sceneCount: number;
  scenes: ScriptScene[];
  updatedAt: string;
}

export interface ScriptDocument {
  format: "txt" | "srt";
  originalPath: string;
  contentPath: string;
  importedAt: string;
  characterCount: number;
  cueCount: number;
  sceneCount: number;
  scenes: ScriptScene[];
}

interface ApiResponse<TData> {
  success: boolean;
  data: TData | null;
  message: string;
  error: { code: string; message: string } | null;
}

export class ScriptApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8765";

export async function importScript(path: string): Promise<ScriptDocument> {
  return request<ScriptDocument>("/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
}

export async function listScriptScenes(): Promise<SceneCollection | null> {
  const response = await fetch(`${apiBaseUrl}/api/scripts/scenes`);
  const payload = (await response.json()) as ApiResponse<SceneCollection>;
  if (!response.ok || !payload.success) {
    const code = payload.error?.code ?? "SCRIPT_REQUEST_FAILED";
    if (code === "NO_ACTIVE_PROJECT" || code === "SCENES_NOT_FOUND") {
      return null;
    }
    throw new ScriptApiError(
      code,
      payload.error?.message ?? `Script request failed: ${response.status}`,
    );
  }
  return payload.data;
}

export function updateScriptScene(
  sceneId: string,
  text: string,
): Promise<SceneCollection> {
  return request<SceneCollection>(`/scenes/${encodeURIComponent(sceneId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

async function request<TData>(
  path: string,
  init: RequestInit,
): Promise<TData> {
  const response = await fetch(`${apiBaseUrl}/api/scripts${path}`, init);
  const payload = (await response.json()) as ApiResponse<TData>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new ScriptApiError(
      payload.error?.code ?? "SCRIPT_REQUEST_FAILED",
      payload.error?.message ?? `Script request failed: ${response.status}`,
    );
  }
  return payload.data;
}
