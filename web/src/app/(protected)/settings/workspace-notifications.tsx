"use client";

import { useCallback, useEffect, useState } from "react";
import {
	ArrowUpRight,
	BookOpen,
	Check,
	Copy,
	MessageSquareMore,
} from "lucide-react";
import { HeaderButton } from "@/components/layout/subpage-header";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { getApiErrorMessage, isApiError } from "@/lib/api/errors";
import * as notificationsApi from "@/lib/api/resources/notifications";
import type { SlackNotificationSettings } from "@/types/notifications";

interface Props {
	onForbidden: () => void;
}

const labelClass =
	"mb-1.5 block text-[12px] font-semibold text-subtle dark:text-panel-body";

function SlackMark() {
	return (
		<span className="grid size-9 shrink-0 grid-cols-2 gap-0.5 rounded-[8px] border border-border bg-card p-2 shadow-sm dark:border-white/10">
			<span className="rounded-full bg-[#36C5F0]" />
			<span className="rounded-full bg-[#2EB67D]" />
			<span className="rounded-full bg-[#E01E5A]" />
			<span className="rounded-full bg-[#ECB22E]" />
		</span>
	);
}

function CopySetupValue({ label, value }: { label: string; value: string }) {
	const [copied, setCopied] = useState(false);

	const copy = () => {
		const clipboard = navigator.clipboard as Clipboard | undefined;
		if (!clipboard) return;
		void clipboard.writeText(value).then(() => {
			setCopied(true);
			window.setTimeout(() => {
				setCopied(false);
			}, 1800);
		});
	};

	return (
		<div className="mt-3 overflow-hidden rounded-[7px] border border-border bg-background dark:border-white/10">
			<div className="border-b border-border px-3 py-1.5 text-[9.5px] font-semibold uppercase tracking-[0.08em] text-meta dark:border-white/10">
				{label}
			</div>
			<div className="flex items-center gap-2 px-3 py-2">
				<code className="min-w-0 flex-1 truncate text-[11px] text-foreground">
					{value}
				</code>
				<button
					type="button"
					onClick={copy}
					className="flex h-7 shrink-0 cursor-pointer items-center gap-1.5 rounded-[5px] border border-input bg-card px-2.5 text-[11px] font-semibold text-subtle transition-colors hover:border-border-hover hover:text-foreground"
				>
					{copied ? (
						<Check className="size-3 text-petrol" />
					) : (
						<Copy className="size-3" />
					)}
					{copied ? "Copied" : "Copy"}
				</button>
			</div>
		</div>
	);
}

