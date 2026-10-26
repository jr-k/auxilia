import { create } from "zustand";
import { type PromptInputMessage } from "@/components/ai-elements/prompt-input";

interface PendingMessageState {
	pendingMessages: Map<string, PromptInputMessage>;
	optimisticMessages: Map<string, PromptInputMessage>;
	setPendingMessage: (threadId: string, message: PromptInputMessage) => void;
	consumePendingMessage: (threadId: string) => PromptInputMessage | null;
	setOptimisticMessage: (threadId: string, message: PromptInputMessage) => void;
	clearOptimisticMessage: (threadId: string) => void;
}

export const usePendingMessageStore = create<PendingMessageState>(
	(set, get) => ({
		pendingMessages: new Map(),
		optimisticMessages: new Map(),
		setPendingMessage: (threadId, message) =>
			set((state) => {
				const newMap = new Map(state.pendingMessages);
				newMap.set(threadId, message);
				return { pendingMessages: newMap };
			}),
		consumePendingMessage: (threadId) => {
			const message = get().pendingMessages.get(threadId);
			if (message) {
				set((state) => {
					const newMap = new Map(state.pendingMessages);
					newMap.delete(threadId);
					return { pendingMessages: newMap };
				});
			}
			return message ?? null;
		},
		setOptimisticMessage: (threadId, message) =>
			set((state) => {
				const optimisticMessages = new Map(state.optimisticMessages);
				optimisticMessages.set(threadId, {
					...message,
					files: message.files ? [...message.files] : [],
				});
				return { optimisticMessages };
			}),
		clearOptimisticMessage: (threadId) =>
			set((state) => {
				if (!state.optimisticMessages.has(threadId)) return state;
				const optimisticMessages = new Map(state.optimisticMessages);
				optimisticMessages.delete(threadId);
				return { optimisticMessages };
			}),
	}),
);
