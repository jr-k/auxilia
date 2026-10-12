export type NotificationChannelType = "browser" | "slack";

export interface NotificationChannel {
	id: string;
	name: string;
	channelType: NotificationChannelType;
	enabled: boolean;
	isDefault: boolean;
	config: {
		channelId?: string;
	};
	createdAt: string;
	updatedAt: string;
}

export interface NotificationChannelCreate {
	name: string;
	channelType: NotificationChannelType;
	enabled?: boolean;
	isDefault?: boolean;
	config?: {
		channelId?: string;
	};
}

export interface NotificationChannelPatch {
	name?: string;
	enabled?: boolean;
	isDefault?: boolean;
	config?: {
		channelId?: string;
	};
}

export interface NotificationChannelTestResult {
	delivered: string[];
	failed: Record<string, string>;
}

export interface SlackNotificationSettings {
	enabled: boolean;
	isConfigured: boolean;
	botTokenLast4: string | null;
	botTokenLength: number | null;
	hasSigningSecret: boolean;
	eventsUrl: string;
	interactionsUrl: string;
}

export interface SlackNotificationSettingsUpdate {
	enabled: boolean;
	botToken?: string;
	signingSecret?: string;
}
