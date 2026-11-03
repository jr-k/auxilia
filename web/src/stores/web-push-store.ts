import { create } from "zustand";

import * as webPushApi from "@/lib/api/resources/web-push";
import type {
	WebPushState,
	WebPushSubscriptionPayload,
} from "@/types/web-push";

interface WebPushStore {
	state: WebPushState;
	error: string | null;
	reconcile: () => Promise<void>;
	enable: () => Promise<void>;
	disable: () => Promise<void>;
}

function isSupported(): boolean {
	return (
		typeof window !== "undefined" &&
		"serviceWorker" in navigator &&
		"PushManager" in window &&
		"Notification" in window
	);
}

function decodeApplicationServerKey(value: string): Uint8Array<ArrayBuffer> {
	const padding = "=".repeat((4 - (value.length % 4)) % 4);
	const base64 = (value + padding).replace(/-/g, "+").replace(/_/g, "/");
	const bytes = Uint8Array.from(window.atob(base64), (character) =>
		character.charCodeAt(0),
	);
	return new Uint8Array(bytes.buffer);
}

function usesApplicationServerKey(
	subscription: PushSubscription,
	key: Uint8Array<ArrayBuffer>,
): boolean {
	const current = subscription.options.applicationServerKey;
	if (!current) return false;
	const currentBytes = new Uint8Array(current);
	return (
		currentBytes.length === key.length &&
		currentBytes.every((value, index) => value === key[index])
	);
}

async function subscriptionForKey(
	serviceWorker: ServiceWorkerRegistration,
	publicKey: string,
	allowCreate: boolean,
): Promise<PushSubscription | null> {
	const applicationServerKey = decodeApplicationServerKey(publicKey);
	let subscription = await serviceWorker.pushManager.getSubscription();
	if (subscription && !usesApplicationServerKey(subscription, applicationServerKey)) {
		try {
			await webPushApi.deleteWebPushSubscription(subscription.endpoint);
		} finally {
			await subscription.unsubscribe();
			subscription = null;
		}
	}
	if (!subscription && allowCreate) {
		subscription = await serviceWorker.pushManager.subscribe({
			userVisibleOnly: true,
			applicationServerKey,
		});
	}
	return subscription;
}

function payloadFor(
	subscription: PushSubscription,
): WebPushSubscriptionPayload {
	const serialized = subscription.toJSON();
	const p256dh = serialized.keys?.p256dh;
	const auth = serialized.keys?.auth;
	if (!p256dh || !auth) {
		throw new Error("The browser returned an incomplete push subscription.");
	}
	return {
		endpoint: subscription.endpoint,
		keys: { p256dh, auth },
		userAgent: navigator.userAgent,
	};
}

async function registration(): Promise<ServiceWorkerRegistration> {
	await navigator.serviceWorker.register("/sw.js", { scope: "/" });
	return navigator.serviceWorker.ready;
}

export const useWebPushStore = create<WebPushStore>((set) => ({
	state: "loading",
	error: null,
	reconcile: async () => {
		if (!isSupported()) {
			set({ state: "unsupported", error: null });
			return;
		}
		set({ state: "loading", error: null });
		try {
			const config = await webPushApi.getWebPushConfig();
			if (!config.enabled || !config.publicKey) {
				set({ state: "not-configured", error: null });
				return;
			}
			const serviceWorker = await registration();
			const subscription = await subscriptionForKey(
				serviceWorker,
				config.publicKey,
				false,
			);
			if (!subscription) {
				set({
					state:
						Notification.permission === "denied" ? "denied" : "disabled",
					error: null,
				});
				return;
			}
			await webPushApi.upsertWebPushSubscription(payloadFor(subscription));
			set({ state: "enabled", error: null });
		} catch (error) {
			console.error("Could not reconcile Web Push:", error);
			set({
				state: "error",
				error: "Could not check notification status.",
			});
		}
	},
	enable: async () => {
		if (!isSupported()) {
			set({ state: "unsupported", error: null });
			return;
		}
		set({ state: "loading", error: null });
		try {
			const config = await webPushApi.getWebPushConfig();
			if (!config.enabled || !config.publicKey) {
				set({ state: "not-configured", error: null });
				return;
			}
			const permission = await Notification.requestPermission();
			if (permission !== "granted") {
				set({ state: "denied", error: null });
				return;
			}
			const serviceWorker = await registration();
			const subscription = await subscriptionForKey(
				serviceWorker,
				config.publicKey,
				true,
			);
			if (!subscription) {
				throw new Error("The browser did not create a push subscription.");
			}
			await webPushApi.upsertWebPushSubscription(payloadFor(subscription));
			set({ state: "enabled", error: null });
		} catch (error) {
			console.error("Could not enable Web Push:", error);
			set({
				state: "error",
				error: "Could not enable browser notifications.",
			});
		}
	},
	disable: async () => {
		if (!isSupported()) {
			set({ state: "unsupported", error: null });
			return;
		}
		set({ state: "loading", error: null });
		try {
			const serviceWorker = await registration();
			const subscription =
				await serviceWorker.pushManager.getSubscription();
			if (subscription) {
				try {
					await webPushApi.deleteWebPushSubscription(
						subscription.endpoint,
					);
				} finally {
					await subscription.unsubscribe();
				}
			}
			set({ state: "disabled", error: null });
		} catch (error) {
			console.error("Could not disable Web Push:", error);
			set({
				state: "error",
				error: "Could not disable browser notifications.",
			});
		}
	},
}));
