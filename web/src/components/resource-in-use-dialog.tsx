"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { AgentAvatar } from "@/components/ui/agent-avatar";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Dialog,
	DialogButton,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import type { BoundAgent } from "@/types/agents";

interface ResourceInUseDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	/** e.g. "Sandbox" / "MCP server" — used in the title and body copy. */
	resourceLabel: string;
	resourceName: string | null;
	/** Agents still bound to the resource — the reason plain delete is refused. */
	agents: BoundAgent[];
	/** What the listed agents lose, e.g. "they lose code execution". */
	consequence: string;
	/** Detach the resource from all listed agents, then delete it. */
	onConfirm: () => Promise<void>;
}

export default function ResourceInUseDialog({
	open,
	onOpenChange,
	resourceLabel,
	resourceName,
	agents,
	consequence,
	onConfirm,
}: ResourceInUseDialogProps) {
	const [isDeleting, setIsDeleting] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [acknowledged, setAcknowledged] = useState(false);

	const handleOpenChange = (nextOpen: boolean) => {
		if (!nextOpen) {
			setError(null);
			setIsDeleting(false);
			setAcknowledged(false);
		}
		onOpenChange(nextOpen);
	};

	const handleConfirm = async () => {
		if (!acknowledged) return;
		setIsDeleting(true);
		setError(null);
		try {
			await onConfirm();
			handleOpenChange(false);
		} catch {
			setError(`Could not delete the ${resourceLabel.toLowerCase()}. Please try again.`);
		} finally {
			setIsDeleting(false);
		}
	};

	if (!resourceName) return null;

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent className="sm:max-w-[480px]">
				<DialogHeader>
					<DialogTitle>{resourceLabel} assigned to agents</DialogTitle>
					<DialogDescription>
						&ldquo;{resourceName}&rdquo; is still enabled on{" "}
						{agents.length === 1 ? "this agent" : `these ${agents.length} agents`}.
					</DialogDescription>
				</DialogHeader>

				{error && (
					<div className="rounded-[10px] bg-[#FBEFED] px-3.5 py-2.5 text-[13px] font-medium text-[#B04A3A] dark:bg-[#B04A3A]/10">
						{error}
					</div>
				)}

				<div className="max-h-[240px] overflow-y-auto rounded-[10px] border border-hairline dark:border-white/10 [scrollbar-width:thin]">
					{agents.map((agent) => (
						<Link
							key={agent.id}
							href={`/agents/${agent.id}`}
							className="flex items-center gap-2.5 border-b border-hairline px-3.5 py-2.5 transition-colors last:border-b-0 hover:bg-sidebar dark:border-white/5 dark:hover:bg-white/5"
						>
							<AgentAvatar
								agentId={agent.id}
								name={agent.name}
								imageRevision={agent.imageRevision}
								color={agent.color}
								emoji={agent.emoji}
								size="xs"
							/>
							<span className="min-w-0 flex-1 truncate text-[13px] font-semibold text-petrol">
								{agent.name}
							</span>
							<ChevronRight className="size-3.5 shrink-0 text-faint dark:text-panel-dim" />
						</Link>
					))}
				</div>

				<p className="text-[13px] leading-[1.55] text-subtle dark:text-panel-body">
					The {resourceLabel.toLowerCase()} will be detached automatically. The affected{" "}
					{agents.length === 1 ? "agent" : "agents"} will lose {consequence}. Threads are unaffected.
				</p>

				<div className="flex items-start gap-3 rounded-[10px] border border-[#B04A3A]/20 bg-[#FBEFED]/70 px-3.5 py-3 dark:border-[#B04A3A]/25 dark:bg-[#B04A3A]/10">
					<Checkbox
						checked={acknowledged}
						aria-label="Confirm detach and delete"
						onCheckedChange={setAcknowledged}
						className="mt-0.5 border-[#B04A3A]/45"
					/>
					<button
						type="button"
						onClick={() => {
							setAcknowledged((current) => !current);
						}}
						className="cursor-pointer text-left text-[12.5px] leading-[1.5] text-[#86392F] dark:text-[#E7A69D]"
					>
						I understand that <span className="font-semibold">{resourceName}</span> will be
						removed from {agents.length === 1 ? "1 agent" : `${agents.length} agents`} and
						deleted permanently.
					</button>
				</div>

				<DialogFooter>
					<DialogButton
						variant="outline"
						onClick={() => {
							handleOpenChange(false);
						}}
					>
						Cancel
					</DialogButton>
					<button
						type="button"
						disabled={isDeleting || !acknowledged}
						onClick={() => {
							void handleConfirm();
						}}
						className="inline-flex cursor-pointer items-center justify-center rounded-[7px] bg-[#B04A3A] px-4 py-2 text-[12.5px] font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-default disabled:opacity-50"
					>
						{isDeleting
							? "Removing…"
							: `Detach from ${agents.length === 1 ? "1 agent" : `${agents.length} agents`} & delete`}
					</button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
