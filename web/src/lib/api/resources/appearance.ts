import { api } from "@/lib/api/client";
import type { WorkspaceAppearance } from "@/types/appearance";

export async function getAppearance(): Promise<WorkspaceAppearance> {
	const response = await api.get<WorkspaceAppearance>("/appearance/");
	return response.data;
}

export async function updateAppearance(
	appName: string,
): Promise<WorkspaceAppearance> {
	const response = await api.patch<WorkspaceAppearance>("/appearance/", {
		appName,
	});
	return response.data;
}

export async function uploadLogo(file: File): Promise<WorkspaceAppearance> {
	const body = new FormData();
	body.append("image", file);
	const response = await api.put<WorkspaceAppearance>("/appearance/logo", body);
	return response.data;
}

export async function deleteLogo(): Promise<WorkspaceAppearance> {
	const response = await api.delete<WorkspaceAppearance>("/appearance/logo");
	return response.data;
}

export function appearanceLogoUrl(logoRevision: string): string {
	return `/api/backend/appearance/logo?revision=${encodeURIComponent(logoRevision)}`;
}