function SlackSetupGuide({
	open,
	onOpenChange,
	eventsUrl,
	interactionsUrl,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	eventsUrl: string;
	interactionsUrl: string;
}) {
	const steps = [
		{
			title: "Create your Slack app",
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
					, choose <strong>From scratch</strong>, then select the Slack
					workspace you want to connect.
				</p>
			),
		},
		{
			title: "Enable the Slack assistant",
			body: (
				<p>
					In <strong>Agents &amp; AI Apps</strong>, enable your app as an AI
					assistant. This gives users a dedicated conversational surface for
					Auxilia in Slack.
				</p>
			),
		},
		{
			title: "Add the bot permissions",
			body: (
				<div>
					<p>
						Under <strong>OAuth &amp; Permissions</strong>, add these Bot
						Token Scopes:
					</p>
					<div className="mt-2 flex flex-wrap gap-1.5">
						{[
							"assistant:write",
							"chat:write",
							"im:history",
							"users:read",
							"users:read.email",
						].map((scope) => (
							<code
								key={scope}
								className="rounded-[4px] border border-border bg-background px-1.5 py-0.5 text-[10.5px] text-foreground dark:border-white/10"
							>
								{scope}
							</code>
						))}
					</div>
				</div>
			),
		},
		{
			title: "Connect Slack events",
			body: (
				<div>
					<p>
						In <strong>Event Subscriptions</strong>, turn events on, paste
						the URL below, then subscribe to the <code>message.im</code> bot
						event so Auxilia can receive direct messages sent to the app.
					</p>
					<CopySetupValue label="Request URL" value={eventsUrl} />
				</div>
			),
		},
		{
			title: "Enable interactive messages",
			body: (
				<div>
					<p>
						In <strong>Interactivity &amp; Shortcuts</strong>, turn
						interactivity on and use this request URL. It lets people choose
						an agent and approve sensitive tool calls without leaving Slack.
					</p>
					<CopySetupValue label="Request URL" value={interactionsUrl} />
				</div>
			),
		},
		{
			title: "Install and connect",
			body: (
				<p>
					Install the app to your workspace. Paste its{" "}
					<strong>Bot User OAuth Token</strong> and the{" "}
					<strong>Signing Secret</strong> from Basic Information into the
					Messaging settings, then save.
				</p>
			),
		},
	];

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="gap-0 p-0 sm:max-w-[600px]">
				<DialogHeader className="border-b border-border px-5 py-4 pr-14 dark:border-white/10 sm:px-6">
					<div className="flex items-center gap-3">
						<SlackMark />
						<div>
							<DialogTitle>Connect Slack to Auxilia</DialogTitle>
							<DialogDescription className="mt-0.5">
								Set up a private, two-way conversation channel for your
								workspace.
							</DialogDescription>
						</div>
					</div>
				</DialogHeader>

				<div className="px-5 py-5 sm:px-6">
					<div className="mb-5 flex gap-3 rounded-[8px] border border-petrol/20 bg-petrol/[0.055] p-3.5 dark:bg-petrol/10">
						<MessageSquareMore className="mt-0.5 size-4 shrink-0 text-petrol" />
						<p className="text-[12px] leading-[1.55] text-subtle dark:text-panel-body">
							Slack messages open real Auxilia threads. Each Slack user is
							matched to a workspace member by email, so agent access and tool
							approvals keep the same permissions as the web app.
						</p>
					</div>

					<ol className="space-y-4">
						{steps.map((step, index) => (
							<li key={step.title} className="flex gap-3">
								<span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-border bg-card font-mono text-[10px] font-semibold text-meta dark:border-white/10">
									{index + 1}
								</span>
								<div className="min-w-0 pt-0.5">
									<h3 className="text-[12.5px] font-semibold text-foreground">
										{step.title}
									</h3>
									<div className="mt-1 text-[11.5px] leading-[1.55] text-subtle dark:text-panel-body">
										{step.body}
									</div>
								</div>
							</li>
						))}
					</ol>

					<p className="mt-5 border-t border-border pt-4 text-[10.5px] leading-[1.5] text-meta dark:border-white/10">
						For identity matching to work, members must use the same email in
						Slack and Auxilia.
					</p>
				</div>
			</DialogContent>
		</Dialog>
	);
}

