export interface BackendHealth {
  appName: string;
  environment: string;
  status: string;
}

interface ApiResponse<TData> {
  success: boolean;
  data: TData | null;
  message: string;
  error: { code: string; message: string } | null;
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8765";

export async function getBackendHealth(): Promise<BackendHealth> {
  const response = await fetch(`${apiBaseUrl}/api/health`);

  if (!response.ok) {
    throw new Error(`Backend health request failed: ${response.status}`);
  }

  const payload = (await response.json()) as ApiResponse<BackendHealth>;

  if (!payload.success || payload.data === null) {
    throw new Error(payload.error?.message ?? "Invalid backend health response");
  }

  return payload.data;
}
