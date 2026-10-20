"use client";

import { useEffect, useMemo, useState } from "react";
import {
	Bot,
	Box,
	Boxes,
	GitFork,
	LoaderCircle,
	Sparkles,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Agent, AgentResources } from "@/types/agents";
import * as agentsApi from "@/lib/api/resources/agents";
import { humanizeToolName } from "@/components/ai-elements/chain-of-thought";
import { AgentAvatar } from "@/components/ui/agent-avatar";
import { SkillAvatar } from "@/components/ui/skill-avatar";
import { SandboxIcon } from "@/components/sandbox-icon";
import { ServerIconTile } from "@/app/(protected)/mcp-servers/components/server-icon-tile";
import { SANDBOX_PROVIDER_LABELS } from "@/lib/sandbox-providers";
import { cn } from "@/lib/utils";

interface TriggerResourcesProps {
	agentId: string | null;
	disabledMcpServerIds: string[] | null;
	disabledSkillIds: string[] | null;
	disabledSandboxIds: string[] | null;
	disabledSubagentIds: string[] | null;
}

interface ResourceSectionProps {
	icon: LucideIcon;
	title: string;
	count: number;
	empty: string;
	children: React.ReactNode;
}

function ResourceSection({
	icon: Icon,
	title,
	count,
	empty,
	children,
}: ResourceSectionProps) {
	return (
		<section>
			<div className="mb-2.5 flex items-center gap-2">
				<Icon className="size-3.5 text-petrol dark:text-panel-terminal" />
				<h3 className="text-[10.5px] font-semibold uppercase tracking-[0.06em] text-label dark:text-muted-foreground">
					{title}
				</h3>
				<span className="font-mono text-[10px] text-meta dark:text-panel-dim">
					{count}
				</span>
			</div>
			{count > 0 ? (
				<div className="flex flex-col gap-2">{children}</div>
			) : (
				<div className="rounded-[10px] border border-dashed border-input/80 px-3.5 py-4 text-center text-[12px] text-meta dark:text-panel-dim">
					{empty}
				</div>
			)}
		</section>
	);
}

