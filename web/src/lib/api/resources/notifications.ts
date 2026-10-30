import { api } from "@/lib/api/client";
import type {
	SlackNotificationSettings,
	SlackNotificationSettingsUpdate,
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
