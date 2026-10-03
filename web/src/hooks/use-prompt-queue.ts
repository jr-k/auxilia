"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import * as threadsApi from "@/lib/api/resources/threads";
import type { QueuedPrompt } from "@/types/runs";

const POLL_MS = 1000;

const byPosition = (a: QueuedPrompt, b: QueuedPrompt) =>
	a.position - b.position || a.id.localeCompare(b.id);

export function usePromptQueue(threadId: string, runActive: boolean) {
	const [items, setItems] = useState<QueuedPrompt[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [loadedThreadId, setLoadedThreadId] = useState<string | null>(null);
	const requestVersion = useRef(0);
	const threadIdRef = useRef(threadId);
	const refreshInFlight = useRef<{
		threadId: string;
		promise: Promise<void>;
	} | null>(null);

	useEffect(() => {
		threadIdRef.current = threadId;
		requestVersion.current += 1;
	}, [threadId]);

	const refresh = useCallback((): Promise<void> => {
		if (refreshInFlight.current?.threadId === threadId) {
			return refreshInFlight.current.promise;
		}
		const version = ++requestVersion.current;
		const promise = threadsApi
			.listQueuedPrompts(threadId)
			.then((next) => {
				if (
					version === requestVersion.current &&
					threadIdRef.current === threadId
				) {
					setItems(next.sort(byPosition));
					setLoadedThreadId(threadId);
				}
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
		if (
			!runActive &&
			items.length === 0 &&
			loadedThreadId === threadId
		)
			return;
		const timer = window.setInterval(() => {
			void refresh().catch(() => {});
		}, POLL_MS);
		return () => {
			window.clearInterval(timer);
		};
	}, [items.length, loadedThreadId, refresh, runActive, threadId]);

	const enqueue = useCallback(
		async (text: string) => {
			const version = requestVersion.current;
			const item = await threadsApi.enqueuePrompt(threadId, text);
			if (
				threadIdRef.current !== threadId ||
				version !== requestVersion.current
			) {
				return item;
			}
			setItems((current) =>
				loadedThreadId === threadId
					? [...current, item].sort(byPosition)
					: [item],
			);
			setLoadedThreadId(threadId);
			return item;
		},
		[loadedThreadId, threadId],
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

	const remove = useCallback(
		async (id: string) => {
			const version = requestVersion.current;
			const previous = items;
			setItems((current) => current.filter((item) => item.id !== id));
			try {
				await threadsApi.removeQueuedPrompt(threadId, id);
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

	return {
		items: loadedThreadId === threadId ? items : [],
		isLoading: isLoading || loadedThreadId !== threadId,
		enqueue,
		update,
		beginEdit,
		endEdit,
		remove,
		reorder,
		refresh,
	};
}