function ResourceStateBadge({
	enabled,
	inherited,
}: {
	enabled: boolean;
	inherited: boolean;
}) {
	if (enabled) return null;
	return (
		<span className="shrink-0 rounded-full bg-hover px-2 py-0.5 text-[9.5px] font-semibold whitespace-nowrap text-meta dark:bg-white/5 dark:text-panel-dim">
			{inherited ? "Off by default" : "Disabled"}
		</span>
	);
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
}: TriggerResourcesProps) {
	const [result, setResult] = useState<{
		agentId: string;
		agent: Agent | null;
		resources: AgentResources | null;
		failed: boolean;
	} | null>(null);

	useEffect(() => {
		if (!agentId) return;
		let active = true;
		void Promise.all([
			agentsApi.getAgent(agentId),
			agentsApi.getAgentResources(agentId),
		])
			.then(([loadedAgent, loadedResources]) => {
				if (!active) return;
				setResult({
					agentId,
					agent: loadedAgent,
					resources: loadedResources,
					failed: false,
				});
			})
			.catch(() => {
				if (!active) return;
				setResult({
					agentId,
					agent: null,
					resources: null,
					failed: true,
				});
			});
		return () => {
			active = false;
		};
	}, [agentId]);

	const agent = result?.agentId === agentId ? result.agent : null;
	const resources = result?.agentId === agentId ? result.resources : null;
	const toolGroups = useMemo(
		() => (resources?.mcpServers ?? []).filter((server) => server.toolNames.length > 0),
		[resources],
	);
	const toolCount = toolGroups.reduce(
		(total, server) => total + server.toolNames.length,
		0,
	);
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
		<div className="flex flex-col gap-7">
			<div>
				<p className="text-[13px] font-semibold text-foreground">
					Available to {agent.name}
				</p>
				<p className="mt-1 text-[11.5px] leading-5 text-meta dark:text-panel-dim">
					Triggers inherit the agent&apos;s saved resource permissions.
				</p>
			</div>

			<ResourceSection
				icon={Boxes}
				title="Tools"
				count={toolCount}
				empty="No MCP tools allowed"
			>
				{toolGroups.map((server) => {
					const enabled = isEnabled(
						server.id,
						disabledMcpServerIds,
						server.enabledByDefault,
					);
					return (
						<div
							key={server.id}
							className={cn(
								"overflow-hidden rounded-[10px] border border-hairline bg-card dark:border-white/8 dark:bg-white/[0.035]",
								!enabled && "opacity-65",
							)}
						>
						<div className="flex items-center gap-2.5 border-b border-hairline px-3 py-2.5 dark:border-white/8">
							<ServerIconTile
								iconUrl={server.iconUrl}
								serverId={server.id}
								imageRevision={server.imageRevision}
								name={server.name}
								size={26}
							/>
							<span className="min-w-0 flex-1 truncate text-[12px] font-semibold text-foreground">
								{server.name}
							</span>
							<ResourceStateBadge
								enabled={enabled}
								inherited={disabledMcpServerIds === null}
							/>
						</div>
						<div className="flex flex-wrap gap-1.5 px-3 py-2.5">
							{server.toolNames.map((name) => (
								<span
									key={name}
									className="max-w-full truncate rounded-md bg-sidebar px-2 py-1 text-[10.5px] font-medium text-foreground dark:bg-white/5"
								>
									{humanizeToolName(name)}
								</span>
							))}
						</div>
						</div>
					);
				})}
			</ResourceSection>

			<ResourceSection
				icon={Box}
				title="Sandboxes"
				count={resources?.sandboxes.length ?? 0}
				empty="No sandbox allowed"
			>
				{(resources?.sandboxes ?? []).map((sandbox) => {
					const enabled = isEnabled(
						sandbox.id,
						disabledSandboxIds,
						sandbox.enabledByDefault,
					);
					return (
						<div
							key={sandbox.id}
							className={cn(
								"flex items-center gap-3 rounded-[10px] border border-hairline bg-card px-3 py-2.5 dark:border-white/8 dark:bg-white/[0.035]",
								!enabled && "opacity-65",
							)}
						>
						<span className="flex size-8 shrink-0 items-center justify-center rounded-[8px] bg-sidebar dark:bg-white/5">
							<SandboxIcon
								sandboxId={sandbox.id}
								imageRevision={sandbox.imageRevision}
								provider={sandbox.provider}
								size={17}
							/>
						</span>
						<div className="min-w-0 flex-1">
							<p className="truncate text-[12px] font-semibold text-foreground">
								{sandbox.name}
							</p>
							<p className="truncate text-[10.5px] text-meta dark:text-panel-dim">
								{SANDBOX_PROVIDER_LABELS[sandbox.provider]}
							</p>
						</div>
							<ResourceStateBadge
								enabled={enabled}
								inherited={disabledSandboxIds === null}
							/>
						</div>
					);
				})}
			</ResourceSection>

			<ResourceSection
				icon={Sparkles}
				title="Skills"
				count={resources?.skills.length ?? 0}
				empty="No skills allowed"
			>
				{(resources?.skills ?? []).map((skill) => {
					const enabled = isEnabled(
						skill.id,
						disabledSkillIds,
						skill.enabledByDefault,
					);
					return (
						<div
							key={skill.id}
							className={cn(
								"flex items-center gap-3 rounded-[10px] border border-hairline bg-card px-3 py-2.5 dark:border-white/8 dark:bg-white/[0.035]",
								!enabled && "opacity-65",
							)}
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
							<p className="truncate text-[12px] font-semibold text-foreground">
								{skill.name}
							</p>
							{skill.description && (
								<p className="truncate text-[10.5px] text-meta dark:text-panel-dim">
									{skill.description}
								</p>
							)}
						</div>
							<ResourceStateBadge
								enabled={enabled}
								inherited={disabledSkillIds === null}
							/>
						</div>
					);
				})}
			</ResourceSection>

			<ResourceSection
				icon={GitFork}
				title="Subagents"
				count={resources?.subagents.length ?? 0}
				empty="No subagents allowed"
			>
				{(resources?.subagents ?? []).map((subagent) => {
					const enabled = isEnabled(
						subagent.id,
						disabledSubagentIds,
						subagent.enabledByDefault,
					);
					return (
						<div
							key={subagent.id}
							className={cn(
								"flex items-center gap-3 rounded-[10px] border border-hairline bg-card px-3 py-2.5 dark:border-white/8 dark:bg-white/[0.035]",
								!enabled && "opacity-65",
							)}
						>
						<AgentAvatar
							agentId={subagent.id}
							name={subagent.name}
							emoji={subagent.emoji}
							color={subagent.color}
							imageRevision={subagent.imageRevision}
							size="sm"
						/>
						<div className="min-w-0 flex-1">
							<p className="truncate text-[12px] font-semibold text-foreground">
								{subagent.name}
							</p>
							{subagent.description && (
								<p className="truncate text-[10.5px] text-meta dark:text-panel-dim">
									{subagent.description}
								</p>
							)}
						</div>
							<ResourceStateBadge
								enabled={enabled}
								inherited={disabledSubagentIds === null}
							/>
						</div>
					);
				})}
			</ResourceSection>
		</div>
	);
}
