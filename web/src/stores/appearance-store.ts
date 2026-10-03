import { create } from "zustand";
import { createOnce } from "@/lib/api/once";
import * as appearanceApi from "@/lib/api/resources/appearance";
import type { WorkspaceAppearance } from "@/types/appearance";

interface AppearanceState {
	appearance: WorkspaceAppearance;
	isInitialized: boolean;
	fetchAppearance: () => Promise<void>;
	setAppearance: (appearance: WorkspaceAppearance) => void;
}

const DEFAULT_APPEARANCE: WorkspaceAppearance = {
	appName: "auxilia",
	logoRevision: null,
};

export const useAppearanceStore = create<AppearanceState>((set, get) => {
	const load = createOnce(async () => {
		try {
			const appearance = await appearanceApi.getAppearance();
			set({ appearance, isInitialized: true });
		} catch (error) {
			console.error("Error fetching workspace appearance:", error);
			set({ isInitialized: true });
		}
	});

	return {
		appearance: DEFAULT_APPEARANCE,
		isInitialized: false,
		fetchAppearance: async () => {
			if (get().isInitialized) return;
			await load.run();
		},
		setAppearance: (appearance) => {
			set({ appearance, isInitialized: true });
		},
	};
});
