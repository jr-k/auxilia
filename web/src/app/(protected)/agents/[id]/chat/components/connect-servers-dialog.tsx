"use client";

import Link from "next/link";
import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
	DialogDescription,
} from "@/components/ui/dialog";
import * as agentsApi from "@/lib/api/resources/agents";
import * as mcpServersApi from "@/lib/api/resources/mcp-servers";
import type { MCPServer } from "@/types/mcp-servers";
import type {
	AgentResourceMCPServer,
	AgentResources,
} from "@/types/agents";
import type { ThreadResourceSettings } from "@/types/threads";
import {
	ExternalLinkIcon,
	LoaderIcon,
	PlugIcon,
	SparklesIcon,
} from "lucide-react";
import { toast } from "sonner";
import { ServerIconTile } from "@/app/(protected)/mcp-servers/components/server-icon-tile";
import { SkillAvatar } from "@/components/ui/skill-avatar";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

interface ConnectServersDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	agentId: string;
	disconnectedServers: MCPServer[];
	onConnectionChange: () => void;
	resourceSettings: ThreadResourceSettings;
	onResourceSettingsChange: (settings: ThreadResourceSettings) => void;
	resourceSettingsSaving?: boolean;
}

type ResourceTab = "servers" | "skills";

export function ConnectServersDialog({
	open,
	onOpenChange,
	agentId,
	disconnectedServers,
	onConnectionChange,
	resourceSettings,
	onResourceSettingsChange,
	resourceSettingsSaving = false,
}: ConnectServersDialogProps) {
	const [activeTab, setActiveTab] = useState<ResourceTab>("servers");
	const [resources, setResources] = useState<AgentResources | null>(null);
	const [resourcesAgentId, setResourcesAgentId] = useState<string | null>(null);
	const [loadFailedFor, setLoadFailedFor] = useState<string | null>(null);
	const [connectedIds, setConnectedIds] = useState<Set<string>>(new Set());
	const [connectingId, setConnectingId] = useState<string | null>(null);
	const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
	const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const resourceRequestRef = useRef(0);

	const disconnectedIds = useMemo(
		() => new Set(disconnectedServers.map((server) => server.id)),
		[disconnectedServers],
	);
	const servers = resources?.mcpServers ?? [];
	const skills = resources?.skills ?? [];
	const disabledServerIds = useMemo(
		() => new Set(resourceSettings.disabledMcpServerIds),
		[resourceSettings.disabledMcpServerIds],
	);
	const disabledSkillIds = useMemo(
		() => new Set(resourceSettings.disabledSkillIds),
		[resourceSettings.disabledSkillIds],
	);
	const enabledServerCount = servers.filter(
		(server) => !disabledServerIds.has(server.id),
	).length;
	const enabledSkillCount = skills.filter(
		(skill) => !disabledSkillIds.has(skill.id),
	).length;
	const isLoadingResources =
		open && resourcesAgentId !== agentId && loadFailedFor !== agentId;

	const clearPolling = useCallback(() => {
		if (pollRef.current) clearInterval(pollRef.current);
		if (timeoutRef.current) clearTimeout(timeoutRef.current);
		pollRef.current = null;
		timeoutRef.current = null;
	}, []);

	const handleOpenChange = (nextOpen: boolean) => {
		if (!nextOpen) {
			clearPolling();
			setConnectingId(null);
		}
		onOpenChange(nextOpen);
	};

	useEffect(() => {
		if (!open) return;
		const requestId = ++resourceRequestRef.current;
		void agentsApi
			.getAgentResources(agentId)
			.then((loadedResources) => {
				if (requestId !== resourceRequestRef.current) return;
				setResources(loadedResources);
				setResourcesAgentId(agentId);
				setLoadFailedFor(null);
			})
			.catch((error: unknown) => {
				if (requestId !== resourceRequestRef.current) return;
				console.error("Failed to load agent resources:", error);
				setResources(null);
				setResourcesAgentId(null);
				setLoadFailedFor(agentId);
			});
		return () => {
			resourceRequestRef.current += 1;
		};
	}, [agentId, open]);

	useEffect(() => clearPolling, [clearPolling]);

	const markConnected = useCallback(
		(serverId: string) => {
			setConnectedIds((previous) => new Set(previous).add(serverId));
			setConnectingId(null);
			onConnectionChange();
		},
		[onConnectionChange],
	);

	const handleConnect = useCallback(
		async (server: AgentResourceMCPServer) => {
			setConnectingId(server.id);

			try {
				const result = await mcpServersApi.listMcpServerTools(server.id);

				if (result.status === "ok") {
					markConnected(server.id);
					return;
				}

				const popup = window.open(
					result.authUrl,
					"_blank",
					"width=600,height=700",
				);
				if (!popup) {
					toast.error(`Allow pop-ups to connect ${server.name}.`);
					setConnectingId(null);
					return;
				}

				let connectionHandled = false;
				const poll = async () => {
					try {
						const connected = await mcpServersApi.isMcpServerConnected(
							server.id,
						);
						if (!connected || connectionHandled) return;
						connectionHandled = true;
						clearPolling();
						if (!popup.closed) popup.close();
						markConnected(server.id);
					} catch {
						// A transient probe failure should not stop OAuth polling.
					}
				};
				pollRef.current = setInterval(() => {
					void poll();
				}, 2000);
				timeoutRef.current = setTimeout(() => {
					clearPolling();
					setConnectingId(null);
					toast.error(`Connection to ${server.name} timed out.`);
				}, 60000);
			} catch (error: unknown) {
				console.error("Failed to connect:", error);
				setConnectingId(null);
				toast.error(`Could not connect ${server.name}.`);
			}
		},
		[clearPolling, markConnected],
	);

	const setResourceEnabled = (
		type: ResourceTab,
		resourceId: string,
		enabled: boolean,
	) => {
		const disabledKey =
			type === "servers" ? "disabledMcpServerIds" : "disabledSkillIds";
		const disabledIds = resourceSettings[disabledKey];
		onResourceSettingsChange({
			...resourceSettings,
			[disabledKey]: enabled
				? disabledIds.filter((id) => id !== resourceId)
				: [...new Set([...disabledIds, resourceId])],
		});
	};

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent className="gap-4 sm:max-w-[540px]">
				<DialogHeader>
					<DialogTitle>Conversation resources</DialogTitle>
					<DialogDescription>
						Choose which MCP servers and skills are available in this
						conversation.
					</DialogDescription>
				</DialogHeader>

				<div
					role="tablist"
					aria-label="Agent resource type"
					className="grid grid-cols-2 rounded-full bg-hover p-1 dark:bg-white/5"
				>
					{(
						[
							["servers", "MCP servers", PlugIcon],
							["skills", "Skills", SparklesIcon],
						] as const
					).map(([tab, label, Icon]) => {
						const isActive = activeTab === tab;
						return (
							<button
								key={tab}
								type="button"
								role="tab"
								aria-selected={isActive}
								onClick={() => {
									setActiveTab(tab);
								}}
								className={cn(
									"flex h-9 cursor-pointer items-center justify-center gap-2 rounded-full text-[12.5px] font-semibold transition-all",
									isActive
										? "bg-card text-foreground shadow-sm dark:bg-white/10"
										: "text-meta hover:text-foreground dark:text-panel-dim",
								)}
							>
								<Icon className="size-3.5" />
								{label}
								{resourcesAgentId === agentId && (
									<span className="text-[10.5px] font-medium opacity-60">
										{tab === "servers"
											? `${enabledServerCount}/${servers.length}`
											: `${enabledSkillCount}/${skills.length}`}
									</span>
								)}
							</button>
						);
					})}
				</div>

				<div className="h-[480px] overflow-y-auto [scrollbar-width:thin]">
					{isLoadingResources ? (
						<div className="flex min-h-[180px] items-center justify-center gap-2 text-[13px] text-meta dark:text-panel-dim">
							<LoaderIcon className="size-4 animate-spin" />
							Loading resources…
						</div>
					) : activeTab === "servers" ? (
						servers.length > 0 ? (
							<div className="flex flex-col gap-2">
								{servers.map((server) => {
									const isEnabled = !disabledServerIds.has(server.id);
									const isDisconnected =
										disconnectedIds.has(server.id) &&
										!connectedIds.has(server.id);
									const isConnecting = connectingId === server.id;
									return (
										<div
											key={server.id}
											className="flex items-center gap-3 rounded-[10px] border border-hairline bg-sidebar p-3 dark:bg-white/5"
										>
											<ServerIconTile
												iconUrl={server.iconUrl}
												serverId={server.id}
												imageRevision={server.imageRevision}
												name={server.name}
												size={32}
											/>
											<p className="min-w-0 flex-1 truncate text-[13px] font-semibold text-ink dark:text-panel-button">
												{server.name}
											</p>
											<div className="ml-auto flex shrink-0 items-center gap-2">
												<ConnectionStatusBadge connected={!isDisconnected} />
												{isEnabled && isDisconnected && (
													<button
														type="button"
														disabled={connectingId !== null}
														onClick={() => {
															void handleConnect(server);
														}}
														className="flex h-8 min-w-[82px] cursor-pointer items-center justify-center gap-1.5 rounded-full bg-petrol px-3 text-[11.5px] font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-55"
													>
														{isConnecting ? (
															<LoaderIcon className="size-3.5 animate-spin" />
														) : (
															<PlugIcon className="size-3.5" />
														)}
														{isConnecting ? "Waiting…" : "Connect"}
													</button>
												)}
												<Switch
													checked={isEnabled}
													disabled={resourceSettingsSaving}
													onCheckedChange={(checked) => {
														setResourceEnabled("servers", server.id, checked);
													}}
													aria-label={`${isEnabled ? "Disable" : "Enable"} ${server.name} for this conversation`}
												/>
											</div>
										</div>
									);
								})}
							</div>
						) : (
							<EmptyState
								icon={PlugIcon}
								title="No MCP servers"
								description="This agent has no MCP server enabled."
							/>
						)
					) : skills.length > 0 ? (
						<div className="flex flex-col gap-2">
							{skills.map((skill) => {
								const isEnabled = !disabledSkillIds.has(skill.id);
								return (
									<div
										key={skill.id}
										className="flex items-center gap-3 rounded-[10px] border border-hairline bg-sidebar p-3 dark:bg-white/5"
									>
										<Link
											href={`/skills/${skill.id}`}
											target="_blank"
											rel="noreferrer"
											className="group flex min-w-0 flex-1 items-center gap-3 rounded-md"
										>
											<SkillAvatar
												skillId={skill.id}
												name={skill.name}
												emoji={skill.emoji}
												color={skill.color}
												imageRevision={skill.imageRevision}
												size="sm"
											/>
											<div className="min-w-0 flex-1">
												<p className="truncate text-[13px] font-semibold text-ink dark:text-panel-button">
													{skill.name}
												</p>
												{skill.description && (
													<p className="mt-0.5 truncate text-[11.5px] text-meta dark:text-panel-dim">
														{skill.description}
													</p>
												)}
											</div>
											<ExternalLinkIcon className="size-3.5 shrink-0 text-meta transition-colors group-hover:text-petrol dark:text-panel-dim" />
										</Link>
										<Switch
											checked={isEnabled}
											disabled={resourceSettingsSaving}
											onCheckedChange={(checked) => {
												setResourceEnabled("skills", skill.id, checked);
											}}
											aria-label={`${isEnabled ? "Disable" : "Enable"} ${skill.name} for this conversation`}
										/>
									</div>
								);
							})}
						</div>
					) : (
						<EmptyState
							icon={SparklesIcon}
							title="No skills"
							description="This agent has no skill enabled."
						/>
					)}
				</div>
			</DialogContent>
		</Dialog>
	);
}