export default function WorkspaceMessaging({ onForbidden }: Props) {
	const [settings, setSettings] = useState<SlackNotificationSettings | null>(null);
	const [enabled, setEnabled] = useState(false);
	const [botToken, setBotToken] = useState("");
	const [signingSecret, setSigningSecret] = useState("");
	const [guideOpen, setGuideOpen] = useState(false);
	const [saving, setSaving] = useState(false);
	const [status, setStatus] = useState<string | null>(null);
	const [loadError, setLoadError] = useState<string | null>(null);

	const load = useCallback(async () => {
		setLoadError(null);
		try {
			const value = await notificationsApi.getSlackSettings();
			setSettings(value);
			setEnabled(value.enabled);
		} catch (error: unknown) {
			if (isApiError(error) && error.status === 403) {
				onForbidden();
				return;
			}
			setLoadError(
				getApiErrorMessage(error, "Could not load messaging settings."),
			);
		}
	}, [onForbidden]);

	useEffect(() => {
		const timeoutId = window.setTimeout(() => {
			void load();
		}, 0);
		return () => {
			window.clearTimeout(timeoutId);
		};
	}, [load]);

	if (!settings) {
		if (loadError) {
			return (
				<div className="rounded-[10px] border border-destructive/25 bg-destructive/5 p-5">
					<p className="text-[13px] text-destructive">{loadError}</p>
					<button
						type="button"
						onClick={() => {
							void load();
						}}
						className="mt-3 cursor-pointer rounded-[7px] border border-input bg-card px-3 py-1.5 text-[12px] font-semibold text-foreground"
					>
						Retry
					</button>
				</div>
			);
		}
		return (
			<div className="h-64 animate-pulse rounded-[10px] border border-border bg-card" />
		);
	}

	const save = async () => {
		setSaving(true);
		setStatus(null);
		try {
			const replacing = botToken.trim() || signingSecret.trim();
			const updated = await notificationsApi.updateSlackSettings({
				enabled,
				...(replacing
					? {
							botToken: botToken.trim(),
							signingSecret: signingSecret.trim(),
						}
					: {}),
			});
			setSettings(updated);
			setBotToken("");
			setSigningSecret("");
			setStatus("Messaging settings saved.");
		} catch (error: unknown) {
			if (isApiError(error) && error.status === 403) onForbidden();
			setStatus(
				isApiError(error) && error.detail
					? error.detail
					: "Could not save messaging settings.",
			);
		} finally {
			setSaving(false);
		}
	};

	const toggleEnabled = async (checked: boolean) => {
		setEnabled(checked);
		setStatus(null);
		if (checked && !settings.isConfigured) return;

		setSaving(true);
		try {
			const updated = await notificationsApi.updateSlackSettings({
				enabled: checked,
			});
			setSettings(updated);
			setStatus(
				checked ? "Slack messaging enabled." : "Slack messaging disabled.",
			);
		} catch (error: unknown) {
			setEnabled(!checked);
			if (isApiError(error) && error.status === 403) onForbidden();
			setStatus(
				isApiError(error) && error.detail
					? error.detail
					: "Could not update messaging settings.",
			);
		} finally {
			setSaving(false);
		}
	};

	return (
		<div>
			<SlackSetupGuide
				open={guideOpen}
				onOpenChange={setGuideOpen}
				eventsUrl={settings.eventsUrl}
				interactionsUrl={settings.interactionsUrl}
			/>
			<div className="mb-1.5 flex items-center gap-2.5">
				<span className="text-[10.5px] font-semibold text-subtle dark:text-panel-dim">
					Messaging
				</span>
				<span className="text-[10.5px] text-meta dark:text-panel-dim">admin</span>
				<span className="flex-1" />
				<button
					type="button"
					onClick={() => {
						setGuideOpen(true);
					}}
					className="flex cursor-pointer items-center gap-1.5 rounded-[6px] px-2 py-1 text-[11px] font-semibold text-petrol transition-colors hover:bg-petrol/10"
				>
					<BookOpen className="size-3.5" />
					How to connect Slack
				</button>
			</div>
			<p className="mb-3.5 max-w-[620px] text-[13px] leading-[1.55] text-subtle dark:text-panel-body">
				Connect a Slack app to run agents and deliver their responses in Slack.
			</p>
			<div className="overflow-hidden rounded-[10px] border border-border bg-card dark:border-white/10">
				<div className="space-y-5 px-4 py-4">
					<div className="flex items-center justify-between gap-4">
						<div>
							<div className="text-[13px] font-semibold text-foreground">
								Slack
							</div>
							<div className="text-[11.5px] text-meta">
								{settings.isConfigured
									? `Configured, bot token ending in ${settings.botTokenLast4}`
									: "Not configured"}
							</div>
						</div>
						<Switch
							checked={enabled}
							disabled={saving}
							onCheckedChange={(checked) => {
								void toggleEnabled(checked);
							}}
							className="cursor-pointer data-[state=checked]:bg-petrol"
						/>
					</div>
					{enabled && (
						<>
							<label className="block">
								<span className={labelClass}>Bot token</span>
								<Input
									type="password"
									value={botToken}
									onChange={(event) => {
										setBotToken(event.target.value);
									}}
									placeholder={
										settings.isConfigured
											? "Leave blank to keep current"
											: "xoxb-…"
									}
								/>
							</label>
							<label className="block">
								<span className={labelClass}>Signing secret</span>
								<Input
									type="password"
									value={signingSecret}
									onChange={(event) => {
										setSigningSecret(event.target.value);
									}}
									placeholder={
										settings.isConfigured ? "Leave blank to keep current" : ""
									}
								/>
							</label>
							<label className="block">
								<span className={labelClass}>Events request URL</span>
								<Input
									readOnly
									value={settings.eventsUrl}
									className="font-mono"
								/>
							</label>
							<label className="block">
								<span className={labelClass}>Interactions request URL</span>
								<Input
									readOnly
									value={settings.interactionsUrl}
									className="font-mono"
								/>
							</label>
						</>
					)}
				</div>
				{enabled && (
					<div className="flex items-center gap-3 border-t border-hairline px-4 py-3">
						<HeaderButton
							accent
							disabled={saving}
							onClick={() => {
								void save();
							}}
						>
							{saving ? "Saving…" : "Save changes"}
						</HeaderButton>
						{status && (
							<span className="text-[12px] text-subtle">{status}</span>
						)}
					</div>
				)}
			</div>
		</div>
	);
}
