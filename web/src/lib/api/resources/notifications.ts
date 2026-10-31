import { api } from "@/lib/api/client";
import type {
	SlackIdentity,
	SlackLinkCode,
	SlackNotificationSettings,
	SlackNotificationSettingsUpdate,
	TelegramIdentity,
	TelegramLinkCode,
	TelegramWorkspaceSettings,
} from "@/types/notifications";

export async function getSlackSettings(): Promise<SlackNotificationSettings> {
	const response =
		await api.get<SlackNotificationSettings>("/notifications/slack");
	return response.data;
}

export async function updateSlackSettings(
	update: SlackNotificationSettingsUpdate,
): Promise<SlackNotificationSettings> {
	const response = await api.put<SlackNotificationSettings>(
		"/notifications/slack",
		update,
	);
	return response.data;
}

export async function getSlackIdentity(): Promise<SlackIdentity> {
	const response = await api.get<SlackIdentity>("/integrations/slack/account");
	return response.data;
}

export async function createSlackLinkCode(): Promise<SlackLinkCode> {
	const response = await api.post<SlackLinkCode>(
		"/integrations/slack/link-code",
	);
	return response.data;
}

export async function unlinkSlackIdentity(): Promise<void> {
	await api.delete("/integrations/slack/account");
}

export async function getTelegramSettings(): Promise<TelegramWorkspaceSettings> {
	const response =
		await api.get<TelegramWorkspaceSettings>("/notifications/telegram");
	return response.data;
}

export async function updateTelegramSettings(
	enabled: boolean,
): Promise<TelegramWorkspaceSettings> {
	const response = await api.put<TelegramWorkspaceSettings>(
		"/notifications/telegram",
		{ enabled },
	);
	return response.data;
}

export async function getTelegramIdentity(): Promise<TelegramIdentity> {
	const response = await api.get<TelegramIdentity>(
		"/integrations/telegram/account",
	);
	return response.data;
}

export async function createTelegramLinkCode(): Promise<TelegramLinkCode> {
	const response = await api.post<TelegramLinkCode>(
		"/integrations/telegram/link-code",
	);
	return response.data;
}

export async function unlinkTelegramIdentity(): Promise<void> {
	await api.delete("/integrations/telegram/account");
}
