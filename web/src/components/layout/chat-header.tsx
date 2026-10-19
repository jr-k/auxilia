"use client";

import { AlarmClock } from "lucide-react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import { useChatHeaderStore } from "@/stores/chat-header-store";
import { useModelsStore } from "@/stores/models-store";
import { ModelSelectorLogo } from "@/components/ai-elements/model-selector";
import {
	HoverCard,
	HoverCardContent,
	HoverCardTrigger,
} from "@/components/ui/hover-card";
import type { ThreadCost } from "@/lib/api/resources/thread-costs";
import { formatRunAt } from "@/lib/triggers/schedule";
import { AgentAvatar } from "@/components/ui/agent-avatar";
import { SidebarTrigger } from "@/components/ui/sidebar";
import ForbiddenErrorDialog from "@/components/forbidden-error-dialog";
import {
	AGENT_EDITOR_FORBIDDEN_MESSAGE,
	useOpenAgentEditor,
} from "@/hooks/use-open-agent-editor";

/** Pill amount: two decimals, or less than one cent. */
export function formatPillCost(amount: string): string {
	const value = Number(amount);
	return value > 0 && value < 0.01 ? "<\u20090.01$" : `${value.toFixed(2)}$`;
}

/** Hover amount: retain useful precision for small per-token totals. */
export function formatExactCost(amount: string): string {
	return `${Number(amount).toLocaleString("en-US", {
		maximumFractionDigits: 10,
	})}$`;
}

function CostBreakdown({ cost }: { cost: ThreadCost }) {
	const rows = [
		["Input", cost.usageDetails.input, cost.costDetails.input],
		[
			"Cached input",
			cost.usageDetails.inputCacheRead,
			cost.costDetails.inputCacheRead,
		],
		[
			"Cache write",
			cost.usageDetails.inputCacheCreation,
			cost.costDetails.inputCacheCreation,
		],
		["Output", cost.usageDetails.output, cost.costDetails.output],
	] as const;
	return (
		<div className="text-[12px]">
			<table className="w-full tabular-nums">
				<thead>
					<tr className="text-meta">
						<th className="pb-1 text-left font-medium" />
						<th className="pb-1 text-right font-medium">Tokens</th>
						<th className="pb-1 pl-4 text-right font-medium">Cost</th>
					</tr>
				</thead>
				<tbody>
					{rows.map(([label, tokens, amount]) => (
						<tr key={label}>
							<td className="py-0.5 text-subtle">{label}</td>
							<td className="py-0.5 text-right">
								{tokens.toLocaleString("en-US")}
							</td>
							<td className="py-0.5 pl-4 text-right font-mono">
								{formatExactCost(amount)}
							</td>
						</tr>
					))}
					<tr className="border-t border-border font-semibold">
						<td className="pt-1.5">Total</td>
						<td className="pt-1.5 text-right">
							{cost.usageDetails.total.toLocaleString("en-US")}
						</td>
						<td className="pt-1.5 pl-4 text-right font-mono">
							{formatExactCost(cost.costDetails.total)}
						</td>
					</tr>
				</tbody>
			</table>
			{!cost.complete && (
				<p className="mt-2 text-meta">
					{cost.unpricedCallCount} of {cost.callCount} calls have no price or
					usage; this subtotal covers priced calls only.
				</p>
			)}
		</div>
	);
}

function ModelCostPill() {
	const modelId = useChatHeaderStore((state) => state.modelId);
	const cost = useChatHeaderStore((state) => state.cost);
	const model = useModelsStore((state) =>
		state.models.find((candidate) => candidate.id === modelId),
	);
	if (!modelId) return null;

	const showCost = cost !== null && cost.callCount > 0;
	const pill = (
		<span
			title={showCost ? undefined : `Model: ${modelId}`}
			tabIndex={showCost ? 0 : undefined}
			className="hidden h-[30px] min-w-0 max-w-72 items-center gap-2 rounded-full border border-border bg-white px-3 text-[13px] font-medium text-foreground outline-none focus-visible:ring-2 focus-visible:ring-petrol/40 md:flex dark:bg-white/5"
		>
			{model?.chefSlug && <ModelSelectorLogo provider={model.chefSlug} />}
			<span className="truncate">{model?.name ?? modelId}</span>
			{showCost && (
				<span className="min-w-[7ch] flex-none border-l border-border pl-2 text-right tabular-nums text-subtle">
					{formatPillCost(cost.knownCost)}
				</span>
			)}
		</span>
	);
	return showCost ? (
		<HoverCard openDelay={150} closeDelay={100}>
			<HoverCardTrigger asChild>{pill}</HoverCardTrigger>
			<HoverCardContent align="end" className="w-80">
				<CostBreakdown cost={cost} />
			</HoverCardContent>
		</HoverCard>
	) : (
		pill
	);
}

