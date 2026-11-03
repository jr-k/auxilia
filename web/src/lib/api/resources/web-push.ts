import { api } from "@/lib/api/client";
import type {
	WebPushConfig,
	WebPushSubscriptionPayload,
	WebPushSubscriptionStatus,
} from "@/types/web-push";

export async function getWebPushConfig(): Promise<WebPushConfig> {
	const response = await api.get<WebPushConfig>("/notifications/web-push");
	return response.data;
}

export async function upsertWebPushSubscription(
	subscription: WebPushSubscriptionPayload,
): Promise<WebPushSubscriptionStatus> {
	const response = await api.put<WebPushSubscriptionStatus>(
		"/notifications/web-push/subscriptions",
		subscription,
	);
	return response.data;
}

export async function deleteWebPushSubscription(
	endpoint: string,
): Promise<WebPushSubscriptionStatus> {
	const response = await api.delete<WebPushSubscriptionStatus>(
		"/notifications/web-push/subscriptions",
		{ data: { endpoint } },
	);
	return response.data;
}
