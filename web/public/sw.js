"use strict";

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
			const existing = windows.find(
				(client) => new URL(client.url).origin === self.location.origin,
			);
			if (existing) {
				await existing.navigate(targetUrl);
				await existing.focus();
				return;
			}
			await self.clients.openWindow(targetUrl);
		})(),
	);
});