function ConnectionStatusBadge({ connected }: { connected: boolean }) {
	return (
		<span
			className={cn(
				"inline-flex shrink-0 items-center gap-1.5 rounded-[4px] px-2 py-[3px] text-[9.5px] font-semibold",
				connected
					? "bg-success-bg text-success dark:bg-emerald-950 dark:text-emerald-300"
					: "bg-[#FBEFED] text-[#B04A3A] dark:bg-[#B04A3A]/15 dark:text-[#E58A7D]",
			)}
		>
			<span
				className={cn(
					"size-[5px] rounded-full",
					connected ? "bg-success" : "bg-[#B04A3A]",
				)}
			/>
			{connected ? "Connected" : "Not connected"}
		</span>
	);
}

function EmptyState({
	icon: Icon,
	title,
	description,
}: {
	icon: typeof PlugIcon;
	title: string;
	description: string;
}) {
	return (
		<div className="flex min-h-[180px] flex-col items-center justify-center text-center">
			<div className="mb-3 flex size-10 items-center justify-center rounded-full bg-hover text-meta dark:bg-white/5 dark:text-panel-dim">
				<Icon className="size-4" />
			</div>
			<p className="text-[13px] font-semibold text-foreground">{title}</p>
			<p className="mt-1 text-[11.5px] text-meta dark:text-panel-dim">
				{description}
			</p>
		</div>
	);
}
