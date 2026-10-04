import { api } from "@/lib/api/client";
import type {
	ChannelLinkCode,
	DiscordNotificationSettings,
	DiscordNotificationSettingsUpdate,
	ExternalIdentity,
	ExternalProvider,
	SlackNotificationSettings,
	SlackNotificationSettingsUpdate,
	TelegramNotificationSettings,
	TelegramNotificationSettingsUpdate,
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

export async function deleteSlackSettings(): Promise<SlackNotificationSettings> {
	const response =
		await api.delete<SlackNotificationSettings>("/notifications/slack");
	return response.data;
}

export async function getTelegramSettings(): Promise<TelegramNotificationSettings> {
	const response =
		await api.get<TelegramNotificationSettings>("/notifications/telegram");
	return response.data;
}

export async function updateTelegramSettings(
	update: TelegramNotificationSettingsUpdate,
): Promise<TelegramNotificationSettings> {
	const response = await api.put<TelegramNotificationSettings>(
		"/notifications/telegram",
		update,
	);
	return response.data;
}

export async function getDiscordSettings(): Promise<DiscordNotificationSettings> {
	const response =
		await api.get<DiscordNotificationSettings>("/notifications/discord");
	return response.data;
}

export async function updateDiscordSettings(
	update: DiscordNotificationSettingsUpdate,
): Promise<DiscordNotificationSettings> {
	const response = await api.put<DiscordNotificationSettings>(
		"/notifications/discord",
		update,
	);
	return response.data;
}

export async function createChannelLinkCode(): Promise<ChannelLinkCode> {
	const response = await api.post<ChannelLinkCode>(
		"/integrations/channels/link-code",
	);
	return response.data;
}

export async function listExternalIdentities(): Promise<ExternalIdentity[]> {
	const response = await api.get<ExternalIdentity[]>(
		"/integrations/channels/identities",
	);
	return response.data;
}

export async function unlinkExternalIdentity(
	provider: ExternalProvider,
): Promise<void> {
	await api.delete(`/integrations/channels/identities/${provider}`);
}
