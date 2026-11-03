"use strict";

self.addEventListener("install", (event) => {
	event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
	event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
	event.waitUntil(
		(async () => {
			let payload;
			try {
				payload = event.data?.json();
			} catch {
				return;
			}
			if (!payload?.title || !payload?.data?.url) return;

			const windows = await self.clients.matchAll({
				type: "window",
				includeUncontrolled: true,
			});
			const threadId = payload.data.threadId;
			const matchingConversationIsActive = windows.some((client) => {
				if (!client.focused || client.visibilityState !== "visible") return false;
				const url = new URL(client.url);
				return Boolean(
					threadId &&
						decodeURIComponent(url.pathname).endsWith(
							`/chat/${threadId}`,
						),
				);
			});
			if (matchingConversationIsActive) return;

			await self.registration.showNotification(payload.title, {
				body: payload.body,
				tag: payload.tag,
				icon: payload.icon,
				badge: payload.badge,
				data: payload.data,
				renotify: true,
			});
		})(),
	);
});

self.addEventListener("notificationclick", (event) => {
	event.notification.close();
	event.waitUntil(
		(async () => {
			const relativeUrl = event.notification.data?.url;
			if (!relativeUrl) return;
			const targetUrl = new URL(relativeUrl, self.location.origin).href;
			const windows = await self.clients.matchAll({
				type: "window",
				includeUncontrolled: true,
			});
			const threadId = event.notification.data?.threadId;
			const conversation = windows.find((client) => {
				if (!threadId) return false;
				const url = new URL(client.url);
				return decodeURIComponent(url.pathname).endsWith(
					`/chat/${threadId}`,
				);
			});
			if (conversation) {
				await conversation.focus();
				return;
			}

			const existing =
				windows.find(
					(client) =>
						client.focused &&
						new URL(client.url).origin === self.location.origin,
				) ??
				windows.find(
					(client) => new URL(client.url).origin === self.location.origin,
				);
			if (existing) {
				const navigated = await existing.navigate(targetUrl);
				await (navigated ?? existing).focus();
				return;
			}
			const opened = await self.clients.openWindow(targetUrl);
			await opened?.focus();
		})(),
	);
});
