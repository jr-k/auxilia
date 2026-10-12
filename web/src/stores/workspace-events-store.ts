import { create } from "zustand";

import type { WorkspaceInvalidation } from "@/types/workspace-events";

export type WorkspaceEventConnection =
  | "idle"
  | "connecting"
  | "connected"
  | "disconnected";

interface WorkspaceEventsState {
  connection: WorkspaceEventConnection;
  syncVersion: number;
  threadsVersion: number;
  runsVersion: number;
  triggerHistoryVersion: number;
  queueVersions: Record<string, number>;
  setConnection: (connection: WorkspaceEventConnection) => void;
  sync: () => void;
  invalidate: (event: WorkspaceInvalidation) => void;
  reset: () => void;
}

const initialVersions = {
  syncVersion: 0,
  threadsVersion: 0,
  runsVersion: 0,
  triggerHistoryVersion: 0,
  queueVersions: {},
};

export const useWorkspaceEventsStore = create<WorkspaceEventsState>((set) => ({
  connection: "idle",
  ...initialVersions,
  setConnection: (connection) => {
    set({ connection });
  },
  sync: () => {
    set((state) => ({
      syncVersion: state.syncVersion + 1,
      threadsVersion: state.threadsVersion + 1,
      runsVersion: state.runsVersion + 1,
      triggerHistoryVersion: state.triggerHistoryVersion + 1,
    }));
  },
  invalidate: (event) => {
    switch (event.kind) {
      case "threads":
        set((state) => ({ threadsVersion: state.threadsVersion + 1 }));
        break;
      case "runs":
        set((state) => ({ runsVersion: state.runsVersion + 1 }));
        break;
      case "trigger_history":
        set((state) => ({
          triggerHistoryVersion: state.triggerHistoryVersion + 1,
        }));
        break;
      case "prompt_queue": {
        const threadId = event.threadId;
        if (threadId === undefined) break;
        set((state) => ({
          queueVersions: {
            ...state.queueVersions,
            [threadId]: (state.queueVersions[threadId] ?? 0) + 1,
          },
        }));
        break;
      }
    }
  },
  reset: () => {
    set({ connection: "idle", ...initialVersions });
  },
}));
