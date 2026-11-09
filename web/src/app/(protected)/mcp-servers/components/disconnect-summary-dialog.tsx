"use client";

import Link from "next/link";
import { AlertTriangle, CheckCircle2, MinusCircle } from "lucide-react";
import {
	Dialog,
	DialogButton,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import type { MCPConnectionDisconnectSummary } from "@/types/mcp-servers";

interface DisconnectSummaryDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	summary: MCPConnectionDisconnectSummary | null;
	title?: string;
}

export function DisconnectSummaryDialog({
	open,
	onOpenChange,
	summary,
	title = "MCP account disconnect report",
}: DisconnectSummaryDialogProps) {
	if (!summary) return null;

	const providerWarnings = summary.disconnected.filter(
		(item) => item.providerRevocation === "failed",
	);

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="overflow-hidden p-0 sm:max-w-[560px]">
				<div className="border-b border-border px-6 pb-5 pt-6 dark:border-white/10">
					<DialogHeader>
						<DialogTitle>{title}</DialogTitle>
						<DialogDescription>
							Other users and shared workspace credentials were left unchanged.
						</DialogDescription>
					</DialogHeader>
				</div>

				<div className="max-h-[55vh] space-y-3 overflow-y-auto px-6 py-4">
					{summary.disconnected.map((item) => (
						<div
							key={`disconnected-${item.serverId}`}
							className="flex items-start gap-3 rounded-[9px] border border-border px-3.5 py-3 dark:border-white/10"
						>
							<CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" />
							<div className="min-w-0 flex-1">
								<p className="truncate text-[13px] font-semibold text-foreground">
									{item.serverName}
								</p>
								<p className="mt-0.5 text-[11.5px] leading-[1.45] text-meta dark:text-panel-dim">
									Personal account disconnected.
									{item.providerRevocation === "unsupported"
										? " The provider does not advertise remote revocation."
										: null}
								</p>
								{item.warning && (
									<p className="mt-1 text-[11.5px] leading-[1.45] text-warning">
										{item.warning}
									</p>
								)}
							</div>
							<Link
								href={`/mcp-servers/${item.serverId}`}
								className="shrink-0 text-[12px] font-semibold text-petrol hover:underline"
							>
								Reconnect
							</Link>
						</div>
					))}

					{summary.failed.map((item) => (
						<div
							key={`failed-${item.serverId}`}
							className="flex items-start gap-3 rounded-[9px] bg-destructive/10 px-3.5 py-3 text-destructive"
						>
							<AlertTriangle className="mt-0.5 size-4 shrink-0" />
							<div className="min-w-0">
								<p className="truncate text-[13px] font-semibold">
									{item.serverName}
								</p>
								<p className="mt-0.5 text-[11.5px] leading-[1.45]">
									{item.detail}
								</p>
							</div>
						</div>
					))}

					{summary.alreadyAbsent.length > 0 && (
						<div className="flex items-start gap-3 rounded-[9px] bg-hover px-3.5 py-3 dark:bg-white/5">
							<MinusCircle className="mt-0.5 size-4 shrink-0 text-meta" />
							<p className="text-[12px] leading-[1.5] text-body dark:text-panel-body">
								{summary.alreadyAbsent.length} personal connection
								{summary.alreadyAbsent.length === 1 ? " was" : "s were"} already
								absent.
							</p>
						</div>
					)}

					{summary.unaffectedShared.length > 0 && (
						<div className="rounded-[9px] bg-petrol-tint px-3.5 py-3 text-[12px] leading-[1.5] text-petrol dark:bg-petrol/15 dark:text-panel-terminal">
							{summary.unaffectedShared.length} shared integration
							{summary.unaffectedShared.length === 1 ? " was" : "s were"} preserved.
						</div>
					)}

					{providerWarnings.length > 0 && (
						<p className="text-[11.5px] leading-[1.5] text-meta dark:text-panel-dim">
							Local access is removed for every disconnected account. Provider
							warnings only mean remote revocation could not be confirmed.
						</p>
					)}
				</div>

				<DialogFooter className="border-t border-border px-6 py-4 dark:border-white/10">
					<DialogButton
						onClick={() => {
							onOpenChange(false);
						}}
					>
						Close
					</DialogButton>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
