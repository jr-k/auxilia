"use client";

import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { humanizeToolName } from "@/components/ai-elements/chain-of-thought";
import { SandboxIcon } from "@/components/sandbox-icon";
import { Switch } from "@/components/ui/switch";
import { SANDBOX_PROVIDER_LABELS } from "@/lib/sandbox-providers";
import type { Sandbox } from "@/types/sandboxes";

// The filesystem tools deepagents gives a sandboxed agent. The sandbox
// itself is opened by the runtime before every run — there is no tool for it.
const SANDBOX_TOOLS = [
	{ name: "execute", description: "Run shell commands in the environment" },
	{ name: "ls", description: "List files in a directory with metadata (size, modified time)" },
	{ name: "read_file", description: "Read file contents with line numbers, supports offset/limit for large files" },
	{ name: "write_file", description: "Create new files" },
	{ name: "edit_file", description: "Perform exact string replacements in files (with global replace mode)" },
	{ name: "glob", description: "Find files matching patterns (e.g., **/*.py)" },
	{ name: "grep", description: "Search file contents with multiple output modes (files only, content with context, or counts)" },
];

interface AgentSandboxProps {
	sandbox: Sandbox;
	enabledByDefault: boolean;
	readOnly?: boolean;
	canToggleDefault?: boolean;
	mode?: "agent" | "trigger";
	onDefaultEnabledChange?: (enabled: boolean) => void;
	/** Draft update: detach this sandbox from the agent. */
	onRemove?: () => void;
}

export default function AgentSandbox({
	sandbox,
	enabledByDefault,
	readOnly,
	canToggleDefault,
	mode = "agent",
	onDefaultEnabledChange,
	onRemove,
}: AgentSandboxProps) {
	// Matches the MCP server cards: collapsed on page open.
	const [isExpanded, setIsExpanded] = useState(false);

	return (
		<div className="overflow-hidden rounded-[10px] border border-border bg-card">
			<button
				type="button"
				onClick={() => {
					setIsExpanded(!isExpanded);
				}}
				aria-label={isExpanded ? "Collapse" : "Expand"}
				aria-expanded={isExpanded}
				className="flex w-full cursor-pointer items-center gap-2.5 bg-card px-4 py-3 text-left"
			>
				<span className="flex size-[26px] shrink-0 items-center justify-center rounded-[6px] border border-border bg-card">
					<SandboxIcon
						sandboxId={sandbox.id}
						imageRevision={sandbox.imageRevision}
						provider={sandbox.provider}
						size={14}
					/>
				</span>
				<span className="truncate text-[13.5px] font-semibold text-foreground">
					{sandbox.name}
				</span>
				<span className="shrink-0 rounded-[4px] bg-hover px-2 py-0.5 text-[9.5px] font-semibold text-subtle dark:bg-white/10 dark:text-panel-dim">
					{SANDBOX_PROVIDER_LABELS[sandbox.provider]}
				</span>
				<ChevronRight
					aria-hidden="true"
					className={`ml-auto mr-1 size-4 text-meta transition-all dark:text-panel-dim ${
						isExpanded ? "rotate-90" : ""
					}`}
				/>
			</button>

			{isExpanded && (
				<div className="border-t border-hover dark:border-white/5">
					<div className="flex items-center gap-3 border-b border-hover bg-petrol-tint/55 px-4 py-3 dark:border-white/5 dark:bg-white/5">
						<div className="min-w-0 flex-1">
							<p className="text-[12.5px] font-semibold text-foreground">
								{mode === "trigger" ? "This trigger" : "New conversations"}
							</p>
							<p className="mt-0.5 text-[11.5px] text-muted-foreground">
								{mode === "trigger"
									? "Allow this sandbox during automated runs"
									: "Enable this sandbox by default"}
							</p>
						</div>
						<Switch
							checked={enabledByDefault}
							disabled={
								canToggleDefault === false ||
								(readOnly && !canToggleDefault)
							}
							onCheckedChange={(checked) => {
								onDefaultEnabledChange?.(checked);
							}}
							aria-label={
								mode === "trigger"
									? `Allow ${sandbox.name} for this trigger`
									: `Enable ${sandbox.name} by default in new conversations`
							}
						/>
					</div>
					<div className="max-h-80 overflow-y-auto [scrollbar-width:thin]">
						{SANDBOX_TOOLS.map((tool) => (
							<div
								key={tool.name}
								className="border-b border-hover px-4 py-2.5 last:border-b-0 dark:border-white/5"
							>
								<span className="block truncate text-[13.5px] font-semibold text-foreground">
									{humanizeToolName(tool.name)}
								</span>
								<span className="mt-px block text-xs text-muted-foreground">
									{tool.description}
								</span>
							</div>
						))}
					</div>
					{!readOnly && (
						<div className="flex justify-center border-t border-hover px-4 py-2 dark:border-white/5">
							<button
								className="cursor-pointer rounded-[7px] px-3 py-1.5 text-[12.5px] font-semibold text-[#B04A3A] transition-colors hover:bg-[#FBEFED] dark:hover:bg-[#B04A3A]/10"
								onClick={() => {
									onRemove?.();
								}}
							>
								Disable {sandbox.name}
							</button>
						</div>
					)}
				</div>
			)}
		</div>
	);
}
