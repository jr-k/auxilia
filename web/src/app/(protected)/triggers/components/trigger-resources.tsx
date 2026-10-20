"use client";

import { useEffect, useMemo, useState } from "react";
import { Bot, LoaderCircle } from "lucide-react";
import type { Agent } from "@/types/agents";
import { canConfigureAgent } from "@/types/agents";
import * as agentsApi from "@/lib/api/resources/agents";
import AgentToolList from "@/app/(protected)/agents/[id]/components/agent-tool-list";
import AgentSkillList from "@/app/(protected)/agents/[id]/components/agent-skill-list";
import AgentSubagentList from "@/app/(protected)/agents/[id]/components/agent-subagent-list";
import { fromAgent } from "@/app/(protected)/agents/lib/agent-form";

interface TriggerResourcesProps {
	agentId: string | null;
	disabledMcpServerIds: string[] | null;
	disabledSkillIds: string[] | null;
	disabledSandboxIds: string[] | null;
	disabledSubagentIds: string[] | null;
	disabledMcpTools: Record<string, string[]> | null;
	readOnly?: boolean;
	onDisabledMcpServerIdsChange?: (ids: string[]) => void;
	onDisabledSkillIdsChange?: (ids: string[]) => void;
	onDisabledSandboxIdsChange?: (ids: string[]) => void;
	onDisabledSubagentIdsChange?: (ids: string[]) => void;
	onDisabledMcpToolsChange?: (tools: Record<string, string[]>) => void;
}

function isEnabled(
	resourceId: string,
	disabledIds: string[] | null,
	enabledByDefault?: boolean,
): boolean {
	return disabledIds === null
		? enabledByDefault !== false
		: !disabledIds.includes(resourceId);
}

