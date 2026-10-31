"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, Settings2 } from "lucide-react";
import { useConfirmDialog } from "@/components/providers/dialog-provider";
import { SlackLogo } from "@/components/slack-logo";
import { TelegramLogo } from "@/components/telegram-logo";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { getApiErrorMessage } from "@/lib/api/errors";
import * as agentsApi from "@/lib/api/resources/agents";
import { handleKeyboardListNavigation } from "@/lib/keyboard-list-navigation";
import { useAppearanceStore } from "@/stores/appearance-store";
import type {
	AgentSlackBotSettings,
	AgentSlackBotSettingsUpdate,
	AgentTelegramBotSettings,
	AgentTelegramBotSettingsUpdate,
} from "@/types/agents";
import AgentSlackBotDialog from "./agent-slack-bot-dialog";
import AgentTelegramBotDialog from "./agent-telegram-bot-dialog";

interface Props {
	agentId: string;
	canManage: boolean;
	readOnly: boolean;
}

export default function AgentSlackBotCard({ agentId, canManage, readOnly }: Props) {
	const confirmDialog = useConfirmDialog();
	const appName = useAppearanceStore((state) => state.appearance.appName);
	const [connections, setConnections] = useState<AgentSlackBotSettings[]>([]);
	const [setup, setSetup] = useState<AgentSlackBotSettings | null>(null);
	const [selected, setSelected] = useState<AgentSlackBotSettings | null>(null);
	const [telegramConnections, setTelegramConnections] = useState<
		AgentTelegramBotSettings[]
	>([]);
	const [telegramSetup, setTelegramSetup] =
		useState<AgentTelegramBotSettings | null>(null);
	const [selectedTelegram, setSelectedTelegram] =
		useState<AgentTelegramBotSettings | null>(null);
	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState<string | null>(null);
	const [pickerOpen, setPickerOpen] = useState(false);
	const [dialogOpen, setDialogOpen] = useState(false);
	const [telegramDialogOpen, setTelegramDialogOpen] = useState(false);
	const [saving, setSaving] = useState(false);
	const [saveError, setSaveError] = useState<string | null>(null);

	const load = useCallback(async () => {
		setLoading(true);
		setLoadError(null);
		try {
			const [
				nextConnections,
				nextSetup,
				nextTelegramConnections,
				nextTelegramSetup,
			] = await Promise.all([
				agentsApi.listAgentSlackBots(agentId),
				agentsApi.getAgentSlackBotSetup(agentId),
				agentsApi.listAgentTelegramBots(agentId),
				agentsApi.getAgentTelegramBotSetup(agentId),
			]);
			setConnections(nextConnections);
			setSetup(nextSetup);
			setTelegramConnections(nextTelegramConnections);
			setTelegramSetup(nextTelegramSetup);
		} catch (error: unknown) {
			setLoadError(
				getApiErrorMessage(error, "Could not load agent side-channels."),
			);
		} finally {
			setLoading(false);
		}
	}, [agentId]);

	useEffect(() => {
		const timeoutId = window.setTimeout(() => {
			void load();
		}, 0);
		return () => {
			window.clearTimeout(timeoutId);
		};
	}, [load]);

	const openConfiguration = (settings: AgentSlackBotSettings) => {
		setSaveError(null);
		setSelected(settings);
		setDialogOpen(true);
	};

	const chooseSlack = () => {
		if (!setup) return;
		setPickerOpen(false);
		openConfiguration(setup);
	};

	const chooseTelegram = () => {
		if (!telegramSetup) return;
		setPickerOpen(false);
		setSaveError(null);
		setSelectedTelegram(telegramSetup);
		setTelegramDialogOpen(true);
	};

	const save = async (update: AgentSlackBotSettingsUpdate) => {
		if (!selected) return;
		setSaving(true);
		setSaveError(null);
		try {
			const updated = selected.id
				? await agentsApi.updateAgentSlackBot(
						agentId,
						selected.id,
						update,
					)
				: await agentsApi.createAgentSlackBot(agentId, update);
			setConnections((current) =>
				selected.id
					? current.map((connection) =>
							connection.id === updated.id ? updated : connection,
						)
					: [...current, updated],
			);
			setDialogOpen(false);
			setSelected(null);
		} catch (error: unknown) {
			setSaveError(
				getApiErrorMessage(error, "Could not save the Slack connection."),
			);
		} finally {
			setSaving(false);
		}
	};

	const disconnect = async (connection: AgentSlackBotSettings) => {
		if (
			!connection.id ||
			!(await confirmDialog({
				title: `Disconnect ${connection.slackTeamName ?? "this Slack workspace"}?`,
				description:
					`New Slack messages from this connection will stop reaching the agent. Existing ${appName} threads remain available.`,
				confirmLabel: "Disconnect",
				destructive: true,
			}))
		) {
			return;
		}
		setSaving(true);
		setLoadError(null);
		try {
			await agentsApi.deleteAgentSlackBot(agentId, connection.id);
			setConnections((current) =>
				current.filter((item) => item.id !== connection.id),
			);
			setDialogOpen(false);
			setSelected(null);
		} catch (error: unknown) {
			setLoadError(
				getApiErrorMessage(error, "Could not disconnect the Slack bot."),
			);
		} finally {
			setSaving(false);
		}
	};

	const saveTelegram = async (update: AgentTelegramBotSettingsUpdate) => {
		if (!selectedTelegram) return;
		setSaving(true);
		setSaveError(null);
		try {
			const updated = selectedTelegram.id
				? await agentsApi.updateAgentTelegramBot(
						agentId,
						selectedTelegram.id,
						update,
					)
				: await agentsApi.createAgentTelegramBot(agentId, update);
			setTelegramConnections((current) =>
				selectedTelegram.id
					? current.map((connection) =>
							connection.id === updated.id ? updated : connection,
						)
					: [...current, updated],
			);
			setTelegramDialogOpen(false);
			setSelectedTelegram(null);
		} catch (error: unknown) {
			setSaveError(
				getApiErrorMessage(error, "Could not save the Telegram connection."),
			);
		} finally {
			setSaving(false);
		}
	};

	const disconnectTelegram = async (
		connection: AgentTelegramBotSettings,
	) => {
		if (
			!connection.id ||
			!(await confirmDialog({
				title: `Disconnect @${connection.botUsername ?? "this Telegram bot"}?`,
				description: `New Telegram messages will stop reaching the agent. Existing ${appName} threads remain available.`,
				confirmLabel: "Disconnect",
				destructive: true,
			}))
		) {
			return;
		}
		setSaving(true);
		try {
			await agentsApi.deleteAgentTelegramBot(agentId, connection.id);
			setTelegramConnections((current) =>
				current.filter((item) => item.id !== connection.id),
			);
			setTelegramDialogOpen(false);
			setSelectedTelegram(null);
		} catch (error: unknown) {
			setLoadError(
				getApiErrorMessage(error, "Could not disconnect the Telegram bot."),
			);
		} finally {
			setSaving(false);
		}
	};

	const totalConnections = connections.length + telegramConnections.length;

	const statusLabel = (connection: {
		workspaceEnabled: boolean;
		enabled: boolean;
	}) =>
		!connection.workspaceEnabled
			? "Workspace disabled"
			: connection.enabled
				? "Connected"
				: "Paused";

	return (
		<section className="mt-8">
			<div className="mb-2 flex items-center justify-between gap-4">
				<span className="text-[10.5px] font-semibold text-subtle dark:text-panel-dim">
					Side channels{" "}
					<span className="text-meta dark:text-panel-dim">
						{totalConnections}
					</span>
				</span>
				{canManage && !readOnly && setup && telegramSetup && (
					<button
						type="button"
						onClick={() => {
							setPickerOpen(true);
						}}
						className="flex cursor-pointer items-center gap-1 text-[12.5px] font-semibold text-petrol transition-opacity hover:opacity-80 dark:text-panel-terminal"
					>
						<Plus className="size-3" />
						Add side-channel
					</button>
				)}
			</div>
			<p className="mb-3 text-[12px] leading-5 text-meta">
				Let people operate this agent from external conversations.
			</p>

			<div
				className={`overflow-hidden rounded-[10px] border ${
					!loading && totalConnections === 0
						? "border-dashed border-input"
						: "border-border bg-card dark:border-white/10"
				}`}
			>
				{loading ? (
					<div className="px-3.5 py-4 text-[11px] text-meta">
						Checking connections…
					</div>
				) : totalConnections === 0 ? (
					<div className="px-4 py-8 text-center text-[13px] text-meta dark:text-panel-dim">
						No side channels configured
					</div>
				) : (
					<>
					{connections.map((connection, index) => (
						<div
							key={connection.id}
							className={`flex items-center gap-3 px-3.5 py-3 ${
								index > 0 ? "border-t border-hairline" : ""
							}`}
						>
							<SlackLogo className="size-8 shadow-none" />
							<div className="min-w-0 flex-1">
								<div className="flex items-center gap-2">
									<p className="truncate text-[12.5px] font-semibold text-foreground">
										{connection.slackTeamName ?? "Slack workspace"}
									</p>
									{connection.botName && (
										<span className="truncate text-[10.5px] text-meta">
											{connection.botName}
										</span>
									)}
								</div>
							</div>
							<span className="shrink-0 rounded-[4px] bg-success-bg px-2 py-0.5 text-[9.5px] font-semibold text-success dark:bg-emerald-950 dark:text-emerald-300">
								{statusLabel(connection)}
							</span>
							{canManage && !readOnly && (
								<button
									type="button"
									onClick={() => {
										openConfiguration(connection);
									}}
									className="flex shrink-0 cursor-pointer items-center gap-1.5 rounded-[6px] border border-input bg-background px-2.5 py-1.5 text-[11px] font-semibold text-foreground transition-colors hover:border-border-hover"
								>
									<Settings2 className="size-3" />
									Configure
								</button>
							)}
						</div>
					))}
					{telegramConnections.map((connection, index) => (
						<div
							key={connection.id}
							className={`flex items-center gap-3 px-3.5 py-3 ${
								connections.length > 0 || index > 0
									? "border-t border-hairline"
									: ""
							}`}
						>
							<TelegramLogo className="size-8" />
							<div className="min-w-0 flex-1">
								<div className="flex items-center gap-2">
									<p className="truncate text-[12.5px] font-semibold text-foreground">
										@{connection.botUsername ?? "Telegram bot"}
									</p>
									{connection.botName && (
										<span className="truncate text-[10.5px] text-meta">
											{connection.botName}
										</span>
									)}
								</div>
							</div>
							<span className="shrink-0 rounded-[4px] bg-success-bg px-2 py-0.5 text-[9.5px] font-semibold text-success dark:bg-emerald-950 dark:text-emerald-300">
								{statusLabel(connection)}
							</span>
							{canManage && !readOnly && (
								<button
									type="button"
									onClick={() => {
										setSaveError(null);
										setSelectedTelegram(connection);
										setTelegramDialogOpen(true);
									}}
									className="flex shrink-0 cursor-pointer items-center gap-1.5 rounded-[6px] border border-input bg-background px-2.5 py-1.5 text-[11px] font-semibold text-foreground transition-colors hover:border-border-hover"
								>
									<Settings2 className="size-3" />
									Configure
								</button>
							)}
						</div>
					))}
					</>
				)}

				{loadError && (
					<div className="border-t border-border bg-destructive/5 px-3.5 py-2.5 dark:border-white/10">
						<p className="text-[10.5px] text-destructive">{loadError}</p>
						<button
							type="button"
							onClick={() => {
								void load();
							}}
							className="mt-1 cursor-pointer text-[10.5px] font-semibold text-petrol hover:underline"
						>
							Retry
						</button>
					</div>
				)}
			</div>

			<Dialog open={pickerOpen} onOpenChange={setPickerOpen}>
				<DialogContent
					className="gap-0 overflow-hidden p-0 sm:max-w-[480px]"
					onKeyDown={handleKeyboardListNavigation}
				>
					<DialogHeader className="border-b border-border px-5 py-4 pr-14 dark:border-white/10">
						<DialogTitle>Add Side-Channel</DialogTitle>
						<DialogDescription className="mt-0.5">
							Choose where people can talk to this agent.
						</DialogDescription>
					</DialogHeader>
					<div className="space-y-2.5 p-5">
						<button
							type="button"
							data-keyboard-option="true"
							onClick={chooseSlack}
							className="group flex w-full cursor-pointer items-center gap-3 rounded-[10px] border border-border bg-card p-3.5 text-left transition-all hover:border-petrol/35 hover:bg-petrol/[0.035] dark:border-white/10"
						>
							<SlackLogo className="size-10 shadow-none" />
							<span className="min-w-0 flex-1">
								<span className="block text-[13px] font-semibold text-foreground">
									Slack
								</span>
								<span className="mt-0.5 block text-[10.5px] leading-4 text-meta">
									Install a dedicated bot in a Slack workspace.
								</span>
							</span>
							<span className="flex size-7 items-center justify-center rounded-[7px] border border-input bg-background text-subtle transition-colors group-hover:border-petrol/35 group-hover:text-petrol">
								<Plus className="size-3.5" />
							</span>
						</button>
						<button
							type="button"
							data-keyboard-option="true"
							onClick={chooseTelegram}
							className="group flex w-full cursor-pointer items-center gap-3 rounded-[10px] border border-border bg-card p-3.5 text-left transition-all hover:border-[#2AABEE]/40 hover:bg-sky-50/60 dark:border-white/10 dark:hover:bg-sky-950/20"
						>
							<span className="flex size-10 shrink-0 items-center justify-center rounded-[8px] border border-border bg-background shadow-sm dark:border-white/10">
								<TelegramLogo className="size-[62%]" />
							</span>
							<span className="min-w-0 flex-1">
								<span className="block text-[13px] font-semibold text-foreground">
									Telegram
								</span>
								<span className="mt-0.5 block text-[10.5px] leading-4 text-meta">
									Connect a BotFather bot for direct messages, groups, and
									topics.
								</span>
							</span>
							<span className="flex size-7 items-center justify-center rounded-[7px] border border-input bg-background text-subtle transition-colors group-hover:border-[#2AABEE]/40 group-hover:text-[#2AABEE]">
								<Plus className="size-3.5" />
							</span>
						</button>
					</div>
				</DialogContent>
			</Dialog>

			{selected && dialogOpen && (
				<AgentSlackBotDialog
					key={selected.id ?? "new-slack-channel"}
					open={dialogOpen}
					onOpenChange={(open) => {
						setDialogOpen(open);
						if (!open) setSelected(null);
					}}
					settings={selected}
					saving={saving}
					error={saveError}
					onSave={save}
					onDisconnect={
						selected.id ? () => disconnect(selected) : undefined
					}
				/>
			)}
			{selectedTelegram && telegramDialogOpen && (
				<AgentTelegramBotDialog
					key={selectedTelegram.id ?? "new-telegram-channel"}
					open={telegramDialogOpen}
					onOpenChange={(open) => {
						setTelegramDialogOpen(open);
						if (!open) setSelectedTelegram(null);
					}}
					settings={selectedTelegram}
					saving={saving}
					error={saveError}
					onSave={saveTelegram}
					onDisconnect={
						selectedTelegram.id
							? () => disconnectTelegram(selectedTelegram)
							: undefined
					}
				/>
			)}
		</section>
	);
}
