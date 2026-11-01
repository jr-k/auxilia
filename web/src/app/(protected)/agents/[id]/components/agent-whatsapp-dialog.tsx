"use client";

import { useState } from "react";
import {
	ArrowLeft,
	ArrowRight,
	ArrowUpRight,
	Check,
	Copy,
	PackageOpen,
	Unplug,
} from "lucide-react";
import { WhatsAppLogo } from "@/components/whatsapp-logo";
import {
	Dialog,
	DialogButton,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { DropdownMenu } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import type {
	AgentWhatsAppSettings,
	AgentWhatsAppSettingsUpdate,
	WhatsAppToolDiscoveryMode,
} from "@/types/agents";

interface Props {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	settings: AgentWhatsAppSettings;
	saving: boolean;
	error: string | null;
	onSave: (update: AgentWhatsAppSettingsUpdate) => Promise<void>;
	onDisconnect?: () => Promise<void>;
}

const discoveryOptions: Array<{
	value: WhatsAppToolDiscoveryMode;
	label: string;
	description: string;
}> = [
	{ value: "disabled", label: "Eager", description: "Load every MCP schema" },
	{ value: "lazy", label: "Lazy", description: "Choose servers per prompt" },
	{ value: "local", label: "Precision", description: "Retrieve tools adaptively" },
	{
		value: "all_capabilities",
		label: "Enable all capabilities",
		description: "Force all configured resources",
	},
];

function CopyValue({ label, value }: { label: string; value: string }) {
	const [copied, setCopied] = useState(false);
	const copy = () => {
		void navigator.clipboard.writeText(value).then(() => {
			setCopied(true);
			window.setTimeout(() => {
				setCopied(false);
			}, 1600);
		});
	};

	return (
		<div className="overflow-hidden rounded-[8px] border border-border bg-background dark:border-white/10">
			<div className="flex items-center justify-between gap-3 border-b border-border px-3 py-1.5 dark:border-white/10">
				<span className="text-[10.5px] font-semibold text-meta">{label}</span>
				<button
					type="button"
					onClick={copy}
					className="flex shrink-0 cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-[5px] px-2 py-1 text-[12px] font-semibold text-petrol transition-colors hover:bg-petrol/10"
				>
					{copied ? <Check className="size-3" /> : <Copy className="size-3" />}
					{copied ? "Copied" : "Copy"}
				</button>
			</div>
			<code className="block break-all px-3 py-2.5 text-[12px] text-foreground">
				{value}
			</code>
		</div>
	);
}

function AgentWhatsAppSetupGuide({
	settings,
	onDone,
}: {
	settings: AgentWhatsAppSettings;
	onDone: () => void;
}) {
	const [activeStep, setActiveStep] = useState(0);
	const badgeClass =
		"rounded-[4px] border border-border bg-background px-1.5 py-0.5 font-mono text-[11.5px] text-foreground dark:border-white/10";
	const steps = [
		{
			title: "Create a Meta app",
			body: (
				<div className="space-y-3">
					<p>
						Open{" "}
						<a
							href="https://developers.facebook.com/apps/"
							target="_blank"
							rel="noreferrer"
							className="inline-flex items-center gap-1 font-semibold text-petrol hover:underline"
						>
							Meta for Developers
							<ArrowUpRight className="size-3" />
						</a>
						, create a business app, then add the{" "}
						<strong>WhatsApp</strong> product.
					</p>
					<p>
						Use a dedicated Meta app and phone number for this agent so its
						identity and webhook lifecycle remain isolated.
					</p>
				</div>
			),
		},
		{
			title: "Connect the phone number",
			body: (
				<div className="space-y-3">
					<p>
						In <strong>WhatsApp / API Setup</strong>, add or select the phone
						number this agent will use.
					</p>
					<p>
						Copy the <strong>Phone number ID</strong> and the{" "}
						<strong>WhatsApp Business Account ID</strong>. These are numeric
						identifiers, not the displayed phone number.
					</p>
				</div>
			),
		},
		{
			title: "Create a permanent token",
			body: (
				<div className="space-y-3">
					<p>
						In Meta Business Settings, create a system user and grant it access
						to the app and WhatsApp account. Generate a permanent access token
						with <code className={badgeClass}>whatsapp_business_messaging</code>{" "}
						and{" "}
						<code className={badgeClass}>whatsapp_business_management</code>.
					</p>
					<p>
						Do not use the temporary token from the API Setup page for a
						production connection.
					</p>
				</div>
			),
		},
		{
			title: "Configure the webhook",
			body: (
				<div className="space-y-3">
					<p>
						In <strong>WhatsApp / Configuration</strong>, choose{" "}
						<strong>Edit</strong> under Webhook and enter these values.
					</p>
					<CopyValue label="Callback URL" value={settings.webhookUrl} />
					{settings.verifyToken ? (
						<CopyValue label="Verify token" value={settings.verifyToken} />
					) : (
						<p className="rounded-[8px] border border-amber-300/60 bg-amber-50 px-3 py-2 text-[11.5px] text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
							Save the connection first, then reopen this guide to copy the
							connection-specific callback URL and verify token.
						</p>
					)}
					<p>
						After Meta verifies the callback, subscribe the WhatsApp Business
						Account to the <code className={badgeClass}>messages</code> field.
					</p>
				</div>
			),
		},
		{
			title: "Copy the app secret",
			body: (
				<div className="space-y-3">
					<p>
						Open <strong>App settings / Basic</strong>, reveal the{" "}
						<strong>App secret</strong>, and copy it. Auxilia uses it to verify
						that webhook requests came from Meta.
					</p>
					<p>
						Keep the app secret and access token private. Both are stored
						encrypted and are never returned by the API.
					</p>
				</div>
			),
		},
		{
			title: "Save and test",
			body: (
				<div className="space-y-3">
					<p>
						Return to the configuration form and enter the access token, app
						secret, business account ID, and phone number ID.
					</p>
					<p>
						Enable the connection, save it, then send a WhatsApp message to the
						connected number. Meta may require an approved template when the
						agent starts a conversation outside the 24-hour customer service
						window.
					</p>
				</div>
			),
		},
	];
	const step = steps[activeStep];
	const isLastStep = activeStep === steps.length - 1;

	return (
		<div className="grid min-h-[410px] grid-cols-[158px_minmax(0,1fr)] sm:grid-cols-[220px_minmax(0,1fr)]">
			<nav
				aria-label="WhatsApp setup steps"
				className="border-r border-border bg-card/45 py-4 dark:border-white/10 dark:bg-white/[0.025]"
			>
				<p className="mb-2 px-4 text-[10.5px] font-semibold text-meta sm:px-5">
					Meta Cloud API setup
				</p>
				<ol>
					{steps.map((candidate, index) => (
						<li key={candidate.title}>
							<button
								type="button"
								aria-current={activeStep === index ? "step" : undefined}
								onClick={() => {
									setActiveStep(index);
								}}
								className={`group flex w-full cursor-pointer items-center gap-2.5 px-3 py-3 text-left transition-colors sm:px-4 ${
									activeStep === index ? "bg-petrol/[0.07]" : "hover:bg-hover"
								}`}
							>
								<span
									className={`flex size-6 shrink-0 items-center justify-center rounded-full border font-mono text-[10.5px] font-semibold ${
										activeStep === index
											? "border-petrol bg-petrol text-white"
											: "border-border bg-card text-meta dark:border-white/10"
									}`}
								>
									{index + 1}
								</span>
								<span
									className={`min-w-0 text-[12.5px] leading-[1.3] font-semibold ${
										activeStep === index ? "text-foreground" : "text-subtle"
									}`}
								>
									{candidate.title}
								</span>
							</button>
						</li>
					))}
				</ol>
			</nav>
			<section
				aria-live="polite"
				className="flex min-w-0 flex-col px-4 py-5 sm:px-6"
			>
				<div className="flex-1">
					<h3 className="text-[18px] font-bold text-foreground">{step.title}</h3>
					<div className="mt-3 text-[13.5px] leading-[1.65] text-subtle dark:text-panel-body">
						{step.body}
					</div>
				</div>
				<div className="mt-6 flex items-end justify-between gap-3 border-t border-border pt-4 dark:border-white/10">
					<p className="max-w-[260px] text-[11px] leading-[1.45] text-meta">
						Each WhatsApp number is connected to this agent only.
					</p>
					<DialogButton
						className="shrink-0 whitespace-nowrap"
						onClick={() => {
							if (isLastStep) {
								onDone();
								return;
							}
							setActiveStep((current) => current + 1);
						}}
					>
						{isLastStep ? "Done" : "Next"}
						{!isLastStep && <ArrowRight className="size-3.5" />}
					</DialogButton>
				</div>
			</section>
		</div>
	);
}

export default function AgentWhatsAppDialog({
	open,
	onOpenChange,
	settings,
	saving,
	error,
	onSave,
	onDisconnect,
}: Props) {
	const [view, setView] = useState<"configuration" | "guide">("configuration");
	const [accessToken, setAccessToken] = useState("");
	const [appSecret, setAppSecret] = useState("");
	const [businessAccountId, setBusinessAccountId] = useState(
		settings.businessAccountId ?? "",
	);
	const [phoneNumberId, setPhoneNumberId] = useState(
		settings.phoneNumberId ?? "",
	);
	const [enabled, setEnabled] = useState(settings.enabled);
	const [showTypingIndicator, setShowTypingIndicator] = useState(
		settings.showTypingIndicator,
	);
	const [showToolCallouts, setShowToolCallouts] = useState(
		settings.showToolCallouts,
	);
	const [showAuxiliaLink, setShowAuxiliaLink] = useState(
		settings.showAuxiliaLink,
	);
	const [toolDiscoveryMode, setToolDiscoveryMode] =
		useState<WhatsAppToolDiscoveryMode>(settings.toolDiscoveryMode);

	const hasNewSecrets = Boolean(accessToken.trim() || appSecret.trim());
	const secretsComplete = Boolean(accessToken.trim() && appSecret.trim());
	const identifiersComplete = Boolean(
		businessAccountId.trim() && phoneNumberId.trim(),
	);
	const canSave =
		!saving &&
		identifiersComplete &&
		(settings.isConfigured || secretsComplete) &&
		(!hasNewSecrets || secretsComplete);

	const submit = () => {
		if (!canSave) return;
		void onSave({
			enabled,
			showTypingIndicator,
			showToolCallouts,
			showAuxiliaLink,
			toolDiscoveryMode,
			businessAccountId: businessAccountId.trim(),
			phoneNumberId: phoneNumberId.trim(),
			...(secretsComplete
				? {
						accessToken: accessToken.trim(),
						appSecret: appSecret.trim(),
					}
				: {}),
		});
	};

	const handleOpenChange = (nextOpen: boolean) => {
		if (!nextOpen) setView("configuration");
		onOpenChange(nextOpen);
	};

	return (
		<Dialog open={open} onOpenChange={saving ? undefined : handleOpenChange}>
			<DialogContent
				className={`gap-0 overflow-hidden p-0 ${
					view === "guide" ? "sm:max-w-[700px]" : "sm:max-w-[580px]"
				}`}
			>
				<DialogHeader className="border-b border-border px-5 py-4 pr-14 dark:border-white/10 sm:px-6">
					<div className="flex items-center gap-3">
						{view === "guide" ? (
							<button
								type="button"
								onClick={() => {
									setView("configuration");
								}}
								className="flex size-9 shrink-0 cursor-pointer items-center justify-center rounded-[9px] border border-border bg-card text-subtle transition-colors hover:text-foreground"
								aria-label="Back to configuration"
							>
								<ArrowLeft className="size-4" />
							</button>
						) : (
							<span className="flex size-9 shrink-0 items-center justify-center rounded-[9px] border border-border bg-card shadow-sm dark:border-white/10">
								<WhatsAppLogo className="size-[62%]" />
							</span>
						)}
						<div className="min-w-0">
							<DialogTitle>
								{view === "guide"
									? "Connect the Meta Cloud API"
									: settings.isConfigured
										? "WhatsApp connection"
										: "Add WhatsApp side-channel"}
							</DialogTitle>
							<DialogDescription className="mt-0.5">
								{view === "guide"
									? "Give this agent a dedicated Meta app and phone number."
									: settings.isConfigured
										? `Connected to ${settings.displayPhoneNumber ?? settings.verifiedName ?? "a WhatsApp number"}.`
										: "Receive and answer messages through the WhatsApp Cloud API."}
							</DialogDescription>
						</div>
					</div>
				</DialogHeader>

				{view === "configuration" ? (
					<>
						<div className="max-h-[68vh] space-y-5 overflow-y-auto px-5 py-5 sm:px-6">
							{!settings.workspaceEnabled && (
								<p className="rounded-[8px] border border-amber-300/60 bg-amber-50 px-3 py-2 text-[11.5px] text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
									WhatsApp is disabled for this workspace. An administrator
									must enable it in Settings / Integrations / Messaging.
								</p>
							)}

							<button
								type="button"
								onClick={() => {
									setView("guide");
								}}
								className="group flex w-full cursor-pointer items-center gap-3 rounded-[10px] border border-petrol/30 bg-petrol/[0.07] p-4 text-left transition-all hover:border-petrol/45 hover:bg-petrol/[0.11] dark:border-petrol/60 dark:bg-petrol/25 dark:hover:bg-petrol/35"
							>
								<span className="min-w-0 flex-1">
									<span className="flex items-center gap-2">
										<span className="block text-[12.5px] font-semibold text-foreground">
											{settings.isConfigured
												? "Review the Meta setup"
												: "Set up the Meta Cloud API"}
										</span>
										{!settings.isConfigured && (
											<span className="rounded-full bg-petrol/10 px-1.5 py-0.5 text-[9px] font-bold text-petrol dark:bg-panel-terminal/15 dark:text-panel-terminal">
												Required
											</span>
										)}
									</span>
									<span className="mt-0.5 block text-[10.5px] text-subtle dark:text-panel-body">
										Create the app, connect a number, and configure its webhook.
									</span>
								</span>
								<PackageOpen className="size-4 shrink-0 text-petrol dark:text-panel-terminal" />
							</button>

							<div className="space-y-3">
								<div>
									<p className="text-[12px] font-semibold text-foreground">
										Add the Meta credentials
									</p>
									<p className="text-[10.5px] text-meta">
										Use the identifiers and permanent credentials for this app.
									</p>
								</div>
								<div className="grid gap-4 sm:grid-cols-2">
									<label className="block">
										<span className="mb-1.5 block text-[11px] font-semibold text-label">
											Business account ID
										</span>
										<Input
											value={businessAccountId}
											onChange={(event) => {
												setBusinessAccountId(event.target.value);
											}}
											placeholder="1234567890"
										/>
									</label>
									<label className="block">
										<span className="mb-1.5 block text-[11px] font-semibold text-label">
											Phone number ID
										</span>
										<Input
											value={phoneNumberId}
											onChange={(event) => {
												setPhoneNumberId(event.target.value);
											}}
											placeholder="1234567890"
										/>
									</label>
									<label className="block">
										<span className="mb-1.5 block text-[11px] font-semibold text-label">
											Access token
										</span>
										<Input
											type="password"
											autoComplete="new-password"
											value={accessToken}
											onChange={(event) => {
												setAccessToken(event.target.value);
											}}
											placeholder={
												settings.isConfigured
													? settings.accessTokenLast4
														? `****${settings.accessTokenLast4}`
														: "Token configured"
													: "Permanent access token"
											}
										/>
									</label>
									<label className="block">
										<span className="mb-1.5 block text-[11px] font-semibold text-label">
											App secret
										</span>
										<Input
											type="password"
											autoComplete="new-password"
											value={appSecret}
											onChange={(event) => {
												setAppSecret(event.target.value);
											}}
											placeholder={
												settings.hasAppSecret
													? "Leave blank to keep current"
													: "Meta app secret"
											}
										/>
									</label>
								</div>
								{settings.verifiedName && (
									<p className="text-[11px] text-meta">
										Verified identity:{" "}
										<span className="font-semibold text-foreground">
											{settings.verifiedName}
											{settings.displayPhoneNumber
												? ` / ${settings.displayPhoneNumber}`
												: ""}
										</span>
									</p>
								)}
							</div>

							<div className="overflow-hidden rounded-[9px] border border-border bg-sidebar dark:border-white/10">
								<div className="flex items-center justify-between gap-4 px-3.5 py-3">
									<div className="min-w-0">
										<p className="text-[12.5px] font-semibold text-foreground">
											Tool discovery in WhatsApp
										</p>
										<p className="mt-0.5 text-[10.5px] text-meta">
											How MCP tools reach the model for this connection.
										</p>
									</div>
									<DropdownMenu
										align="end"
										itemClassName="py-[9px]"
										items={discoveryOptions.map((option) => ({
											label: option.label,
											description: option.description,
											active: toolDiscoveryMode === option.value,
											onClick: () => {
												setToolDiscoveryMode(option.value);
											},
										}))}
										trigger={
											<button
												type="button"
												className="inline-flex h-8 shrink-0 cursor-pointer items-center whitespace-nowrap rounded-full bg-hover px-3 text-[12px] font-medium text-foreground transition-colors hover:bg-petrol-tint dark:bg-white/5 dark:hover:bg-white/10"
											>
												{discoveryOptions.find(
													(option) => option.value === toolDiscoveryMode,
												)?.label ?? toolDiscoveryMode}
											</button>
										}
									/>
								</div>
								{[
									{
										label: "Accept WhatsApp requests",
										description: "Agent permissions are checked on every message.",
										checked: enabled,
										onChange: setEnabled,
										disabled: !settings.workspaceEnabled,
									},
									{
										label: "Show typing indicator",
										description: "Show activity while the agent prepares its response.",
										checked: showTypingIndicator,
										onChange: setShowTypingIndicator,
									},
									{
										label: "Show tool callouts",
										description: "Send short updates while the agent uses tools.",
										checked: showToolCallouts,
										onChange: setShowToolCallouts,
									},
									{
										label: "Show Auxilia link",
										description: "Include “View in Auxilia” with successful responses.",
										checked: showAuxiliaLink,
										onChange: setShowAuxiliaLink,
									},
								].map((option) => (
									<div
										key={option.label}
										className="flex items-center justify-between gap-4 border-t border-hairline px-3.5 py-3"
									>
										<div>
											<p className="text-[12.5px] font-semibold text-foreground">
												{option.label}
											</p>
											<p className="mt-0.5 text-[10.5px] text-meta">
												{option.description}
											</p>
										</div>
										<Switch
											checked={option.checked}
											onCheckedChange={option.onChange}
											disabled={option.disabled}
											className="cursor-pointer data-[state=checked]:bg-petrol"
										/>
									</div>
								))}
							</div>

							{error && (
								<p className="rounded-[7px] bg-destructive/10 px-3 py-2 text-[11.5px] text-destructive">
									{error}
								</p>
							)}
						</div>
						<DialogFooter className="border-t border-border px-5 py-3.5 dark:border-white/10 sm:px-6">
							{onDisconnect && (
								<DialogButton
									variant="destructive"
									className="mr-auto shrink-0 whitespace-nowrap"
									disabled={saving}
									onClick={() => {
										void onDisconnect();
									}}
								>
									<Unplug className="size-3.5" />
									Disconnect
								</DialogButton>
							)}
							<DialogButton
								variant="outline"
								className="shrink-0 whitespace-nowrap"
								disabled={saving}
								onClick={() => {
									handleOpenChange(false);
								}}
							>
								Cancel
							</DialogButton>
							<DialogButton
								className="shrink-0 whitespace-nowrap"
								disabled={!canSave}
								onClick={submit}
							>
								{saving ? "Saving…" : "Save connection"}
							</DialogButton>
						</DialogFooter>
					</>
				) : (
					<AgentWhatsAppSetupGuide
						settings={settings}
						onDone={() => {
							setView("configuration");
						}}
					/>
				)}
			</DialogContent>
		</Dialog>
	);
}
