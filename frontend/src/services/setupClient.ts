export interface SetupCheck {
  id: string;
  label: string;
  status: string;
  configured: boolean;
  message: string;
  hint: string;
  envVar: string | null;
  valuePreview: string | null;
}

export interface SetupStatus {
  providers: SetupCheck[];
  apiKeys: SetupCheck[];
  tools: SetupCheck[];
}

interface ApiResponse<TData> {
  success: boolean;
  data: TData | null;
  message: string;
  error: { code: string; message: string } | null;
}

export class SetupApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8765";

export async function getSetupStatus(): Promise<SetupStatus> {
  const response = await fetch(`${apiBaseUrl}/api/setup/status`);
  const payload = (await response.json()) as ApiResponse<SetupStatus>;
  if (!response.ok || !payload.success || payload.data === null) {
    throw new SetupApiError(
      payload.error?.code ?? "SETUP_REQUEST_FAILED",
      payload.error?.message ?? `Setup request failed: ${response.status}`,
    );
  }
  return payload.data;
}
