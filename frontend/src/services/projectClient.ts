export interface ProjectSummary {
  id: string;
  name: string;
  path: string;
  createdAt: string;
  updatedAt: string;
  schemaVersion: number;
}

interface ApiResponse<TData> {
  success: boolean;
  data: TData | null;
  message: string;
  error: { code: string; message: string } | null;
}

export class ProjectApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8765";

export async function getCurrentProject(): Promise<ProjectSummary | null> {
  const response = await fetch(`${apiBaseUrl}/api/projects/current`);
  const payload = (await response.json()) as ApiResponse<ProjectSummary>;
  if (!response.ok || !payload.success) {
    throw new ProjectApiError(
      payload.error?.code ?? "PROJECT_REQUEST_FAILED",
      payload.error?.message ?? `Project request failed: ${response.status}`,
    );
  }
  return payload.data;
}

export function createProject(
  name: string,
  parentDirectory: string,
): Promise<ProjectSummary> {
  return requestProject("", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, parentDirectory }),
  });
}

export function openProject(path: string): Promise<ProjectSummary> {
  return requestProject("/open", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
}

export function closeProject(): Promise<ProjectSummary> {
  return requestProject("/close", { method: "POST" });
}

export async function listRecentProjects(): Promise<ProjectSummary[]> {
  const response = await fetch(`${apiBaseUrl}/api/projects/recent?limit=5`);
  const payload = (await response.json()) as ApiResponse<{
    projects: ProjectSummary[];
  }>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new ProjectApiError(
      payload.error?.code ?? "PROJECT_REQUEST_FAILED",
      payload.error?.message ?? `Project request failed: ${response.status}`,
    );
  }
  return payload.data.projects;
}

async function requestProject(
  path: string,
  init: RequestInit,
): Promise<ProjectSummary> {
  const response = await fetch(`${apiBaseUrl}/api/projects${path}`, init);
  const payload = (await response.json()) as ApiResponse<ProjectSummary>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new ProjectApiError(
      payload.error?.code ?? "PROJECT_REQUEST_FAILED",
      payload.error?.message ?? `Project request failed: ${response.status}`,
    );
  }
  return payload.data;
}
