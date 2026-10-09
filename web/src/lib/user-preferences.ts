"use client";

import { useSyncExternalStore } from "react";

const RESPONSE_SOUND_KEY = "auxilia:play-response-sound";
const SHOW_SHORTCUTS_IN_MENU_KEY = "auxilia:show-shortcuts-in-menu";
const responseSoundListeners = new Set<() => void>();
const shortcutsMenuListeners = new Set<() => void>();
let responseSoundFallback = true;
let shortcutsMenuFallback = true;

function readPreference(key: string, fallback: boolean): boolean {
	if (typeof window === "undefined") return fallback;
	try {
		const value = window.localStorage.getItem(key);
		return value === null ? fallback : value !== "false";
	} catch {
		return fallback;
	}
}

function readResponseSoundPreference(): boolean {
	responseSoundFallback = readPreference(RESPONSE_SOUND_KEY, responseSoundFallback);
	return responseSoundFallback;
}

function readShowShortcutsInMenuPreference(): boolean {
	shortcutsMenuFallback = readPreference(
		SHOW_SHORTCUTS_IN_MENU_KEY,
		shortcutsMenuFallback,
	);
	return shortcutsMenuFallback;
}

function subscribeToPreference(
	key: string,
	listeners: Set<() => void>,
	listener: () => void,
): () => void {
	listeners.add(listener);
	const handleStorage = (event: StorageEvent) => {
		if (event.key === null || event.key === key) listener();
	};
	window.addEventListener("storage", handleStorage);
	return () => {
		listeners.delete(listener);
		window.removeEventListener("storage", handleStorage);
	};
}

function subscribeToResponseSound(listener: () => void): () => void {
	return subscribeToPreference(
		RESPONSE_SOUND_KEY,
		responseSoundListeners,
		listener,
	);
}

function subscribeToShortcutsMenu(listener: () => void): () => void {
	return subscribeToPreference(
		SHOW_SHORTCUTS_IN_MENU_KEY,
		shortcutsMenuListeners,
		listener,
	);
}

export function useResponseSoundEnabled(): boolean {
	return useSyncExternalStore(
		subscribeToResponseSound,
		readResponseSoundPreference,
		() => true,
	);
}

export function useShowShortcutsInMenu(): boolean {
	return useSyncExternalStore(
		subscribeToShortcutsMenu,
		readShowShortcutsInMenuPreference,
		() => true,
	);
}

export function isResponseSoundEnabled(): boolean {
	return readResponseSoundPreference();
}

export function setResponseSoundEnabled(enabled: boolean): void {
	responseSoundFallback = enabled;
	try {
		window.localStorage.setItem(RESPONSE_SOUND_KEY, String(enabled));
	} catch {
		// Keep the in-memory preference when storage is unavailable.
	}
	responseSoundListeners.forEach((listener) => {
		listener();
	});
}

export function setShowShortcutsInMenu(enabled: boolean): void {
	shortcutsMenuFallback = enabled;
	try {
		window.localStorage.setItem(SHOW_SHORTCUTS_IN_MENU_KEY, String(enabled));
	} catch {
		// Keep the in-memory preference when storage is unavailable.
	}
	shortcutsMenuListeners.forEach((listener) => {
		listener();
	});
}
