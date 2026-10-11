"use client";

import { RefreshCw, ShieldCheck } from "lucide-react";
import {
	Dialog,
	DialogButton,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";

interface OAuthConnectionFollowUpDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onVerify: () => void;
	isVerifying: boolean;
	message?: string | null;
}

export function OAuthConnectionFollowUpDialog({
	open,
	onOpenChange,
	onVerify,
	isVerifying,
	message,
}: OAuthConnectionFollowUpDialogProps) {
	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent>
				<div className="flex size-10 items-center justify-center rounded-[10px] bg-petrol/10 text-petrol dark:bg-petrol/20 dark:text-panel-terminal">
					<ShieldCheck className="size-5" />
				</div>
				<DialogHeader>
					<DialogTitle>Finished authorizing?</DialogTitle>
					<DialogDescription>
						Once you&apos;ve completed OAuth in the other window, refresh here
						to verify the connection and load the available tools.
					</DialogDescription>
				</DialogHeader>
				{message && (
					<p
						className="rounded-[8px] bg-hover px-3 py-2.5 text-[12px] leading-[1.5] text-subtle dark:bg-white/5 dark:text-panel-body"
						aria-live="polite"
					>
						{message}
					</p>
				)}
				<DialogFooter className="flex-col-reverse sm:flex-row">
					<DialogButton
						variant="outline"
						className="w-full sm:w-auto"
						onClick={() => {
							onOpenChange(false);
						}}
						disabled={isVerifying}
					>
						Not yet
					</DialogButton>
					<DialogButton
						className="w-full sm:w-auto"
						onClick={onVerify}
						disabled={isVerifying}
					>
						<RefreshCw
							className={`size-3.5 ${isVerifying ? "animate-spin" : ""}`}
						/>
						{isVerifying ? "Verifying…" : "Refresh to verify connection"}
					</DialogButton>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
