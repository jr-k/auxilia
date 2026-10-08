"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

interface RowSelectionOptions {
	orderedIds: string[];
	eligibleIds?: string[];
}

export function useRowSelection({
	orderedIds,
	eligibleIds = orderedIds,
}: RowSelectionOptions) {
	const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
	const anchorId = useRef<string | null>(null);
	const eligibleKey = eligibleIds.join("\u0000");
	const orderedKey = orderedIds.join("\u0000");
	const stableOrderedIds = useMemo(
		() => (orderedKey ? orderedKey.split("\u0000") : []),
		[orderedKey],
	);
	const stableEligibleIds = useMemo(
		() => (eligibleKey ? eligibleKey.split("\u0000") : []),
		[eligibleKey],
	);
	const eligibleSet = useMemo(
		() => new Set(stableEligibleIds),
		[stableEligibleIds],
	);

	useEffect(() => {
		setSelectedIds((current) => {
			const next = new Set(
				[...current].filter(
					(id) => eligibleSet.has(id) && stableOrderedIds.includes(id),
				),
			);
			if (
				next.size === current.size &&
				[...next].every((id) => current.has(id))
			) {
				return current;
			}
			if (anchorId.current && !next.has(anchorId.current)) {
				anchorId.current = null;
			}
			return next;
		});
	}, [eligibleSet, stableOrderedIds]);

	const toggle = useCallback(
		(id: string, shiftKey = false) => {
			if (!eligibleSet.has(id)) return;
			setSelectedIds((current) => {
				const next = new Set(current);
				const anchorIndex = anchorId.current
					? stableOrderedIds.indexOf(anchorId.current)
					: -1;
				const targetIndex = stableOrderedIds.indexOf(id);
				const shouldSelect = !current.has(id);

				if (shiftKey && anchorIndex >= 0 && targetIndex >= 0) {
					const from = Math.min(anchorIndex, targetIndex);
					const to = Math.max(anchorIndex, targetIndex);
					for (const rangeId of stableOrderedIds.slice(from, to + 1)) {
						if (!eligibleSet.has(rangeId)) continue;
						if (shouldSelect) next.add(rangeId);
						else next.delete(rangeId);
					}
				} else if (shouldSelect) {
					next.add(id);
				} else {
					next.delete(id);
				}

				anchorId.current = id;
				return next;
			});
		},
		[eligibleSet, stableOrderedIds],
	);

	const eligibleVisibleIds = stableOrderedIds.filter((id) => eligibleSet.has(id));
	const allSelected =
		eligibleVisibleIds.length > 0 &&
		eligibleVisibleIds.every((id) => selectedIds.has(id));
	const someSelected = eligibleVisibleIds.some((id) => selectedIds.has(id));

	const toggleAll = useCallback(() => {
		setSelectedIds((current) => {
			const next = new Set(current);
			const everyVisibleSelected = eligibleVisibleIds.every((id) =>
				current.has(id),
			);
			for (const id of eligibleVisibleIds) {
				if (everyVisibleSelected) next.delete(id);
				else next.add(id);
			}
			anchorId.current = null;
			return next;
		});
	}, [eligibleVisibleIds]);

	const clear = useCallback(() => {
		anchorId.current = null;
		setSelectedIds(new Set());
	}, []);

	const remove = useCallback((ids: Iterable<string>) => {
		setSelectedIds((current) => {
			const next = new Set(current);
			for (const id of ids) next.delete(id);
			return next;
		});
	}, []);

	return {
		selectedIds,
		selectedCount: selectedIds.size,
		selectionMode: selectedIds.size > 0,
		allSelected,
		someSelected,
		toggle,
		toggleAll,
		clear,
		remove,
		isSelected: (id: string) => selectedIds.has(id),
	};
}
