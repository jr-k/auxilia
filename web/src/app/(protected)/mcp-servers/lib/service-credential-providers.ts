import type { ServiceCredentialProvider } from "@/types/mcp-servers";

export type ServiceIdentityProvider = Exclude<
	ServiceCredentialProvider,
	"custom_http_headers"
>;

export interface ServiceCredentialFields {
	tokenUrl: string;
	clientId: string;
	clientSecret: string;
	tokenEndpointAuthMethod: "client_secret_basic" | "client_secret_post";
	audience: string;
	resource: string;
	githubAppId: string;
	githubInstallationId: string;
	githubPrivateKey: string;
	awsRegion: string;
	awsService: string;
	awsAccessKeyId: string;
	awsSecretAccessKey: string;
	awsSessionToken: string;
	azureResource: string;
	azureClientId: string;
}

export const EMPTY_SERVICE_CREDENTIAL_FIELDS: ServiceCredentialFields = {
	tokenUrl: "",
	clientId: "",
	clientSecret: "",
	tokenEndpointAuthMethod: "client_secret_basic",
	audience: "",
	resource: "",
	githubAppId: "",
	githubInstallationId: "",
	githubPrivateKey: "",
	awsRegion: "",
	awsService: "execute-api",
	awsAccessKeyId: "",
	awsSecretAccessKey: "",
	awsSessionToken: "",
	azureResource: "",
	azureClientId: "",
};

export const SERVICE_IDENTITY_PROVIDERS: {
	value: ServiceIdentityProvider;
	label: string;
	description: string;
}[] = [
	{
		value: "google_service_account",
		label: "Google Service Account",
		description:
			"Signed Google credentials with automatically refreshed tokens.",
	},
	{
		value: "oauth_client_credentials",
		label: "OAuth 2.0 Client Credentials",
		description: "Standard machine-to-machine OAuth token exchange.",
	},
	{
		value: "github_app",
		label: "GitHub App",
		description:
			"Short-lived installation tokens minted from an App private key.",
	},
	{
		value: "aws_iam",
		label: "AWS IAM",
		description:
			"AWS Signature Version 4 with explicit or ambient credentials.",
	},
	{
		value: "azure_managed_identity",
		label: "Azure Managed Identity",
		description:
			"Tokens issued to the Azure identity attached to this deployment.",
	},
];

const KNOWN_SERVICE_PROVIDERS_BY_URL: Record<
	string,
	ServiceIdentityProvider[]
> = {
	"https://bigquery.googleapis.com/mcp": ["google_service_account"],
	"https://logging.googleapis.com/mcp": ["google_service_account"],
	"https://api.githubcopilot.com/mcp": ["github_app"],
};

export function knownServiceProvidersForUrl(
	url: string,
): ServiceIdentityProvider[] | undefined {
	return KNOWN_SERVICE_PROVIDERS_BY_URL[url];
}

export function providerLabel(provider: ServiceCredentialProvider): string {
	if (provider === "custom_http_headers") return "Custom HTTP";
	return (
		SERVICE_IDENTITY_PROVIDERS.find((entry) => entry.value === provider)
			?.label ?? provider
	);
}

export function buildProviderCredentialsJson(
	provider: ServiceIdentityProvider,
	fields: ServiceCredentialFields,
	googleCredentialsJson: string | undefined,
): string | undefined {
	switch (provider) {
		case "google_service_account":
			return googleCredentialsJson;
		case "oauth_client_credentials":
			return JSON.stringify({
				token_url: fields.tokenUrl.trim(),
				client_id: fields.clientId.trim(),
				client_secret: fields.clientSecret,
				token_endpoint_auth_method: fields.tokenEndpointAuthMethod,
				...(fields.audience.trim() ? { audience: fields.audience.trim() } : {}),
				...(fields.resource.trim() ? { resource: fields.resource.trim() } : {}),
			});
		case "github_app":
			return JSON.stringify({
				app_id: fields.githubAppId.trim(),
				installation_id: fields.githubInstallationId.trim(),
				private_key: fields.githubPrivateKey,
			});
		case "aws_iam":
			return JSON.stringify({
				region: fields.awsRegion.trim(),
				service: fields.awsService.trim(),
				...(fields.awsAccessKeyId.trim()
					? { access_key_id: fields.awsAccessKeyId.trim() }
					: {}),
				...(fields.awsSecretAccessKey
					? { secret_access_key: fields.awsSecretAccessKey }
					: {}),
				...(fields.awsSessionToken
					? { session_token: fields.awsSessionToken }
					: {}),
			});
		case "azure_managed_identity":
			return JSON.stringify({
				resource: fields.azureResource.trim(),
				...(fields.azureClientId.trim()
					? { client_id: fields.azureClientId.trim() }
					: {}),
			});
	}
}

export function hasProviderCredentialInput(
	provider: ServiceIdentityProvider,
	fields: ServiceCredentialFields,
	googleCredentialsJson: string | undefined,
): boolean {
	switch (provider) {
		case "google_service_account":
			return Boolean(googleCredentialsJson?.trim());
		case "oauth_client_credentials":
			return Boolean(
				fields.tokenUrl.trim() || fields.clientId.trim() || fields.clientSecret,
			);
		case "github_app":
			return Boolean(
				fields.githubAppId.trim() ||
				fields.githubInstallationId.trim() ||
				fields.githubPrivateKey,
			);
		case "aws_iam":
			return Boolean(fields.awsRegion.trim() && fields.awsService.trim());
		case "azure_managed_identity":
			return Boolean(fields.azureResource.trim());
	}
}

export function validateProviderCredentials(
	provider: ServiceIdentityProvider,
	fields: ServiceCredentialFields,
	googleCredentialsJson: string | undefined,
): string | undefined {
	switch (provider) {
		case "google_service_account":
			return googleCredentialsJson?.trim()
				? undefined
				: "A Google service account JSON file is required.";
		case "oauth_client_credentials":
			if (!fields.tokenUrl.trim()) return "Token URL is required.";
			if (!fields.clientId.trim()) return "Client ID is required.";
			if (!fields.clientSecret) return "Client secret is required.";
			return undefined;
		case "github_app":
			if (!fields.githubAppId.trim()) return "GitHub App ID is required.";
			if (!fields.githubInstallationId.trim()) {
				return "GitHub installation ID is required.";
			}
			if (!fields.githubPrivateKey) {
				return "GitHub App private key is required.";
			}
			return undefined;
		case "aws_iam":
			if (!fields.awsRegion.trim()) return "AWS region is required.";
			if (!fields.awsService.trim()) return "AWS service is required.";
			if (
				Boolean(fields.awsAccessKeyId.trim()) !==
				Boolean(fields.awsSecretAccessKey)
			) {
				return "AWS access key ID and secret access key must be provided together.";
			}
			return undefined;
		case "azure_managed_identity":
			return fields.azureResource.trim()
				? undefined
				: "Azure resource App ID URI is required.";
	}
}
