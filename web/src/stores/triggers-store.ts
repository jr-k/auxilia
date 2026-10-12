import { create } from "zustand";
import {
	Trigger,
	TriggerCreate,
	TriggerRun,
	TriggerUpdate,
} from "@/types/triggers";
import { createOnce } from "@/lib/api/once";
import * as triggersApi from "@/lib/api/resources/triggers";
import { getWorkspaceGeneration, isCurrentWorkspaceGeneration } from "@/lib/workspace-generation";
import { useTriggerRunsStore } from "@/stores/trigger-runs-store";

interface TriggersState {
	triggers: Trigger[];
	isInitialized: boolean;
	fetchTriggers: () => Promise<void>;
	refreshTriggers: () => Promise<void>;
	createTrigger: (payload: TriggerCreate) => Promise<Trigger>;
	updateTrigger: (id: string, payload: TriggerUpdate) => Promise<Trigger>;
	deleteTrigger: (id: string) => Promise<void>;
	runTrigger: (id: string) => Promise<TriggerRun>;
	upsertTrigger: (trigger: Trigger) => void;
	removeTriggersForAgent: (agentId: string) => void;
}

export const useTriggersStore = create<TriggersState>((set, get) => {
	// One request even when several components mount before the first load
	// resolves (sidebar count + triggers page).
	const load = createOnce(async () => {
		const generation = getWorkspaceGeneration();
		try {
			const triggers = await triggersApi.listTriggers();
			if (isCurrentWorkspaceGeneration(generation)) {
				set({ triggers, isInitialized: true });
			}
		} catch (error) {
			if (!isCurrentWorkspaceGeneration(generation)) return;
			console.error("Error fetching triggers:", error);
			throw error;
		}
	});

	return {
		triggers: [],
		isInitialized: false,
		fetchTriggers: async () => {
			if (get().isInitialized) {
				return;
			}
			await load.run();
		},
		refreshTriggers: () => load.refresh(),
		createTrigger: async (payload) => {
			const created = await triggersApi.createTrigger(payload);
			set((state) => ({ triggers: [created, ...state.triggers] }));
			return created;
		},
		updateTrigger: async (id, payload) => {
			const updated = await triggersApi.updateTrigger(id, payload);
			set((state) => ({
				triggers: state.triggers.map((trigger) =>
					trigger.id === id ? updated : trigger,
				),
			}));
			return updated;
		},
		deleteTrigger: async (id) => {
			await triggersApi.deleteTrigger(id);
			set((state) => ({
				triggers: state.triggers.filter((trigger) => trigger.id !== id),
			}));
		},
		runTrigger: (id) => triggersApi.runTrigger(id),
		upsertTrigger: (trigger) => {
			set((state) => {
				const exists = state.triggers.some((t) => t.id === trigger.id);
				return {
					triggers: exists
						? state.triggers.map((t) => (t.id === trigger.id ? trigger : t))
						: [trigger, ...state.triggers],
				};
			});
		},
		removeTriggersForAgent: (agentId) => {
			const triggerIds = get()
				.triggers.filter((trigger) => trigger.agentId === agentId)
				.map((trigger) => trigger.id);
			useTriggerRunsStore.getState().removeTriggers(triggerIds);
			set((state) => ({
				triggers: state.triggers.filter((trigger) => trigger.agentId !== agentId),
			}));
		},
	};
});
