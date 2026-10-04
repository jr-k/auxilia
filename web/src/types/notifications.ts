export interface SlackNotificationSettings {
	enabled: boolean;
	isConfigured: boolean;
	botTokenLast4: string | null;
	botTokenLength: number | null;
	hasSigningSecret: boolean;
	eventsUrl: string;
	interactionsUrl: string;
	slackTeamId: string | null;
}

export interface SlackNotificationSettingsUpdate {
	enabled: boolean;
	botToken?: string;
	signingSecret?: string;
}

export interface TelegramNotificationSettings {
	enabled: boolean;
	isConfigured: boolean;
	botTokenLast4: string | null;
	botUsername: string | null;
	webhookUrl: string;
}

export interface TelegramNotificationSettingsUpdate {
	enabled: boolean;
	botToken?: string;
}

export interface DiscordNotificationSettings {
	enabled: boolean;
	isConfigured: boolean;
	botTokenLast4: string | null;
	botUsername: string | null;
	applicationId: string | null;
	interactionsUrl: string;
	installUrl: string | null;
}

export interface DiscordNotificationSettingsUpdate {
	enabled: boolean;
	botToken?: string;
	applicationId?: string;
	publicKey?: string;
}

export type ExternalProvider = "telegram" | "discord";

export interface ExternalIdentity {
	provider: ExternalProvider;
	displayName: string | null;
}

export interface ChannelLinkCode {
	code: string;
	expiresIn: number;
}
