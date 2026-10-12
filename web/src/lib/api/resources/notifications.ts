import { api } from "@/lib/api/client";
import type {
	NotificationChannel,
	NotificationChannelCreate,
	NotificationChannelPatch,
	NotificationChannelTestResult,
	SlackNotificationSettings,
	SlackNotificationSettingsUpdate,
} from "@/types/notifications";

export async function listChannels(): Promise<NotificationChannel[]> {
	const response =
		await api.get<NotificationChannel[]>("/notifications/channels");
	return response.data;
}

export async function createChannel(
	data: NotificationChannelCreate,
): Promise<NotificationChannel> {
	const response = await api.post<NotificationChannel>(
		"/notifications/channels",
		data,
	);
	return response.data;
}

export async function updateChannel(
	channelId: string,
	data: NotificationChannelPatch,
): Promise<NotificationChannel> {
	const response = await api.patch<NotificationChannel>(
		`/notifications/channels/${channelId}`,
		data,
	);
	return response.data;
}

export async function deleteChannel(channelId: string): Promise<void> {
	await api.delete(`/notifications/channels/${channelId}`);
}

export async function testChannel(
	channelId: string,
): Promise<NotificationChannelTestResult> {
	const response = await api.post<NotificationChannelTestResult>(
		`/notifications/channels/${channelId}/test`,
	);
	return response.data;
}

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
