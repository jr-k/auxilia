"use client";

import { useMemo, useState } from "react";
import {
	ArrowLeft,
	ArrowRight,
	ArrowUpRight,
	Check,
	Copy,
	PackageOpen,
	Unplug,
} from "lucide-react";
import {
	Dialog,
	DialogButton,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { CodeBlock } from "@/components/ai-elements/code-block";
import { SlackLogo } from "@/components/slack-logo";
import { DropdownMenu } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useAppearanceStore } from "@/stores/appearance-store";
import { PETROL_MONO_THEME } from "@/lib/shiki-petrol-mono";
import type {
	AgentSlackBotSettings,
	AgentSlackBotSettingsUpdate,
	SlackToolDiscoveryMode,
} from "@/types/agents";

const SLACK_TOOL_DISCOVERY_OPTIONS: ReadonlyArray<{
	value: SlackToolDiscoveryMode;
	label: string;
	description: string;
}> = [
	{
		value: "disabled",
		label: "Eager",
		description: "Load every MCP schema",
	},
	{
		value: "lazy",
		label: "Lazy",
		description: "Choose servers per prompt",
	},
	{
		value: "local",
		label: "Precision",
		description: "Retrieve tools adaptively",
	},
	{
		value: "all_capabilities",
		label: "Enable all capabilities",
		description: "Force all",
	},
];

const slackToolDiscoveryLabel = (mode: SlackToolDiscoveryMode): string =>
	SLACK_TOOL_DISCOVERY_OPTIONS.find((option) => option.value === mode)
		?.label ?? mode;

interface Props {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	settings: AgentSlackBotSettings;
	saving: boolean;
	error: string | null;
	onSave: (update: AgentSlackBotSettingsUpdate) => Promise<void>;
	onDisconnect?: () => Promise<void>;
}

const scopes = [
	"app_mentions:read",
	"assistant:write",
	"channels:history",
	"chat:write",
	"chat:write.public",
	"commands",
	"files:read",
	"files:write",
	"groups:history",
	"im:history",
	"im:write",
	"mpim:history",
	"reactions:read",
	"reactions:write",
	"users:read",
	"users:read.email",
];

function CopyValue({
	label,
	value,
	multiline = false,
}: {
	label: string;
	value: string;
	multiline?: boolean;
}) {
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
			<div className="flex items-center justify-between border-b border-border px-3 py-1.5 dark:border-white/10">
				<span className="text-[10.5px] font-semibold uppercase tracking-[0.08em] text-meta">
					{label}
				</span>
				<button
					type="button"
					onClick={copy}
					className="flex cursor-pointer items-center gap-1.5 rounded-[5px] px-2 py-1 text-[12px] font-semibold text-petrol transition-colors hover:bg-petrol/10"
				>
					{copied ? <Check className="size-3" /> : <Copy className="size-3" />}
					{copied ? "Copied" : "Copy"}
				</button>
			</div>
			{multiline ? (
				<div className="max-h-40 overflow-auto bg-panel">
					<CodeBlock
						code={value}
						language="json"
						theme={PETROL_MONO_THEME}
						className="rounded-none"
					/>
				</div>
			) : (
				<code className="block truncate px-3 py-2.5 text-[12px] text-foreground">
					{value}
				</code>
			)}
		</div>
	);
}