function MobileSidebarTrigger() {
	return (
		<SidebarTrigger className="absolute left-3 top-1/2 z-10 size-9 -translate-y-1/2 cursor-pointer rounded-lg border border-sidebar-border bg-sidebar shadow-raised md:hidden" />
	);
}

export function ChatHeaderActions({ children }: { children: ReactNode }) {
	const element = useChatHeaderStore((state) => state.actionsEl);
	return element ? createPortal(children, element) : null;
}

function HeaderActionsSlot() {
	const setActionsEl = useChatHeaderStore((state) => state.setActionsEl);
	return <div ref={setActionsEl} className="flex min-w-0 items-center gap-2" />;
}

function HeaderBar({
	children,
	className,
}: {
	children?: ReactNode;
	className?: string;
}) {
	return (
		<div className="relative grid h-14 shrink-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center border-b border-border px-3 md:px-5">
			<MobileSidebarTrigger />
			<div />
			<div
				className={`flex min-w-0 items-center justify-center gap-2 ${className ?? ""}`}
			>
				{children}
			</div>
			<div className="flex min-w-0 items-center gap-2 justify-self-end">
				<ModelCostPill />
				<HeaderActionsSlot />
			</div>
		</div>
	);
}

/**
 * Petrol Mono chat header (design 8a): 56px, centered round avatar +
 * agent name, hairline bottom border like the other page top bars. The agent
 * name leads to the agent's page, gated on `editor` there (the gate opens a
 * "No access" dialog when the viewer is too weak).
 */
export function ChatHeader() {
	const router = useRouter();
	const {
		agentId,
		agentName,
		agentEmoji,
		agentColor,
		agentImageRevision,
		triggerId,
		triggerName,
		triggerRunAt,
	} = useChatHeaderStore();
	const { openAgentEditor, forbiddenOpen, setForbiddenOpen } =
		useOpenAgentEditor();

	if (triggerName) {
		return (
			<HeaderBar className="text-[14px]">
				<div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-petrol-tint dark:bg-white/10">
					<AlarmClock className="size-3.5 text-petrol dark:text-panel-terminal" />
				</div>
				{triggerId ? (
					<button
						type="button"
						onClick={() => {
							router.push(`/triggers/${triggerId}`);
						}}
						className="min-w-0 cursor-pointer truncate rounded-sm font-semibold leading-none text-foreground transition-colors hover:text-petrol focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-petrol/40 dark:hover:text-panel-terminal"
					>
						{triggerName}
					</button>
				) : (
					<span className="min-w-0 truncate font-semibold leading-none text-foreground">
						{triggerName}
					</span>
				)}
				{triggerRunAt && (
					<>
						<span className="text-ghost dark:text-panel-dim">/</span>
						<span className="flex-none whitespace-nowrap font-mono text-[12px] leading-none text-meta dark:text-panel-dim">
							{formatRunAt(
								triggerRunAt,
								Intl.DateTimeFormat().resolvedOptions().timeZone,
							)}
						</span>
					</>
				)}
			</HeaderBar>
		);
	}

	if (!agentName) {
		return <HeaderBar />;
	}

	return (
		<HeaderBar>
			<AgentAvatar
				agentId={agentId}
				name={agentName}
				imageRevision={agentImageRevision}
				color={agentColor}
				emoji={agentEmoji}
				size="xs"
			/>
			{agentId ? (
				<button
					type="button"
					onClick={() => {
						void openAgentEditor(agentId);
					}}
					className="min-w-0 cursor-pointer truncate rounded-sm text-[14px] font-semibold leading-none tracking-[-0.01em] text-foreground transition-colors hover:text-petrol focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-petrol/40 dark:hover:text-panel-terminal"
				>
					{agentName}
				</button>
			) : (
				<span className="min-w-0 truncate text-[14px] font-semibold leading-none tracking-[-0.01em] text-foreground">
					{agentName}
				</span>
			)}

			<ForbiddenErrorDialog
				open={forbiddenOpen}
				onOpenChange={setForbiddenOpen}
				title="No access"
				message={AGENT_EDITOR_FORBIDDEN_MESSAGE}
			/>
		</HeaderBar>
	);
}
