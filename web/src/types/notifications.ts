export interface SlackNotificationSettings {
	enabled: boolean;
}

export interface SlackNotificationSettingsUpdate {
	enabled: boolean;
}

export interface TelegramWorkspaceSettings {
	enabled: boolean;
}

export interface TelegramIdentity {
	linked: boolean;
	username: string | null;
	displayName: string | null;
}

export interface TelegramLinkCode {
	code: string;
	expiresIn: number;
	deepLinkUrl: string | null;
}
