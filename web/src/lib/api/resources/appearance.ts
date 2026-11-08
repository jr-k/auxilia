import { api } from "@/lib/api/client";
import type { InstanceAppearance } from "@/types/appearance";

export async function getAppearance(): Promise<InstanceAppearance> {
	const response = await api.get<InstanceAppearance>("/appearance/");
	return response.data;
}

export async function updateAppearance(
	appName: string,
): Promise<InstanceAppearance> {
	const response = await api.patch<InstanceAppearance>("/appearance/", {
		appName,
	});
	return response.data;
}

export async function uploadLogo(file: File): Promise<InstanceAppearance> {
	const body = new FormData();
	body.append("image", file);
	const response = await api.put<InstanceAppearance>("/appearance/logo", body);
	return response.data;
}

export async function deleteLogo(): Promise<InstanceAppearance> {
	const response = await api.delete<InstanceAppearance>("/appearance/logo");
	return response.data;
}

export function appearanceLogoUrl(logoRevision: string): string {
	return `/api/backend/appearance/logo?revision=${encodeURIComponent(logoRevision)}`;
}

export async function uploadNotificationBadge(
	file: File,
): Promise<InstanceAppearance> {
	const body = new FormData();
	body.append("image", file);
	const response = await api.put<InstanceAppearance>(
		"/appearance/notification-badge",
		body,
	);
	return response.data;
}

export async function deleteNotificationBadge(): Promise<InstanceAppearance> {
	const response = await api.delete<InstanceAppearance>(
		"/appearance/notification-badge",
	);
	return response.data;
}

export function appearanceNotificationBadgeUrl(
	revision: string,
): string {
	return `/api/backend/appearance/notification-badge?revision=${encodeURIComponent(revision)}`;
}
