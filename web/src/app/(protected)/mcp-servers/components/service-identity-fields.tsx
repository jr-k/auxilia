"use client";

import { useState } from "react";
import { Eye, EyeOff, Upload } from "lucide-react";
import type { ServiceCredentialProvider } from "@/types/mcp-servers";
import {
	SERVICE_IDENTITY_PROVIDERS,
	ServiceCredentialFields,
	ServiceIdentityProvider,
} from "../lib/service-credential-providers";

const LABEL_CLASS = "text-[13px] font-semibold text-foreground";
const INPUT_CLASS =
	"w-full rounded-lg border border-input bg-card px-3 py-[9px] text-[13.5px] font-medium text-foreground outline-none transition-[border-color,box-shadow] placeholder:text-meta dark:placeholder:text-panel-dim focus:border-petrol focus:shadow-[0_0_0_3px_rgba(22,96,110,0.10)]";
const MONO_INPUT_CLASS = `${INPUT_CLASS} font-mono text-[12.5px] font-normal`;

interface ServiceIdentityFieldsProps {
	provider: ServiceIdentityProvider;
	allowedProviders?: ServiceCredentialProvider[];
	fields: ServiceCredentialFields;
	scopes: string;
	credentialFileName: string | null;
	error?: string;
	replacement?: boolean;
	onProviderChange: (provider: ServiceIdentityProvider) => void;
	onFieldsChange: (fields: ServiceCredentialFields) => void;
	onScopesChange: (scopes: string) => void;
	onGoogleCredentialsChange: (contents: string, fileName: string) => void;
	onError: (message: string) => void;
}

function Field({
	label,
	value,
	placeholder,
	type = "text",
	optional = false,
	onChange,
}: {
	label: string;
	value: string;
	placeholder?: string;
	type?: "text" | "password";
	optional?: boolean;
	onChange: (value: string) => void;
}) {
	return (
		<div className="flex flex-col gap-[7px]">
			<label className={LABEL_CLASS}>
				{label}
				{optional && (
					<span className="font-normal text-meta dark:text-panel-dim">
						{" "}
						optional
					</span>
				)}
			</label>
			<input
				type={type}
				value={value}
				placeholder={placeholder}
				onChange={(event) => {
					onChange(event.target.value);
				}}
				className={MONO_INPUT_CLASS}
			/>
		</div>
	);
}

