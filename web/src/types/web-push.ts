export interface WebPushConfig {
	enabled: boolean;
	publicKey: string | null;
}

export interface WebPushSubscriptionPayload {
	endpoint: string;
	keys: {
		p256dh: string;
		auth: string;
	};
	userAgent: string;
}

export interface WebPushSubscriptionStatus {
	subscribed: boolean;
}

export type WebPushState =
	| "loading"
	| "unsupported"
	| "not-configured"
	| "denied"
	| "disabled"
	| "enabled"
	| "error";
