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
import { DropdownMenu } from "@/components/ui/dropdown-menu";
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

const telegramToolDiscoveryLabel = (
	mode: TelegramToolDiscoveryMode,
): string =>
	discoveryOptions.find((option) => option.value === mode)?.label ?? mode;

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
							<span className="flex size-9 shrink-0 items-center justify-center rounded-[9px] border border-border bg-card shadow-sm dark:border-white/10">
								<TelegramLogo className="size-[62%]" />
							</span>
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
								className="group flex w-full cursor-pointer items-center gap-3 rounded-[10px] border border-petrol/30 bg-petrol/[0.07] p-4 text-left transition-all hover:border-petrol/45 hover:bg-petrol/[0.11] dark:border-petrol/60 dark:bg-petrol/25 dark:hover:bg-petrol/35"
							>
								<span className="min-w-0 flex-1">
									<span className="flex items-center gap-2">
										<span className="block text-[12.5px] font-semibold text-foreground">
											{settings.isConfigured
												? "Review the BotFather setup"
												: "Set up with BotFather"}
										</span>
										{!settings.isConfigured && (
											<span className="rounded-full bg-petrol/10 px-1.5 py-0.5 text-[9px] font-bold text-petrol dark:bg-panel-terminal/15 dark:text-panel-terminal">
												Required
											</span>
										)}
									</span>
									<span className="mt-0.5 block text-[10.5px] text-subtle dark:text-panel-body">
										Create the bot, choose its username, and copy its token.
									</span>
								</span>
								<PackageOpen className="size-4 shrink-0 text-petrol dark:text-panel-terminal" />
							</button>

							<div className="space-y-3">
								<div className="flex items-start justify-between gap-4">
									<div>
										<p className="text-[12px] font-semibold text-foreground">
											Add the Telegram credentials
										</p>
										<p className="text-[10.5px] text-meta">
											Copy the token from the BotFather bot you just created.
										</p>
									</div>
									{settings.deepLinkUrl && (
										<a
											href={settings.deepLinkUrl}
											target="_blank"
											rel="noreferrer"
											className="inline-flex shrink-0 items-center gap-1 text-[11px] font-semibold text-petrol hover:underline"
										>
											Open bot
											<ArrowUpRight className="size-3" />
										</a>
									)}
								</div>
								<label className="block">
									<span className="mb-1.5 block text-[11px] font-semibold text-label">
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
												? settings.botTokenLast4
													? `****${settings.botTokenLast4}`
													: "Token configured"
												: "123456:ABC-DEF1234..."
										}
									/>
								</label>
							</div>

							<div className="overflow-hidden rounded-[9px] border border-border bg-sidebar dark:border-white/10">
								<div className="flex items-center justify-between gap-4 px-3.5 py-3">
									<div className="min-w-0">
										<p className="text-[12.5px] font-semibold text-foreground">
											Tool discovery in Telegram
										</p>
										<p className="mt-0.5 text-[10.5px] text-meta">
											How MCP tools reach the model for this connection,
											overriding the agent’s own setting.
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
												{telegramToolDiscoveryLabel(toolDiscoveryMode)}
											</button>
										}
									/>
								</div>
								<div className="flex items-center justify-between gap-4 border-t border-hairline px-3.5 py-3">
									<div>
										<p className="text-[12.5px] font-semibold text-foreground">
											Accept Telegram requests
										</p>
										<p className="mt-0.5 text-[10.5px] text-meta">
											Agent permissions are checked on every message.
										</p>
									</div>
									<Switch
										checked={enabled}
										onCheckedChange={setEnabled}
										disabled={!settings.workspaceEnabled}
										className="cursor-pointer data-[state=checked]:bg-petrol"
									/>
								</div>
								<div className="flex items-center justify-between gap-4 border-t border-hairline px-3.5 py-3">
									<div>
										<p className="text-[12.5px] font-semibold text-foreground">
											Require @mention in groups
										</p>
										<p className="mt-0.5 text-[10.5px] text-meta">
											Only mentions start a run. Other messages remain
											available as context.
										</p>
									</div>
									<Switch
										checked={requireMention}
										onCheckedChange={setRequireMention}
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
								{saving ? "Saving…" : "Save connection"}
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