export function ServiceIdentityFields({
	provider,
	allowedProviders,
	fields,
	scopes,
	credentialFileName,
	error,
	replacement = false,
	onProviderChange,
	onFieldsChange,
	onScopesChange,
	onGoogleCredentialsChange,
	onError,
}: ServiceIdentityFieldsProps) {
	const [showSecrets, setShowSecrets] = useState(false);
	const providers =
		allowedProviders && allowedProviders.length > 0
			? SERVICE_IDENTITY_PROVIDERS.filter((entry) =>
					allowedProviders.includes(entry.value),
				)
			: SERVICE_IDENTITY_PROVIDERS;
	const selected = SERVICE_IDENTITY_PROVIDERS.find(
		(entry) => entry.value === provider,
	);
	const update = (field: keyof ServiceCredentialFields, value: string) => {
		onFieldsChange({ ...fields, [field]: value });
	};

	const readFile = (
		file: File | undefined,
		onRead: (contents: string) => void,
	) => {
		if (!file) return;
		void file
			.text()
			.then(onRead)
			.catch(() => {
				onError("Could not read this credential file.");
			});
	};

	return (
		<>
			<div className="flex flex-col gap-[7px]">
				<label htmlFor="mcp-service-provider" className={LABEL_CLASS}>
					Credential provider
				</label>
				<select
					id="mcp-service-provider"
					value={provider}
					onChange={(event) => {
						onProviderChange(event.target.value as ServiceIdentityProvider);
					}}
					className={INPUT_CLASS}
				>
					{providers.map((entry) => (
						<option key={entry.value} value={entry.value}>
							{entry.label}
						</option>
					))}
				</select>
				{selected && (
					<span className="text-[12px] leading-[1.5] text-meta dark:text-panel-dim">
						{selected.description}
					</span>
				)}
			</div>

			{provider === "google_service_account" && (
				<>
					<div className="flex flex-col gap-[7px]">
						<span className={LABEL_CLASS}>
							{replacement ? "Replacement credential file" : "Credential file"}
						</span>
						<label
							htmlFor="mcp-service-credentials"
							className={`flex cursor-pointer items-center gap-3 rounded-[10px] border border-dashed px-4 py-3 transition-colors hover:border-petrol hover:bg-card ${
								error ? "border-destructive" : "border-input"
							}`}
						>
							<span className="flex size-8 shrink-0 items-center justify-center rounded-[8px] bg-card text-petrol">
								<Upload className="size-4" />
							</span>
							<span className="min-w-0 flex-1">
								<span className="block truncate text-[13px] font-semibold text-foreground">
									{credentialFileName ??
										(replacement
											? "Choose a replacement JSON file"
											: "Choose a JSON credential file")}
								</span>
								<span className="mt-0.5 block text-[11.5px] text-meta dark:text-panel-dim">
									{credentialFileName
										? "Ready to encrypt and save"
										: replacement
											? "Leave empty to keep the stored credential"
											: "The file stays write-only after upload"}
								</span>
							</span>
						</label>
						<input
							id="mcp-service-credentials"
							type="file"
							accept=".json,application/json"
							className="sr-only"
							onChange={(event) => {
								const file = event.target.files?.[0];
								event.target.value = "";
								readFile(file, (contents) => {
									if (file) onGoogleCredentialsChange(contents, file.name);
								});
							}}
						/>
					</div>
					<Field
						label="OAuth scopes"
						value={scopes}
						placeholder="https://www.googleapis.com/auth/cloud-platform"
						onChange={onScopesChange}
					/>
				</>
			)}

			{provider === "oauth_client_credentials" && (
				<>
					<Field
						label="Token URL"
						value={fields.tokenUrl}
						placeholder="https://identity.example.com/oauth/token"
						onChange={(value) => {
							update("tokenUrl", value);
						}}
					/>
					<div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
						<Field
							label="Client ID"
							value={fields.clientId}
							onChange={(value) => {
								update("clientId", value);
							}}
						/>
						<Field
							label="Client secret"
							type={showSecrets ? "text" : "password"}
							value={fields.clientSecret}
							onChange={(value) => {
								update("clientSecret", value);
							}}
						/>
					</div>
					<div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
						<Field
							label="Audience"
							optional
							value={fields.audience}
							onChange={(value) => {
								update("audience", value);
							}}
						/>
						<Field
							label="Resource"
							optional
							value={fields.resource}
							onChange={(value) => {
								update("resource", value);
							}}
						/>
					</div>
					<div className="flex flex-col gap-[7px]">
						<label className={LABEL_CLASS}>Token endpoint authentication</label>
						<select
							value={fields.tokenEndpointAuthMethod}
							onChange={(event) => {
								update("tokenEndpointAuthMethod", event.target.value);
							}}
							className={INPUT_CLASS}
						>
							<option value="client_secret_basic">Client secret Basic</option>
							<option value="client_secret_post">Client secret POST</option>
						</select>
					</div>
					<Field
						label="OAuth scopes"
						optional
						value={scopes}
						onChange={onScopesChange}
					/>
				</>
			)}

			{provider === "github_app" && (
				<>
					<div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
						<Field
							label="GitHub App ID"
							value={fields.githubAppId}
							onChange={(value) => {
								update("githubAppId", value);
							}}
						/>
						<Field
							label="Installation ID"
							value={fields.githubInstallationId}
							onChange={(value) => {
								update("githubInstallationId", value);
							}}
						/>
					</div>
					<div className="flex flex-col gap-[7px]">
						<span className={LABEL_CLASS}>Private key</span>
						<label
							htmlFor="mcp-github-private-key"
							className="flex cursor-pointer items-center gap-3 rounded-[10px] border border-dashed border-input px-4 py-3 transition-colors hover:border-petrol hover:bg-card"
						>
							<Upload className="size-4 text-petrol" />
							<span className="truncate text-[13px] font-semibold text-foreground">
								{fields.githubPrivateKey
									? "Private key ready to encrypt"
									: replacement
										? "Choose a replacement .pem file"
										: "Choose the GitHub App .pem file"}
							</span>
						</label>
						<input
							id="mcp-github-private-key"
							type="file"
							accept=".pem,application/x-pem-file"
							className="sr-only"
							onChange={(event) => {
								const file = event.target.files?.[0];
								event.target.value = "";
								readFile(file, (contents) => {
									update("githubPrivateKey", contents);
								});
							}}
						/>
					</div>
				</>
			)}

			{provider === "aws_iam" && (
				<>
					<div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
						<Field
							label="AWS region"
							value={fields.awsRegion}
							placeholder="eu-west-1"
							onChange={(value) => {
								update("awsRegion", value);
							}}
						/>
						<Field
							label="AWS service"
							value={fields.awsService}
							placeholder="execute-api"
							onChange={(value) => {
								update("awsService", value);
							}}
						/>
					</div>
					<Field
						label="Access key ID"
						optional
						value={fields.awsAccessKeyId}
						onChange={(value) => {
							update("awsAccessKeyId", value);
						}}
					/>
					<Field
						label="Secret access key"
						optional
						type={showSecrets ? "text" : "password"}
						value={fields.awsSecretAccessKey}
						onChange={(value) => {
							update("awsSecretAccessKey", value);
						}}
					/>
					<Field
						label="Session token"
						optional
						type={showSecrets ? "text" : "password"}
						value={fields.awsSessionToken}
						onChange={(value) => {
							update("awsSessionToken", value);
						}}
					/>
					<span className="text-[12px] leading-[1.5] text-meta dark:text-panel-dim">
						Leave access keys empty to use Auxilia&apos;s ambient AWS credential
						chain, including an attached IAM role.
					</span>
				</>
			)}

			{provider === "azure_managed_identity" && (
				<>
					<Field
						label="Resource App ID URI"
						value={fields.azureResource}
						placeholder="https://management.azure.com/"
						onChange={(value) => {
							update("azureResource", value);
						}}
					/>
					<Field
						label="User-assigned identity client ID"
						optional
						value={fields.azureClientId}
						onChange={(value) => {
							update("azureClientId", value);
						}}
					/>
					<span className="text-[12px] leading-[1.5] text-meta dark:text-panel-dim">
						Leave the client ID empty to use the system-assigned identity
						attached to the Auxilia deployment.
					</span>
				</>
			)}

			{provider !== "google_service_account" &&
				(provider === "oauth_client_credentials" || provider === "aws_iam") && (
					<button
						type="button"
						onClick={() => {
							setShowSecrets((current) => !current);
						}}
						className="inline-flex w-fit cursor-pointer items-center gap-1.5 text-[12px] font-semibold text-petrol hover:underline dark:text-panel-terminal"
					>
						{showSecrets ? (
							<EyeOff className="size-3.5" />
						) : (
							<Eye className="size-3.5" />
						)}
						{showSecrets ? "Hide secrets" : "Show secrets"}
					</button>
				)}

			{error && <span className="text-[12.5px] text-destructive">{error}</span>}
		</>
	);
}
