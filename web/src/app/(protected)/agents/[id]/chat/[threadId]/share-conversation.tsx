"use client";

import { Check, Copy, Globe2, Share2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ChatHeaderActions } from "@/components/layout/chat-header";
import ConfirmDialog from "@/components/ui/confirm-dialog";
import {
	Dialog,
	DialogButton,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { getApiErrorMessage } from "@/lib/api/errors";
import {
	createConversationShare,
	deleteConversationShare,
	getConversationShare,
	type ConversationShare,
} from "@/lib/api/resources/threads";

function publicUrl(share: ConversationShare): string {
	return `${window.location.origin}/share/${share.id}#token=${encodeURIComponent(share.token)}`;
}

export function ShareConversation({
	threadId,
	disabled,
}: {
	threadId: string;
	disabled: boolean;
}) {
	const [open, setOpen] = useState(false);
	const [share, setShare] = useState<ConversationShare | null | undefined>();
	const [busy, setBusy] = useState(false);
	const [copied, setCopied] = useState(false);
	const [confirmRevoke, setConfirmRevoke] = useState(false);

	useEffect(() => {
		setShare(undefined);
		setCopied(false);
	}, [threadId]);

	useEffect(() => {
		if (!open || share !== undefined) return;
		let active = true;
		void getConversationShare(threadId).then(
			(value) => {
				if (active) setShare(value);
			},
			(error: unknown) => {
				if (active) {
					setShare(null);
					toast.error(
						getApiErrorMessage(error, "Could not load sharing status"),
					);
				}
			},
		);
		return () => {
			active = false;
		};
	}, [open, share, threadId]);

	const publish = async () => {
		setBusy(true);
		try {
			const value = await createConversationShare(threadId);
			setShare(value);
			toast.success("Conversation published");
		} catch (error) {
			toast.error(getApiErrorMessage(error, "Could not publish conversation"));
		} finally {
			setBusy(false);
		}
	};

	const copy = async () => {
		if (!share) return;
		try {
			await navigator.clipboard.writeText(publicUrl(share));
			setCopied(true);
			toast.success("Public link copied");
		} catch {
			toast.error("Could not copy the public link");
		}
	};

	const revoke = async () => {
		await deleteConversationShare(threadId);
		setShare(null);
		setConfirmRevoke(false);
		toast.success("Publication removed");
	};

	return (
		<>
			<ChatHeaderActions>
				<button
					type="button"
					disabled={disabled}
					onClick={() => {
						setOpen(true);
					}}
					className="flex h-[30px] cursor-pointer items-center gap-1.5 rounded-full bg-petrol-chip px-3 text-[12.5px] font-semibold text-petrol transition-colors hover:bg-petrol-tint disabled:cursor-not-allowed disabled:opacity-50 dark:bg-white/10 dark:text-panel-terminal dark:hover:bg-white/15"
				>
					<Share2 className="size-3.5" />
					Share
				</button>
			</ChatHeaderActions>

			<Dialog open={open} onOpenChange={setOpen}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Share conversation</DialogTitle>
						<DialogDescription>
							Publish a read-only snapshot. New messages added later will not
							appear in the shared version.
						</DialogDescription>
					</DialogHeader>

					{share === undefined ? (
						<div className="h-20 animate-pulse rounded-[10px] bg-hover" />
					) : share === null ? (
						<div className="rounded-[10px] border border-input p-4">
							<div className="flex items-start gap-3">
								<span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-petrol-tint text-petrol">
									<Globe2 className="size-4" />
								</span>
								<div>
									<p className="text-[13px] font-semibold text-foreground">
										Anyone with the link can view this snapshot
									</p>
									<p className="mt-1 text-[12px] leading-5 text-subtle">
										They cannot send messages, approve tools, or interact with
										the agent.
									</p>
								</div>
							</div>
						</div>
					) : (
						<div className="space-y-3">
							<div className="flex items-center gap-2 rounded-[9px] border border-input bg-hover/40 p-2">
								<input
									readOnly
									value={publicUrl(share)}
									aria-label="Public conversation link"
									className="min-w-0 flex-1 bg-transparent px-1 font-mono text-[11.5px] text-foreground outline-none"
								/>
								<button
									type="button"
									onClick={() => {
										void copy();
									}}
									className="flex h-8 shrink-0 cursor-pointer items-center gap-1.5 rounded-[7px] bg-petrol px-3 text-[12px] font-semibold text-white"
								>
									{copied ? (
										<Check className="size-3.5" />
									) : (
										<Copy className="size-3.5" />
									)}
									{copied ? "Copied" : "Copy"}
								</button>
							</div>
							<p className="text-[12px] leading-5 text-subtle">
								The link stays active until you stop sharing it.
							</p>
						</div>
					)}

					<DialogFooter>
						{share ? (
							<>
								<DialogButton
									variant="outline"
									onClick={() => {
										setConfirmRevoke(true);
									}}
								>
									Stop sharing
								</DialogButton>
								<DialogButton
									variant="primary"
									onClick={() => {
										void copy();
									}}
								>
									Copy link
								</DialogButton>
							</>
						) : (
							<DialogButton
								variant="primary"
								disabled={busy || share === undefined}
								onClick={() => {
									void publish();
								}}
							>
								{busy ? "Publishing…" : "Publish snapshot"}
							</DialogButton>
						)}
					</DialogFooter>
				</DialogContent>
			</Dialog>

			<ConfirmDialog
				open={confirmRevoke}
				onOpenChange={setConfirmRevoke}
				title="Stop sharing this conversation?"
				description="The public link will stop working immediately."
				confirmLabel="Stop sharing"
				destructive
				onConfirm={revoke}
			/>
		</>
	);
}
