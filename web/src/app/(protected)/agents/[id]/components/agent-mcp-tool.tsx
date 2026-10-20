"use client";

import { ToolStatus } from "@/types/agents";
import { ThreeStateToggle } from "@/components/ui/three-state-toggle";
import { Switch } from "@/components/ui/switch";
import { humanizeToolName } from "@/components/ai-elements/chain-of-thought";
import { cn } from "@/lib/utils";

interface AgentMCPToolProps {
	toolName: string;
	toolDescription?: string;
	status: ToolStatus;
	readOnly?: boolean;
	mode?: "agent" | "trigger";
	triggerEnabled?: boolean;
	triggerReadOnly?: boolean;
	onStatusChange?: (status: ToolStatus) => void;
	onTriggerEnabledChange?: (enabled: boolean) => void;
}

export default function AgentMCPTool({
	toolName,
	toolDescription,
	status,
	readOnly,
	mode = "agent",
	triggerEnabled = true,
	triggerReadOnly = false,
	onStatusChange,
	onTriggerEnabledChange,
}: AgentMCPToolProps) {
	const isDisabled =
		status === "disabled" || (mode === "trigger" && !triggerEnabled);
	const interactionDisabled = Boolean(
		mode === "trigger" ? triggerReadOnly : readOnly,
	);

	return (
		<div className="flex items-center gap-2.5 border-b border-hover px-4 py-2.5 last:border-b-0 dark:border-white/5">
			<span className="min-w-0 flex-1">
				<span
					className={cn(
						"block truncate text-[13.5px] font-semibold",
						isDisabled ? "text-meta dark:text-panel-dim" : "text-foreground",
					)}
				>
					{humanizeToolName(toolName)}
				</span>
				{toolDescription && (
					<span
						className={cn(
							"mt-px line-clamp-2 text-xs",
							isDisabled
								? "text-faint dark:text-panel-dim"
								: "text-muted-foreground",
						)}
					>
						{toolDescription}
					</span>
				)}
			</span>

			<div
				className={`flex shrink-0 items-center ${
					interactionDisabled ? "pointer-events-none opacity-60" : ""
				}`}
			>
				{mode === "trigger" ? (
					<div className="flex items-center gap-2">
						<span className="w-12 text-right text-[11px] font-medium text-muted-foreground">
							{triggerEnabled ? "Accept" : "Reject"}
						</span>
						<Switch
							checked={triggerEnabled}
							disabled={triggerReadOnly}
							onCheckedChange={(enabled) => {
								onTriggerEnabledChange?.(enabled);
							}}
							aria-label={`${triggerEnabled ? "Reject" : "Accept"} ${humanizeToolName(toolName)} for this trigger`}
						/>
					</div>
				) : (
					<ThreeStateToggle
						value={status}
						onChange={(value) => {
							if (!interactionDisabled) onStatusChange?.(value);
						}}
					/>
				)}
			</div>
		</div>
	);
}