function AgentSlackSetupGuide({
	manifest,
	settings,
	onDone,
}: {
	manifest: string;
	settings: AgentSlackBotSettings;
	onDone: () => void;
}) {
	const [activeStep, setActiveStep] = useState(0);
	const [setupMode, setSetupMode] = useState<"manifest" | "manual">("manifest");
	const appName = useAppearanceStore((state) => state.appearance.appName);
	const badgeClass =
		"rounded-[4px] border border-border bg-background px-1.5 py-0.5 text-[11.5px] text-foreground dark:border-white/10";

	const manifestSteps = [
		{
			title: "Apply the Agent manifest",
			body: (
				<div>
					<p>
						For a new app, open{" "}
						<a
							href="https://api.slack.com/apps"
							target="_blank"
							rel="noreferrer"
							className="inline-flex items-center gap-1 font-semibold text-petrol hover:underline"
						>
							Slack API Apps
							<ArrowUpRight className="size-3" />
						</a>
						, choose <strong>Create New App → From a manifest</strong>, then
						select your workspace. For an existing app, open{" "}
						<strong>Settings → App Manifest</strong>. Paste this JSON and apply
						the changes. It enables Slack&apos;s current{" "}
						<strong>Agent view</strong>, which makes this bot available from
						the Agents menu instead of behaving like a regular app only.
					</p>
					<div className="mt-3">
						<CopyValue
							label="Slack app manifest"
							value={manifest}
							multiline
						/>
					</div>
				</div>
			),
		},
		{
			title: "Install the app",
			body: (
				<p>
					Slack normally asks you to install the app immediately after the
					manifest is applied, so this may already be done. If you skipped it
					or need to reinstall, open <strong>OAuth &amp; Permissions</strong>{" "}
					and click <strong>Install to Workspace</strong> or{" "}
					<strong>Reinstall to Workspace</strong>.
				</p>
			),
		},
		{
			title: "Copy the credentials",
			body: (
				<div className="space-y-3">
					<p>
						In <strong>OAuth &amp; Permissions</strong>, copy the{" "}
						<strong>Bot User OAuth Token</strong> beginning with{" "}
						<code className={badgeClass}>xoxb-</code>. Do not use the{" "}
						<code className={badgeClass}>xoxp-</code> user token.
					</p>
					<p>
						Then open <strong>Settings → Basic Information</strong>. Under{" "}
						<strong>App Credentials</strong>, click <strong>Show</strong> next
						to <strong>Signing Secret</strong> and copy it.
					</p>
				</div>
			),
		},
		{
			title: "Save and verify",
			body: (
				<div className="space-y-3">
					<p>
						Return to the configuration form, paste both credentials, enable
						the bot, and save.
					</p>
					<p>
						Then return to <strong>Event Subscriptions</strong> in Slack and
						click <strong>Retry</strong> if the Request URL is not yet
						verified. The manifest already configures the bot events,
						interactivity, permissions, and disables Socket Mode.
					</p>
				</div>
			),
		},
		{
			title: "Open or pin the agent",
			body: (
				<div className="space-y-3">
					<p>
						Open the <strong>Agents</strong> menu near the top-right of Slack,
						select this bot, then keep or pin it when Slack offers the option.
						It now opens as a dedicated agent in the Messages tab.
					</p>
					<p>
						You can also invite it to a public channel and mention it with a
						request. Replies remain visible to the channel while {appName}{" "}
						checks that the sender can use this agent.
					</p>
				</div>
			),
		},
	];

	const manualSteps = [
		{
			title: "Create the Slack app",
			body: (
				<p>
					Open{" "}
					<a
						href="https://api.slack.com/apps"
						target="_blank"
						rel="noreferrer"
						className="inline-flex items-center gap-1 font-semibold text-petrol hover:underline"
					>
						Slack API Apps
						<ArrowUpRight className="size-3" />
					</a>
					, choose <strong>Create New App → From scratch</strong>, then select
					your Slack workspace.
				</p>
			),
		},
		{
			title: "Disable Socket Mode",
			body: (
				<p>
					Open <strong>Settings → Socket Mode</strong> and turn it off. {appName}
					uses public HTTP callback URLs; Slack hides the Request URL fields
					while Socket Mode is enabled.
				</p>
			),
		},
		{
			title: "Enable the Agent experience",
			body: (
				<div className="space-y-3">
					<p>
						Open <strong>Features → Agents</strong> and enable the Agent
						feature. Add a short agent description. Choose the current{" "}
						<strong>Agent messaging experience</strong>, not the legacy
						Assistant experience. This is what makes the bot appear in
						Slack&apos;s Agents menu.
					</p>
					<p>
						Then open <strong>Features → App Home</strong>. Enable the{" "}
						<strong>Messages Tab</strong>, allow users to send messages from
						it, and leave the Home tab disabled.
					</p>
				</div>
			),
		},
		{
			title: "Add bot permissions",
			body: (
				<div>
					<p>
						In <strong>OAuth &amp; Permissions</strong>, add these{" "}
						<strong>Bot Token Scopes</strong>:
					</p>
					<div className="mt-2 flex flex-wrap gap-1.5">
						{scopes.map((scope) => (
							<code key={scope} className={badgeClass}>
								{scope}
							</code>
						))}
					</div>
					<p className="mt-3">
						The public write scope lets the agent publish in public channels.
						Private channels still require an invitation. The reactions scopes
						let it understand existing reactions, acknowledge mentions, and
						add requested emoji reactions.
					</p>
				</div>
			),
		},
		{
			title: "Install and copy credentials",
			body: (
				<div className="space-y-3">
					<p>
						Install or reinstall the app from{" "}
						<strong>OAuth &amp; Permissions</strong> and copy the{" "}
						<strong>Bot User OAuth Token</strong> beginning with{" "}
						<code className={badgeClass}>xoxb-</code>, not the{" "}
						<code className={badgeClass}>xoxp-</code> user token.
					</p>
					<p>
						In <strong>Settings → Basic Information → App Credentials</strong>,
						click <strong>Show</strong> beside <strong>Signing Secret</strong>{" "}
						and copy it.
					</p>
				</div>
			),
		},
		{
			title: "Subscribe to bot events",
			body: (
				<div>
					<p>
						In <strong>Event Subscriptions</strong>, enable events and paste
						the URL below. Under <strong>Subscribe to bot events</strong>,
						click <strong>Add Bot User Event</strong> and add{" "}
						<code className={badgeClass}>app_mention</code>,{" "}
						<code className={badgeClass}>message.channels</code>, and{" "}
						<code className={badgeClass}>message.groups</code>,{" "}
						<code className={badgeClass}>message.im</code>, and{" "}
						<code className={badgeClass}>message.mpim</code>. Do not use{" "}
						<strong>Subscribe to events on behalf of users</strong>.
					</p>
					<div className="mt-3">
						<CopyValue label="Events request URL" value={settings.eventsUrl} />
					</div>
				</div>
			),
		},
		{
			title: "Enable interactivity",
			body: (
				<div>
					<p>
						In <strong>Interactivity &amp; Shortcuts</strong>, enable
						interactivity and paste this URL into <strong>Request URL</strong>.
						If the field is missing, disable Socket Mode first.
					</p>
					<div className="mt-3">
						<CopyValue
							label="Interactions request URL"
							value={settings.interactionsUrl}
						/>
					</div>
				</div>
			),
		},
		{
			title: "Add the message shortcut",
			body: (
				<div className="space-y-3">
					<p>
						Still under <strong>Interactivity &amp; Shortcuts</strong>, click{" "}
						<strong>Create New Shortcut</strong> and choose{" "}
						<strong>On messages</strong>.
					</p>
					<p>
						Set the name to <strong>Ask agent about message</strong>, the
						callback ID to{" "}
						<code className={badgeClass}>agent_message_shortcut</code>, and the
						description to{" "}
						<strong>Use this message as context for the agent</strong>.
					</p>
				</div>
			),
		},
		{
			title: "Reinstall and test",
			body: (
				<div className="space-y-3">
					<p>
						Reinstall the app so Slack grants the new Agent scope. Return here
						and save the <code className={badgeClass}>xoxb-</code> token and
						Signing Secret.
					</p>
					<p>
						Open Slack&apos;s <strong>Agents</strong> menu near the top-right,
						select this bot, and pin or keep it there. You can also invite it
						to a channel and mention it.
					</p>
				</div>
			),
		},
	];

	const steps = setupMode === "manifest" ? manifestSteps : manualSteps;
	const step = steps[activeStep];
	const isLastStep = activeStep === steps.length - 1;

	return (
		<div className="grid min-h-[380px] grid-cols-[158px_minmax(0,1fr)] sm:grid-cols-[220px_minmax(0,1fr)]">
			<nav
				aria-label="Agent Slack setup steps"
				className="border-r border-border bg-card/45 py-4 dark:border-white/10 dark:bg-white/[0.025]"
			>
				<div className="mx-3 mb-4 grid grid-cols-2 rounded-[7px] border border-border bg-background p-1 dark:border-white/10 dark:bg-white/5">
					{(["manifest", "manual"] as const).map((mode) => (
						<button
							key={mode}
							type="button"
							onClick={() => {
								setSetupMode(mode);
								setActiveStep(0);
							}}
							className={`cursor-pointer rounded-[5px] px-2 py-1.5 text-[11px] font-semibold capitalize transition-colors ${
								setupMode === mode
									? "bg-card text-foreground shadow-sm"
									: "text-meta hover:text-foreground"
							}`}
						>
							{mode}
						</button>
					))}
				</div>
				<p className="mb-2 px-4 text-[10.5px] font-semibold uppercase tracking-[0.1em] text-meta sm:px-5">
					Setup
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
									className={`flex size-6 shrink-0 items-center justify-center rounded-full border font-mono text-[10.5px] font-semibold transition-colors ${
										activeStep === index
											? "border-petrol bg-petrol text-white"
											: "border-border bg-card text-meta group-hover:text-foreground dark:border-white/10"
									}`}
								>
									{index + 1}
								</span>
								<span
									className={`min-w-0 text-[12.5px] leading-[1.3] font-semibold ${
										activeStep === index
											? "text-foreground"
											: "text-subtle"
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
					<p className="max-w-[250px] text-[11px] leading-[1.45] text-meta">
						Slack and {appName} members must use the same email address.
					</p>
					<DialogButton
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

export default function AgentSlackBotDialog({
	open,
	onOpenChange,
	settings,
	saving,
	error,
	onSave,
	onDisconnect,
}: Props) {
	const [view, setView] = useState<"configuration" | "guide">("configuration");
	const [enabled, setEnabled] = useState(settings.enabled);
	const [requireMentionInThreads, setRequireMentionInThreads] = useState(
		settings.requireMentionInThreads,
	);
	const [showToolCallouts, setShowToolCallouts] = useState(
		settings.showToolCallouts,
	);
	const [showThinkingMessage, setShowThinkingMessage] = useState(
		settings.showThinkingMessage,
	);
	const [showAuxiliaLink, setShowAuxiliaLink] = useState(
		settings.showAuxiliaLink,
	);
	const [toolDiscoveryMode, setToolDiscoveryMode] =
		useState<SlackToolDiscoveryMode>(settings.toolDiscoveryMode);
	const [botToken, setBotToken] = useState("");
	const [signingSecret, setSigningSecret] = useState("");
	const manifest = useMemo(
		() => JSON.stringify(settings.manifest, null, 2),
		[settings.manifest],
	);

	const hasNewCredentials = Boolean(botToken.trim() || signingSecret.trim());
	const credentialsComplete = Boolean(botToken.trim() && signingSecret.trim());
	const canSave =
		!saving &&
		(settings.isConfigured || credentialsComplete) &&
		(!hasNewCredentials || credentialsComplete);

	const submit = async () => {
		if (!canSave) return;
		await onSave({
			enabled,
			requireMentionInThreads,
			showToolCallouts,
			showThinkingMessage,
			showAuxiliaLink,
			toolDiscoveryMode,
			...(credentialsComplete
				? {
						botToken: botToken.trim(),
						signingSecret: signingSecret.trim(),
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
					view === "guide" ? "sm:max-w-[680px]" : "sm:max-w-[560px]"
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
							<SlackLogo className="rounded-[9px] bg-card" />
						)}
						<div className="min-w-0">
							<DialogTitle>
								{view === "guide"
									? "Create the Slack bot"
									: settings.isConfigured
										? "Slack connection"
										: "Add Slack Side-Channel"}
							</DialogTitle>
							<DialogDescription className="mt-0.5">
								{view === "guide"
									? "One Slack app exposes this agent in Slack’s Agents menu."
									: settings.isConfigured
										? `Connected to ${settings.slackTeamName ?? "a Slack workspace"}.`
										: "Give this agent its own identity in a Slack workspace."}
							</DialogDescription>
						</div>
					</div>
				</DialogHeader>

				{view === "configuration" ? (
					<>
						<div className="max-h-[68vh] min-w-0 space-y-5 overflow-y-auto px-5 py-5 sm:px-6">
							{!settings.workspaceEnabled && (
								<div className="rounded-[8px] border border-amber-500/25 bg-amber-500/[0.07] px-3.5 py-3 text-[11.5px] leading-5 text-amber-800 dark:text-amber-200">
									Slack is disabled for the workspace. You can prepare this
									bot now, but an admin must enable Slack before it can answer.
								</div>
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
												? "Review the Slack installation"
												: "Install in Slack"}
										</span>
										{!settings.isConfigured && (
											<span className="rounded-full bg-petrol/10 px-1.5 py-0.5 text-[9px] font-bold text-petrol dark:bg-panel-terminal/15 dark:text-panel-terminal">
												Required
											</span>
										)}
									</span>
									<span className="mt-0.5 block text-[10.5px] text-subtle dark:text-panel-body">
										Create the Slack app, install it in your workspace, and
										configure its callback URLs.
									</span>
								</span>
								<PackageOpen className="size-4 shrink-0 text-petrol dark:text-panel-terminal" />
							</button>

							<div className="space-y-3">
								<div>
									<p className="text-[12px] font-semibold text-foreground">
										Add the Slack credentials
									</p>
									<p className="text-[10.5px] text-meta">
										Copy both values from the Slack app you just created.
									</p>
								</div>
								<div className="grid gap-4 sm:grid-cols-2">
									<label className="block">
										<span className="mb-1.5 block text-[11px] font-semibold text-label">
											Bot User OAuth Token
										</span>
										<Input
											type="password"
											autoComplete="new-password"
											value={botToken}
											onChange={(event) => {
												setBotToken(event.target.value);
											}}
											placeholder={
												settings.isConfigured
													? settings.botTokenLast4
														? `****${settings.botTokenLast4}`
														: "Token configured"
													: "xoxb-…"
											}
										/>
									</label>
									<label className="block">
										<span className="mb-1.5 block text-[11px] font-semibold text-label">
											Signing Secret
										</span>
										<Input
											type="password"
											autoComplete="new-password"
											value={signingSecret}
											onChange={(event) => {
												setSigningSecret(event.target.value);
											}}
											placeholder={
												settings.hasSigningSecret
													? "Leave blank to keep current"
													: "Signing secret"
											}
										/>
									</label>
								</div>
							</div>

							<div className="overflow-hidden rounded-[9px] border border-border bg-sidebar dark:border-white/10">
								<div className="flex items-center justify-between gap-4 px-3.5 py-3">
									<div className="min-w-0">
										<p className="text-[12.5px] font-semibold text-foreground">
											Tool discovery in Slack
										</p>
										<p className="mt-0.5 text-[10.5px] text-meta">
											How MCP tools reach the model for this connection,
											overriding the agent’s own setting.
										</p>
									</div>
									<DropdownMenu
										align="end"
										itemClassName="py-[9px]"
										items={SLACK_TOOL_DISCOVERY_OPTIONS.map((option) => ({
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
												{slackToolDiscoveryLabel(toolDiscoveryMode)}
											</button>
										}
									/>
								</div>
								<div className="flex items-center justify-between gap-4 border-t border-hairline px-3.5 py-3">
									<div>
										<p className="text-[12.5px] font-semibold text-foreground">
											Accept Slack requests
										</p>
										<p className="mt-0.5 text-[10.5px] text-meta">
											Agent permissions are checked on every message.
										</p>
									</div>
									<Switch
										checked={enabled}
										onCheckedChange={setEnabled}
										className="cursor-pointer data-[state=checked]:bg-petrol"
									/>
								</div>
								<div className="flex items-center justify-between gap-4 border-t border-hairline px-3.5 py-3">
									<div>
										<p className="text-[12.5px] font-semibold text-foreground">
											Require @mention in channel threads
										</p>
										<p className="mt-0.5 text-[10.5px] text-meta">
											Ignore channel replies that do not mention this bot.
											Direct messages are always accepted.
										</p>
									</div>
									<Switch
										checked={requireMentionInThreads}
										onCheckedChange={setRequireMentionInThreads}
										className="cursor-pointer data-[state=checked]:bg-petrol"
									/>
								</div>
								<div className="flex items-center justify-between gap-4 border-t border-hairline px-3.5 py-3">
									<div>
										<p className="text-[12.5px] font-semibold text-foreground">
											Show tool callouts
										</p>
										<p className="mt-0.5 text-[10.5px] text-meta">
											Display tool names while the agent works. Turn off to
											keep only the textual response.
										</p>
									</div>
									<Switch
										checked={showToolCallouts}
										onCheckedChange={setShowToolCallouts}
										className="cursor-pointer data-[state=checked]:bg-petrol"
									/>
								</div>
								<div className="flex items-center justify-between gap-4 border-t border-hairline px-3.5 py-3">
									<div>
										<p className="text-[12.5px] font-semibold text-foreground">
											Show thinking message
										</p>
										<p className="mt-0.5 text-[10.5px] text-meta">
											Post a temporary “Working on it…” message while the
											agent prepares its response.
										</p>
									</div>
									<Switch
										checked={showThinkingMessage}
										onCheckedChange={setShowThinkingMessage}
										className="cursor-pointer data-[state=checked]:bg-petrol"
									/>
								</div>
								<div className="flex items-center justify-between gap-4 border-t border-hairline px-3.5 py-3">
									<div>
										<p className="text-[12.5px] font-semibold text-foreground">
											Show Auxilia link
										</p>
										<p className="mt-0.5 text-[10.5px] text-meta">
											Include “View in Auxilia” with successful responses.
										</p>
									</div>
									<Switch
										checked={showAuxiliaLink}
										onCheckedChange={setShowAuxiliaLink}
										className="cursor-pointer data-[state=checked]:bg-petrol"
									/>
								</div>
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
									className="mr-auto"
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
								disabled={saving}
								onClick={() => {
									handleOpenChange(false);
								}}
							>
								Cancel
							</DialogButton>
							<DialogButton
								disabled={!canSave}
								onClick={() => {
									void submit();
								}}
							>
								{saving ? "Saving…" : "Save connection"}
							</DialogButton>
						</DialogFooter>
					</>
				) : (
					<AgentSlackSetupGuide
						manifest={manifest}
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
