"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, Settings2 } from "lucide-react";
import { useConfirmDialog } from "@/components/providers/dialog-provider";
import { SlackLogo } from "@/components/slack-logo";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { getApiErrorMessage } from "@/lib/api/errors";
import * as agentsApi from "@/lib/api/resources/agents";
import { useAppearanceStore } from "@/stores/appearance-store";
import type {
	AgentSlackBotSettings,
	AgentSlackBotSettingsUpdate,
} from "@/types/agents";
import AgentSlackBotDialog from "./agent-slack-bot-dialog";

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
	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState<string | null>(null);
	const [pickerOpen, setPickerOpen] = useState(false);
	const [dialogOpen, setDialogOpen] = useState(false);
	const [saving, setSaving] = useState(false);
	const [saveError, setSaveError] = useState<string | null>(null);

	const load = useCallback(async () => {
		setLoading(true);
		setLoadError(null);
		try {
			const [nextConnections, nextSetup] = await Promise.all([
				agentsApi.listAgentSlackBots(agentId),
				agentsApi.getAgentSlackBotSetup(agentId),
			]);
			setConnections(nextConnections);
			setSetup(nextSetup);
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

	return (
		<section className="mt-8">
			<div className="mb-2 flex items-center justify-between gap-4">
				<span className="text-[10.5px] font-semibold text-subtle dark:text-panel-dim">
					Side-Channels{" "}
					<span className="tracking-normal text-meta dark:text-panel-dim">
						{connections.length}
					</span>
				</span>
				{canManage && !readOnly && setup && (
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

			<div className="overflow-hidden rounded-[10px] border border-border bg-card dark:border-white/10">
				{loading ? (
					<div className="px-3.5 py-4 text-[11px] text-meta">
						Checking connections…
					</div>
				) : connections.length === 0 ? (
					<div className="flex items-center gap-3 px-3.5 py-4">
						<div className="flex size-8 items-center justify-center rounded-[8px] border border-dashed border-border text-meta">
							<Plus className="size-3.5" />
						</div>
						<div>
							<p className="text-[12px] font-semibold text-foreground">
								No side-channels connected
							</p>
							<p className="mt-0.5 text-[10.5px] text-meta">
								Add Slack to make this agent available to another workspace.
							</p>
						</div>
					</div>
				) : (
					connections.map((connection, index) => (
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
							<span className="shrink-0 rounded-[4px] bg-success-bg px-2 py-0.5 text-[9.5px] font-semibold text-success">
								Connected
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
					))
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
				<DialogContent className="gap-0 overflow-hidden p-0 sm:max-w-[480px]">
					<DialogHeader className="border-b border-border px-5 py-4 pr-14 dark:border-white/10">
						<DialogTitle>Add Side-Channel</DialogTitle>
						<DialogDescription className="mt-0.5">
							Choose where people can talk to this agent.
						</DialogDescription>
					</DialogHeader>
					<div className="p-5">
						<button
							type="button"
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
		</section>
	);
}
