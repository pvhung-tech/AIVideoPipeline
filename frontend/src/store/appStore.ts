import { create } from "zustand";

import {
  getBackendHealth,
  type BackendHealth,
} from "../services/healthClient";

type HealthState =
  | { status: "loading" }
  | { status: "online"; health: BackendHealth }
  | { status: "offline"; message: string };

interface AppState {
  healthState: HealthState;
  checkBackendHealth: () => Promise<void>;
}

export const useAppStore = create<AppState>((set) => ({
  healthState: { status: "loading" },
  checkBackendHealth: async () => {
    set({ healthState: { status: "loading" } });

    try {
      const health = await getBackendHealth();
      set({ healthState: { status: "online", health } });
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : "Backend unavailable";
      set({ healthState: { status: "offline", message } });
    }
  },
}));
