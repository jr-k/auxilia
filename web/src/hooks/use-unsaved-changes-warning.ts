"use client";

import { useEffect } from "react";
import { requestConfirmDialog } from "@/components/providers/dialog-provider";

let dirtyEditorCount = 0;
let forcedNavigationAllowed = false;

function resetPreparedNavigationIfStillMounted(): void {
	window.setTimeout(() => {
		if (hasUnsavedChanges()) cancelPreparedNavigation();
	}, 1000);
}

export function hasUnsavedChanges(): boolean {
	return dirtyEditorCount > 0;
}

export async function prepareToDiscardUnsavedChanges(): Promise<boolean> {
	if (!hasUnsavedChanges()) return true;
	const accepted = await requestConfirmDialog({
		title: "Discard unsaved changes?",
		description: "Your changes will be lost if you leave this page.",
		confirmLabel: "Discard changes",
		destructive: true,
	});
	if (!accepted) return false;
	forcedNavigationAllowed = true;
	return true;
}

export function cancelPreparedNavigation(): void {
	forcedNavigationAllowed = false;
}

export async function navigateWithUnsavedChanges(
	navigate: () => void | Promise<void>,
): Promise<boolean> {
	if (!(await prepareToDiscardUnsavedChanges())) return false;
	try {
		await navigate();
		resetPreparedNavigationIfStillMounted();
	} catch (error) {
		cancelPreparedNavigation();
		throw error;
	}
	return true;
}

type NavigationEventLike = Event & {
	navigationType: string;
	destination: { url: string };
};

type NavigationLike = {
	addEventListener: (
		type: "navigate",
		listener: (event: NavigationEventLike) => void,
	) => void;
	removeEventListener: (
		type: "navigate",
		listener: (event: NavigationEventLike) => void,
	) => void;
};

export function useUnsavedChangesWarning(isDirty: boolean): void {
	useEffect(() => {
		if (!isDirty) return;
		dirtyEditorCount += 1;
		const warn = (event: BeforeUnloadEvent) => {
			if (!forcedNavigationAllowed) event.preventDefault();
		};
		const warnInternalNavigation = (event: MouseEvent) => {
			if (
				forcedNavigationAllowed ||
				event.defaultPrevented ||
				event.button !== 0 ||
				event.metaKey ||
				event.ctrlKey ||
				event.shiftKey ||
				event.altKey
			) {
				return;
			}
			const target = event.target;
			const anchor =
				target instanceof Element ? target.closest<HTMLAnchorElement>("a[href]") : null;
			if (!anchor || anchor.target === "_blank" || anchor.hasAttribute("download")) {
				return;
			}
			const destination = new URL(anchor.href, window.location.href);
			if (
				destination.origin !== window.location.origin ||
				destination.href === window.location.href
			) {
				return;
			}
			event.preventDefault();
			event.stopImmediatePropagation();
			void navigateWithUnsavedChanges(() => {
				anchor.click();
			});
		};
		const navigation = (
			window as typeof window & { navigation?: NavigationLike }
		).navigation;
		const warnHistoryTraversal = (event: NavigationEventLike) => {
			if (
				forcedNavigationAllowed ||
				event.navigationType !== "traverse" ||
				event.destination.url === window.location.href
			) {
				return;
			}
			const destinationUrl = event.destination.url;
			event.preventDefault();
			void navigateWithUnsavedChanges(() => {
				window.location.assign(destinationUrl);
			});
		};
		window.addEventListener("beforeunload", warn);
		document.addEventListener("click", warnInternalNavigation, true);
		navigation?.addEventListener("navigate", warnHistoryTraversal);
		return () => {
			window.removeEventListener("beforeunload", warn);
			document.removeEventListener("click", warnInternalNavigation, true);
			navigation?.removeEventListener("navigate", warnHistoryTraversal);
			dirtyEditorCount = Math.max(0, dirtyEditorCount - 1);
			if (dirtyEditorCount === 0) forcedNavigationAllowed = false;
		};
	}, [isDirty]);
}