export default function TriggerResources({
	agentId,
	disabledMcpServerIds,
	disabledSkillIds,
	disabledSandboxIds,
	disabledSubagentIds,
	disabledMcpTools,
	readOnly = false,
	onDisabledMcpServerIdsChange,
	onDisabledSkillIdsChange,
	onDisabledSandboxIdsChange,
	onDisabledSubagentIdsChange,
	onDisabledMcpToolsChange,
}: TriggerResourcesProps) {
	const [result, setResult] = useState<{
		agentId: string;
		agent: Agent | null;
		failed: boolean;
	} | null>(null);

	useEffect(() => {
		if (!agentId) return;
		let active = true;
		void agentsApi
			.getAgent(agentId)
			.then((loadedAgent) => {
				if (!active) return;
				setResult({
					agentId,
					agent: loadedAgent,
					failed: false,
				});
			})
			.catch(() => {
				if (!active) return;
				setResult({
					agentId,
					agent: null,
					failed: true,
				});
			});
		return () => {
			active = false;
		};
	}, [agentId]);

	const agent = result?.agentId === agentId ? result.agent : null;
	const agentForm = useMemo(() => (agent ? fromAgent(agent) : null), [agent]);
	const mcpServers = useMemo(
		() =>
			(agentForm?.mcpServers ?? []).map((server) => ({
				...server,
				enabledByDefault: isEnabled(
					server.mcpServerId,
					disabledMcpServerIds,
					server.enabledByDefault,
				),
			})),
		[agentForm, disabledMcpServerIds],
	);
	const sandboxes = useMemo(
		() =>
			(agentForm?.sandboxes ?? []).map((sandbox) => ({
				...sandbox,
				enabledByDefault: isEnabled(
					sandbox.sandboxId,
					disabledSandboxIds,
					sandbox.enabledByDefault,
				),
			})),
		[agentForm, disabledSandboxIds],
	);
	const disabledSkills =
		disabledSkillIds ?? agentForm?.disabledSkillIdsByDefault ?? [];
	const disabledSubagents =
		disabledSubagentIds ?? agentForm?.disabledSubagentIdsByDefault ?? [];
	const effectiveDisabledMcpTools = useMemo(() => {
		if (disabledMcpTools !== null) return disabledMcpTools;
		return Object.fromEntries(
			(agentForm?.mcpServers ?? []).map((server) => [
				server.mcpServerId,
				Object.entries(server.tools ?? {})
					.filter(([, status]) => status === "needs_approval")
					.map(([toolName]) => toolName),
			]),
		);
	}, [agentForm, disabledMcpTools]);
	const isLoading = Boolean(agentId && result?.agentId !== agentId);

	if (!agentId) {
		return (
			<div className="flex min-h-[280px] flex-col items-center justify-center rounded-xl border border-dashed border-input/80 px-6 text-center">
				<span className="flex size-10 items-center justify-center rounded-xl bg-card text-meta shadow-sm dark:bg-white/5 dark:text-panel-dim">
					<Bot className="size-5" />
				</span>
				<p className="mt-3 text-[13px] font-semibold text-foreground">
					Select an agent first
				</p>
				<p className="mt-1 max-w-[260px] text-[11.5px] leading-5 text-meta dark:text-panel-dim">
					Its allowed tools, sandbox, skills and subagents will appear here.
				</p>
			</div>
		);
	}

	if (isLoading) {
		return (
			<div className="flex min-h-[280px] items-center justify-center gap-2 text-[12.5px] text-meta dark:text-panel-dim">
				<LoaderCircle className="size-4 animate-spin" />
				Loading agent resources…
			</div>
		);
	}

	if (result?.agentId === agentId && result.failed) {
		return (
			<div className="rounded-[10px] bg-destructive/10 px-4 py-3 text-[12.5px] font-medium text-destructive">
				Could not load this agent&apos;s resources.
			</div>
		);
	}
	if (!agent) return null;

	return (
		<div key={agent.id} className="flex min-w-0 flex-col">
			<AgentToolList
				agentId={agent.id}
				readOnly
				canToggleDefault={!readOnly}
				mode="trigger"
				triggerToolsReadOnly={readOnly}
				canEdit={canConfigureAgent(agent.currentUserPermission)}
				mcpServers={mcpServers}
				sandboxes={sandboxes}
				triggerDisabledTools={effectiveDisabledMcpTools}
				onMcpServersChange={(update) => {
					const next = update(mcpServers);
					onDisabledMcpServerIdsChange?.(
						next
							.filter((server) => server.enabledByDefault === false)
							.map((server) => server.mcpServerId),
					);
				}}
				onSandboxesChange={(next) => {
					onDisabledSandboxIdsChange?.(
						next
							.filter((sandbox) => sandbox.enabledByDefault === false)
							.map((sandbox) => sandbox.sandboxId),
					);
				}}
				onTriggerToolEnabledChange={(serverId, toolName, enabled) => {
					const rejected = new Set(
						effectiveDisabledMcpTools[serverId] ?? [],
					);
					if (enabled) rejected.delete(toolName);
					else rejected.add(toolName);
					onDisabledMcpToolsChange?.({
						...effectiveDisabledMcpTools,
						[serverId]: [...rejected],
					});
				}}
			/>
			<AgentSkillList
				readOnly
				canToggleDefault={!readOnly}
				mode="trigger"
				skillIds={agentForm?.skillIds ?? []}
				disabledByDefaultIds={disabledSkills}
				fallbackSkills={agent.skills ?? []}
				runsCode={sandboxes.length > 0}
				onDefaultEnabledChange={(skillId, enabled) => {
					onDisabledSkillIdsChange?.(
						enabled
							? disabledSkills.filter((id) => id !== skillId)
							: [...new Set([...disabledSkills, skillId])],
					);
				}}
			/>
			<AgentSubagentList
				readOnly
				canToggleDefault={!readOnly}
				mode="trigger"
				agentId={agent.id}
				isSubagent={agent.isSubagent}
				subagentIds={agentForm?.subagentIds ?? []}
				disabledByDefaultIds={disabledSubagents}
				fallbackSubagents={agent.subagents}
				onDefaultEnabledChange={(subagentId, enabled) => {
					onDisabledSubagentIdsChange?.(
						enabled
							? disabledSubagents.filter((id) => id !== subagentId)
							: [...new Set([...disabledSubagents, subagentId])],
					);
				}}
			/>
		</div>
	);
}
