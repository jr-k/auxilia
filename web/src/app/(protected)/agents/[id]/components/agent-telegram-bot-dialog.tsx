"use client";

import { useState } from "react";
import {
	ArrowLeft,
	ArrowRight,
	ArrowUpRight,
	PackageOpen,
	Unplug,
} from "lucide-react";
import { TelegramLogo } from "@/components/telegram-logo";
import {
	Dialog,
	DialogButton,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import type {
	AgentTelegramBotSettings,
	AgentTelegramBotSettingsUpdate,
	TelegramToolDiscoveryMode,
} from "@/types/agents";

interface Props {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	settings: AgentTelegramBotSettings;
	saving: boolean;
	error: string | null;
	onSave: (update: AgentTelegramBotSettingsUpdate) => Promise<void>;
	onDisconnect?: () => Promise<void>;
}

const discoveryOptions: Array<{
	value: TelegramToolDiscoveryMode;
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

function AgentTelegramSetupGuide({ onDone }: { onDone: () => void }) {
	const [activeStep, setActiveStep] = useState(0);
	const badgeClass =
		"rounded-[4px] border border-border bg-background px-1.5 py-0.5 font-mono text-[11.5px] text-foreground dark:border-white/10";
	const steps = [
		{
			title: "Open BotFather",
			body: (
				<div className="space-y-3">
					<p>
						Open{" "}
						<a
							href="https://t.me/BotFather"
							target="_blank"
							rel="noreferrer"
							className="inline-flex items-center gap-1 font-semibold text-petrol hover:underline"
						>
							@BotFather in Telegram
							<ArrowUpRight className="size-3" />
						</a>
						. BotFather is Telegram&apos;s official bot for creating and
						managing other bots.
					</p>
					<p>
						Confirm that the account has the verified badge and the username{" "}
						<code className={badgeClass}>@BotFather</code>.
					</p>
				</div>
			),
		},
		{
			title: "Create a new bot",
			body: (
				<div className="space-y-3">
					<p>
						Send the <code className={badgeClass}>/newbot</code> command to
						BotFather.
					</p>
					<p>
						BotFather will ask for a display name first, followed by a unique
						username.
					</p>
				</div>
			),
		},
		{
			title: "Choose its identity",
			body: (
				<div className="space-y-3">
					<p>
						Choose a recognizable display name for the agent. This is the name
						people will see in conversations.
					</p>
					<p>
						Then choose a unique username ending with{" "}
						<code className={badgeClass}>bot</code>, for example{" "}
						<code className={badgeClass}>acme_support_bot</code>.
					</p>
				</div>
			),
		},
		{
			title: "Copy the bot token",
			body: (
				<div className="space-y-3">
					<p>
						BotFather will return a bot token similar to{" "}
						<code className={badgeClass}>123456:ABC-DEF1234...</code>. Copy the
						entire value.
					</p>
					<p>
						Keep this token private. Anyone who has it can control the bot.
						Auxilia stores it encrypted.
					</p>
				</div>
			),
		},
		{
			title: "Enable group context",
			body: (
				<div className="space-y-3">
					<p>
						If the agent will be used in groups, send{" "}
						<code className={badgeClass}>/setprivacy</code> to BotFather,
						select this bot, then choose <strong>Disable</strong>.
					</p>
					<p>
						This lets the bot retain group context for 30 days. Mentions and
						forum topics remain supported.
					</p>
				</div>
			),
		},
		{
			title: "Paste and save",
			body: (
				<div className="space-y-3">
					<p>
						Return to the previous window, paste the token into{" "}
						<strong>Bot token</strong>, and save the connection.
					</p>
					<p>
						After saving, add the bot to any Telegram groups where this agent
						should be available.
					</p>
				</div>
			),
		},
	];
	const step = steps[activeStep];
	const isLastStep = activeStep === steps.length - 1;

	return (
		<div className="grid min-h-[380px] grid-cols-[158px_minmax(0,1fr)] sm:grid-cols-[220px_minmax(0,1fr)]">
			<nav
				aria-label="Telegram bot setup steps"
				className="border-r border-border bg-card/45 py-4 dark:border-white/10 dark:bg-white/[0.025]"
			>
				<p className="mb-2 px-4 text-[10.5px] font-semibold text-meta sm:px-5">
					BotFather setup
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
						Each Telegram bot is connected to this agent only.
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

export default function AgentTelegramBotDialog({
	open,
	onOpenChange,
	settings,
	saving,
	error,
	onSave,
	onDisconnect,
}: Props) {
	const [view, setView] = useState<"configuration" | "guide">("configuration");
	const [token, setToken] = useState("");
	const [enabled, setEnabled] = useState(settings.enabled);
	const [requireMention, setRequireMention] = useState(
		settings.requireMentionInGroups,
	);
	const [showToolCallouts, setShowToolCallouts] = useState(
		settings.showToolCallouts,
	);
	const [toolDiscoveryMode, setToolDiscoveryMode] =
		useState<TelegramToolDiscoveryMode>(settings.toolDiscoveryMode);

	const submit = () => {
		void onSave({
			enabled,
			requireMentionInGroups: requireMention,
			showToolCallouts,
			toolDiscoveryMode,
			...(token.trim() ? { botToken: token.trim() } : {}),
		});
	};

	const handleOpenChange = (nextOpen: boolean) => {
		if (!nextOpen) setView("configuration");
		onOpenChange(nextOpen);
	};

	return (
		<Dialog
			open={open}
			onOpenChange={saving ? undefined : handleOpenChange}
		>
			<DialogContent
				className={`gap-0 overflow-hidden p-0 ${
					view === "guide" ? "sm:max-w-[680px]" : "sm:max-w-[600px]"
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
							<TelegramLogo className="size-9" />
						)}
						<div className="min-w-0">
							<DialogTitle>
								{view === "guide"
									? "Create the Telegram bot"
									: settings.isConfigured
										? "Telegram connection"
										: "Add Telegram side-channel"}
							</DialogTitle>
							<DialogDescription className="mt-0.5">
								{view === "guide"
									? "Create a dedicated bot with Telegram’s official BotFather."
									: settings.isConfigured
										? `Connected to @${settings.botUsername ?? settings.botName ?? "Telegram bot"}.`
										: "Give this agent its own identity on Telegram."}
							</DialogDescription>
						</div>
					</div>
				</DialogHeader>

				{view === "configuration" ? (
					<>
						<div className="max-h-[68vh] space-y-5 overflow-y-auto px-5 py-5 sm:px-6">
							{!settings.workspaceEnabled && (
								<p className="rounded-[8px] border border-amber-300/60 bg-amber-50 px-3 py-2 text-[11.5px] text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
									Telegram is disabled for this workspace. An administrator
									must enable it in Settings / Integrations / Messaging.
								</p>
							)}

							<button
								type="button"
								onClick={() => {
									setView("guide");
								}}
								className="group flex w-full cursor-pointer items-center gap-3 rounded-[10px] border border-[#2AABEE]/30 bg-[#2AABEE]/[0.07] p-4 text-left transition-all hover:border-[#2AABEE]/45 hover:bg-[#2AABEE]/[0.11] dark:border-[#2AABEE]/50 dark:bg-[#2AABEE]/15 dark:hover:bg-[#2AABEE]/20"
							>
								<span className="min-w-0 flex-1">
									<span className="flex items-center gap-2">
										<span className="block text-[12.5px] font-semibold text-foreground">
											{settings.isConfigured
												? "Review the BotFather setup"
												: "Set up with BotFather"}
										</span>
										{!settings.isConfigured && (
											<span className="rounded-full bg-[#2AABEE]/10 px-1.5 py-0.5 text-[9px] font-bold text-[#168bc3] dark:text-[#70c8f2]">
												Required
											</span>
										)}
									</span>
									<span className="mt-0.5 block text-[10.5px] text-subtle dark:text-panel-body">
										Create the bot, choose its username, and copy its token.
									</span>
								</span>
								<PackageOpen className="size-4 shrink-0 text-[#168bc3] dark:text-[#70c8f2]" />
							</button>

							<label className="block">
								<span className="mb-1.5 block text-[11px] font-semibold text-foreground">
									Bot token
								</span>
								<Input
									type="password"
									autoComplete="new-password"
									value={token}
									onChange={(event) => {
										setToken(event.target.value);
									}}
									placeholder={
										settings.isConfigured
											? `Configured / ending in ${settings.botTokenLast4 ?? "••••"}`
											: "123456:ABC-DEF1234..."
									}
								/>
							</label>

							{settings.isConfigured && (
								<div className="rounded-[9px] border border-border bg-background p-3 text-[11.5px] text-meta dark:border-white/10">
									<p className="font-semibold text-foreground">
										@
										{settings.botUsername ??
											settings.botName ??
											"Telegram bot"}
									</p>
									<p className="mt-1 break-all">
										Webhook: {settings.webhookUrl}
									</p>
									{settings.deepLinkUrl && (
										<a
											href={settings.deepLinkUrl}
											target="_blank"
											rel="noreferrer"
											className="mt-2 inline-flex items-center gap-1 font-semibold text-petrol hover:underline"
										>
											Open bot
											<ArrowUpRight className="size-3" />
										</a>
									)}
								</div>
							)}

							<div className="space-y-3 rounded-[10px] border border-border bg-card p-4 dark:border-white/10">
								<div className="flex items-center justify-between gap-4">
									<div>
										<p className="text-[12px] font-semibold text-foreground">
											Bot active
										</p>
										<p className="mt-0.5 text-[10.5px] text-meta">
											Register the secure Telegram webhook.
										</p>
									</div>
									<Switch
										checked={enabled}
										onCheckedChange={setEnabled}
										disabled={!settings.workspaceEnabled}
									/>
								</div>
								<div className="flex items-center justify-between gap-4 border-t border-hairline pt-3">
									<div>
										<p className="text-[12px] font-semibold text-foreground">
											Require mentions in groups
										</p>
										<p className="mt-0.5 text-[10.5px] text-meta">
											Ignore ambient group messages except for context.
										</p>
									</div>
									<Switch
										checked={requireMention}
										onCheckedChange={setRequireMention}
									/>
								</div>
								<div className="flex items-center justify-between gap-4 border-t border-hairline pt-3">
									<div>
										<p className="text-[12px] font-semibold text-foreground">
											Show tool activity
										</p>
										<p className="mt-0.5 text-[10.5px] text-meta">
											Include compact tool callouts while streaming.
										</p>
									</div>
									<Switch
										checked={showToolCallouts}
										onCheckedChange={setShowToolCallouts}
									/>
								</div>
							</div>

							<label className="block">
								<span className="mb-1.5 block text-[11px] font-semibold text-foreground">
									Tool discovery
								</span>
								<select
									value={toolDiscoveryMode}
									onChange={(event) => {
										setToolDiscoveryMode(
											event.target.value as TelegramToolDiscoveryMode,
										);
									}}
									className="h-9 w-full rounded-[7px] border border-input bg-background px-3 text-[12px] text-foreground outline-none focus:border-petrol"
								>
									{discoveryOptions.map((option) => (
										<option key={option.value} value={option.value}>
											{option.label} / {option.description}
										</option>
									))}
								</select>
							</label>

							{error && (
								<p className="rounded-[7px] bg-destructive/10 px-3 py-2 text-[11.5px] text-destructive">
									{error}
								</p>
							)}
						</div>

						<DialogFooter className="border-t border-border px-5 py-4 dark:border-white/10 sm:px-6">
							{onDisconnect && (
								<DialogButton
									variant="destructive"
									onClick={() => {
										void onDisconnect();
									}}
									disabled={saving}
									className="mr-auto"
								>
									<Unplug className="size-3.5" />
									Disconnect
								</DialogButton>
							)}
							<DialogButton
								variant="outline"
								onClick={() => {
									handleOpenChange(false);
								}}
								disabled={saving}
							>
								Cancel
							</DialogButton>
							<DialogButton
								onClick={submit}
								disabled={
									saving || (!settings.isConfigured && !token.trim())
								}
							>
								{saving ? "Saving..." : "Save bot"}
							</DialogButton>
						</DialogFooter>
					</>
				) : (
					<AgentTelegramSetupGuide
						onDone={() => {
							setView("configuration");
						}}
					/>
				)}
			</DialogContent>
		</Dialog>
	);
}
