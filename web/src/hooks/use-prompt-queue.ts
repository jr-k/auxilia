"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { PromptInputMessage } from "@/components/ai-elements/prompt-input";
import * as threadsApi from "@/lib/api/resources/threads";
import { promptMessageToContent } from "@/lib/thread-session/build-content";
import { useWorkspaceEventsStore } from "@/stores/workspace-events-store";
import type { QueuedPrompt } from "@/types/runs";

const POLL_MS = 1000;
/** How long a claimed item counts as "a run is starting" when the stream
 * never reports it (worker crashed before emitting a lifecycle event). */
const CLAIM_GRACE_MS = 5000;
/** Safety net for the optimistic bubble if a claimed run never emits input. */
const CLAIMED_PROMPT_GRACE_MS = 15_000;

const byPosition = (a: QueuedPrompt, b: QueuedPrompt) =>
	a.position - b.position || a.id.localeCompare(b.id);

export function usePromptQueue(
	threadId: string,
	runActive: boolean,
	userMessageCount: number,
) {
	const connection = useWorkspaceEventsStore((state) => state.connection);
	const syncVersion = useWorkspaceEventsStore((state) => state.syncVersion);
	const queueVersion = useWorkspaceEventsStore(
		(state) => state.queueVersions[threadId] ?? 0,
	);
	const [items, setItems] = useState<QueuedPrompt[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [loadedThreadId, setLoadedThreadId] = useState<string | null>(null);
	// A queued item that vanished from a poll without this client removing
	// it was claimed by the worker: a run is active server-side, even though
	// the stream's `running` lifecycle event hasn't landed yet. The composer
	// must keep queueing through that gap, or a fast Enter starts a direct
	// `submit` that the server parks in the queue anyway — and the prompt
	// shows up both in the conversation and in the queue.
	const [claimedRunStart, setClaimedRunStart] = useState<{
		threadId: string;
		claimedAt: number;
	} | null>(null);
	const [claimedPrompt, setClaimedPrompt] = useState<{
		threadId: string;
		item: QueuedPrompt;
		claimedAt: number;
		baselineUserMessageCount: number;
	} | null>(null);
	const userMessageCountRef = useRef(userMessageCount);
	const promptBaselines = useRef(new Map<string, number>());
	useEffect(() => {
		userMessageCountRef.current = userMessageCount;
	}, [userMessageCount]);
	const itemsRef = useRef(items);
	useEffect(() => {
		itemsRef.current = items;
	}, [items]);
	const removedIds = useRef(new Set<string>());
	// Bumped only on thread switch: a response for another thread is dropped.
	const requestVersion = useRef(0);
	const threadIdRef = useRef(threadId);
	// Orders poll responses so an older list can't overwrite a newer one.
	const refreshSeq = useRef(0);
	const refreshInFlight = useRef<{
		threadId: string;
		promise: Promise<void>;
	} | null>(null);
	// Enqueues run one at a time so queue positions follow typing order, and
	// while one is in flight a poll that left before it must not apply its
	// (already stale) list over the optimistic item.
	const enqueueChain = useRef<Promise<void>>(Promise.resolve());
	const enqueueInFlight = useRef(0);

	useEffect(() => {
		threadIdRef.current = threadId;
		requestVersion.current += 1;
		removedIds.current.clear();
		promptBaselines.current.clear();
	}, [threadId]);

	// The stream confirmed the run (or its end): the claim did its job.
	useEffect(() => {
		if (!runActive) return;
		// This state mirrors an external stream transition, so clearing it in
		// the transition effect is intentional.
		// eslint-disable-next-line react-hooks/set-state-in-effect
		setClaimedRunStart((current) =>
			current?.threadId === threadId ? null : current,
		);
	}, [runActive, threadId]);
	useEffect(() => {
		if (claimedRunStart == null) return;
		const remaining =
			claimedRunStart.claimedAt + CLAIM_GRACE_MS - Date.now();
		const timer = window.setTimeout(
			() => {
				setClaimedRunStart((current) =>
					current?.claimedAt === claimedRunStart.claimedAt
						? null
						: current,
				);
			},
			Math.max(0, remaining),
		);
		return () => {
			window.clearTimeout(timer);
		};
	}, [claimedRunStart]);
	useEffect(() => {
		if (claimedPrompt == null) return;
		const remaining =
			claimedPrompt.claimedAt + CLAIMED_PROMPT_GRACE_MS - Date.now();
		const timer = window.setTimeout(
			() => {
				setClaimedPrompt((current) =>
					current?.claimedAt === claimedPrompt.claimedAt ? null : current,
				);
			},
			Math.max(0, remaining),
		);
		return () => {
			window.clearTimeout(timer);
		};
	}, [claimedPrompt]);

	const refresh = useCallback((): Promise<void> => {
		if (refreshInFlight.current?.threadId === threadId) {
			return refreshInFlight.current.promise;
		}
		const version = requestVersion.current;
		const seq = ++refreshSeq.current;
		const promise = threadsApi
			.listQueuedPrompts(threadId)
			.then((next) => {
				if (
					version !== requestVersion.current ||
					threadIdRef.current !== threadId ||
					seq !== refreshSeq.current
				) {
					return;
				}
				if (enqueueInFlight.current === 0) {
					const present = new Set(next.map((item) => item.id));
					const claimed = itemsRef.current.find(
						(item) => !present.has(item.id) && !removedIds.current.has(item.id),
					);
					if (claimed) {
						const now = Date.now();
						setClaimedRunStart({ threadId, claimedAt: now });
						setClaimedPrompt({
							threadId,
							item: claimed,
							claimedAt: now,
							baselineUserMessageCount:
								promptBaselines.current.get(claimed.id) ??
								userMessageCountRef.current,
						});
						promptBaselines.current.delete(claimed.id);
					}
					for (const item of next) {
						// The server just confirmed this item is still waiting.
						// Its eventual optimistic bubble should only outlive a
						// user message added after this confirmed queue state.
						promptBaselines.current.set(
							item.id,
							userMessageCountRef.current,
						);
					}
					for (const id of removedIds.current) {
						if (!present.has(id)) {
							removedIds.current.delete(id);
							promptBaselines.current.delete(id);
						}
					}
					setItems(next.sort(byPosition));
				}
				setLoadedThreadId(threadId);
			})
			.finally(() => {
				if (refreshInFlight.current?.promise === promise) {
					refreshInFlight.current = null;
				}
				if (
					version === requestVersion.current &&
					threadIdRef.current === threadId
				) {
					setIsLoading(false);
				}
			});
		refreshInFlight.current = { threadId, promise };
		return promise;
	}, [threadId]);

	useEffect(() => {
		void refresh().catch(() => {});
	}, [refresh]);
	useEffect(() => {
		if (syncVersion === 0 && queueVersion === 0) return;
		void refresh().catch(() => {});
	}, [queueVersion, refresh, syncVersion]);

	// A run starting (a queued item was claimed) or ending (the next one is
	// about to be) is exactly when the list changes: don't wait for the poll.
	useEffect(() => {
		void refresh().catch(() => {});
	}, [refresh, runActive]);

	// A boolean dependency, not `items.length`: resetting the interval on
	// every enqueue meant it never fired while the user was typing fast.
	const shouldPoll =
		connection === "disconnected" &&
		(runActive || items.length > 0 || loadedThreadId !== threadId);
	useEffect(() => {
		if (!shouldPoll) return;
		const timer = window.setInterval(() => {
			void refresh().catch(() => {});
		}, POLL_MS);
		return () => {
			window.clearInterval(timer);
		};
	}, [refresh, shouldPoll]);

	const enqueue = useCallback(
		(message: PromptInputMessage) => {
			const content = promptMessageToContent(message);
			if (content == null) return Promise.resolve();
			const version = requestVersion.current;
			enqueueInFlight.current += 1;
			const operation = enqueueChain.current.then(async () => {
				try {
					const item = await threadsApi.enqueuePrompt(threadId, content);
					if (
						threadIdRef.current !== threadId ||
						version !== requestVersion.current
					) {
						return item;
					}
					promptBaselines.current.set(item.id, userMessageCountRef.current);
					setItems((current) =>
						loadedThreadId === threadId
							? [
									...current.filter((candidate) => candidate.id !== item.id),
									item,
								].sort(byPosition)
							: [item],
					);
					setLoadedThreadId(threadId);
					return item;
				} finally {
					enqueueInFlight.current -= 1;
					if (
						enqueueInFlight.current === 0 &&
						threadIdRef.current === threadId
					) {
						// Reconcile with the server once the burst is over (an
						// item may already have been claimed meanwhile).
						void refresh().catch(() => {});
					}
				}
			});
			enqueueChain.current = operation.then(
				() => undefined,
				() => undefined,
			);
			return operation;
		},
		[loadedThreadId, refresh, threadId],
	);

	const update = useCallback(
		async (id: string, text: string) => {
			const version = requestVersion.current;
			try {
				const item = await threadsApi.updateQueuedPrompt(threadId, id, text);
				if (
					threadIdRef.current !== threadId ||
					version !== requestVersion.current
				) {
					return item;
				}
				setItems((current) =>
					current
						.map((candidate) => (candidate.id === id ? item : candidate))
						.sort(byPosition),
				);
				return item;
			} catch (error) {
				if (threadIdRef.current === threadId) {
					void refresh().catch(() => {});
				}
				throw error;
			}
		},
		[refresh, threadId],
	);

	const beginEdit = useCallback(
		async (id: string) => {
			await threadsApi.beginQueuedPromptEdit(threadId, id);
		},
		[threadId],
	);

	const endEdit = useCallback(
		async (id: string) => {
			await threadsApi.endQueuedPromptEdit(threadId, id);
		},
		[threadId],
	);

	const sendNow = useCallback(
		async (id: string) => {
			const version = requestVersion.current;
			const previous = items;
			setItems((current) => {
				const selected = current.find((item) => item.id === id);
				if (!selected) return current;
				const ordered = [
					selected,
					...current.filter((item) => item.id !== id),
				];
				const positions = current
					.map((item) => item.position)
					.sort((a, b) => a - b);
				return ordered.map((item, index) => ({
					...item,
					position: positions[index] ?? item.position,
				}));
			});
			try {
				await threadsApi.sendQueuedPromptNow(threadId, id);
				if (
					threadIdRef.current === threadId &&
					version === requestVersion.current
				) {
					void refresh().catch(() => {});
				}
			} catch (error) {
				if (
					threadIdRef.current === threadId &&
					version === requestVersion.current
				) {
					setItems(previous);
					void refresh().catch(() => {});
				}
				throw error;
			}
		},
		[items, refresh, threadId],
	);

	const remove = useCallback(
		async (id: string) => {
			const version = requestVersion.current;
			const previous = items;
			removedIds.current.add(id);
			promptBaselines.current.delete(id);
			setItems((current) => current.filter((item) => item.id !== id));
			try {
				await threadsApi.removeQueuedPrompt(threadId, id);
			} catch (error) {
				if (
					threadIdRef.current === threadId &&
					version === requestVersion.current
				) {
					removedIds.current.delete(id);
					setItems(previous);
					void refresh().catch(() => {});
				}
				throw error;
			}
		},
		[items, refresh, threadId],
	);

	const reorder = useCallback(
		async (orderedIds: string[]) => {
			const version = requestVersion.current;
			const previous = items;
			const index = new Map(orderedIds.map((id, position) => [id, position]));
			setItems((current) =>
				[...current].sort(
					(a, b) => (index.get(a.id) ?? 0) - (index.get(b.id) ?? 0),
				),
			);
			try {
				const next = await threadsApi.reorderQueuedPrompts(
					threadId,
					orderedIds,
				);
				if (
					threadIdRef.current !== threadId ||
					version !== requestVersion.current
				) {
					return;
				}
				setItems(next.sort(byPosition));
			} catch (error) {
				if (
					threadIdRef.current === threadId &&
					version === requestVersion.current
				) {
					setItems(previous);
					void refresh().catch(() => {});
				}
				throw error;
			}
		},
		[items, refresh, threadId],
	);

	const acknowledgeClaimedPrompt = useCallback((id: string) => {
		setClaimedPrompt((current) =>
			current?.item.id === id ? null : current,
		);
	}, []);

	return {
		items: loadedThreadId === threadId ? items : [],
		isLoading: isLoading || loadedThreadId !== threadId,
		/** A queued prompt was just claimed; the stream hasn't confirmed yet. */
		runStarting: claimedRunStart?.threadId === threadId,
		/** Prompt claimed by the worker but not necessarily in the transcript yet. */
		claimedPrompt:
			claimedPrompt?.threadId === threadId ? claimedPrompt.item : null,
		claimedPromptBaseline:
			claimedPrompt?.threadId === threadId
				? claimedPrompt.baselineUserMessageCount
				: null,
		acknowledgeClaimedPrompt,
		enqueue,
		update,
		beginEdit,
		endEdit,
		sendNow,
		remove,
		reorder,
		refresh,
	};
}
