import { create } from "zustand";

import * as authApi from "@/lib/api/resources/auth";
import * as workspacesApi from "@/lib/api/resources/workspaces";
import { resetWorkspaceStores } from "@/stores/reset-workspace-stores";
import { useUserStore } from "@/stores/user-store";
import type { Workspace, WorkspaceCreate, WorkspacePatch } from "@/types/workspaces";

interface WorkspacesState {
	workspaces: Workspace[];
	activeWorkspaceId: string | null;
	isInitialized: boolean;
	isLoading: boolean;
	isSwitching: boolean;
	error: string | null;
	hydrate: () => Promise<void>;
	createWorkspace: (payload: WorkspaceCreate) => Promise<Workspace>;
	updateWorkspace: (workspaceId: string, patch: WorkspacePatch) => Promise<Workspace>;
	setWorkspaceImageRevision: (workspaceId: string, revision: string | null) => void;
	selectWorkspace: (workspaceId: string) => Promise<void>;
}

let hydration: Promise<void> | null = null;

export const useWorkspacesStore = create<WorkspacesState>((set, get) => ({
	workspaces: [],
	activeWorkspaceId: null,
	isInitialized: false,
	isLoading: false,
	isSwitching: false,
	error: null,
	hydrate: async () => {
		if (get().isInitialized) return;
		if (hydration) return hydration;
		set({ isLoading: true, error: null });
		hydration = Promise.all([
			workspacesApi.listWorkspaces(),
			authApi.getCurrentUser(),
		])
			.then(([workspaces, user]) => {
				useUserStore.getState().setUser(user);
				set({
					workspaces,
					activeWorkspaceId: user.workspaceId,
					isInitialized: true,
				});
			})
			.catch((cause: unknown) => {
				console.error("Failed to load workspaces:", cause);
				set({
					error: "Could not load workspaces.",
					isInitialized: false,
				});
			})
			.finally(() => {
				hydration = null;
				set({ isLoading: false });
			});
		return hydration;
	},
	createWorkspace: async (payload) => {
		set({ isSwitching: true });
		try {
			const workspace = await workspacesApi.createWorkspace(payload);
			resetWorkspaceStores();
			set((state) => ({
				workspaces: [...state.workspaces, workspace],
				activeWorkspaceId: workspace.id,
				isSwitching: false,
			}));
			return workspace;
		} catch (error) {
			set({ isSwitching: false });
			throw error;
		}
	},
	updateWorkspace: async (workspaceId, patch) => {
		const workspace = await workspacesApi.updateWorkspace(workspaceId, patch);
		set((state) => ({
			workspaces: state.workspaces.map((candidate) =>
				candidate.id === workspaceId ? workspace : candidate,
			),
		}));
		return workspace;
	},
	setWorkspaceImageRevision: (workspaceId, revision) => {
		set((state) => ({
			workspaces: state.workspaces.map((workspace) =>
				workspace.id === workspaceId
					? { ...workspace, imageRevision: revision }
					: workspace,
			),
		}));
	},
	selectWorkspace: async (workspaceId) => {
		if (workspaceId === get().activeWorkspaceId || get().isSwitching) return;
		set({ isSwitching: true });
		try {
			await workspacesApi.selectWorkspace(workspaceId);
			resetWorkspaceStores();
			set({ activeWorkspaceId: workspaceId });
		} catch (error) {
			set({ isSwitching: false });
			throw error;
		}
	},
}));
