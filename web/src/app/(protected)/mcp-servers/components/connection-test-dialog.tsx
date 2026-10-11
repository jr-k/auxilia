"use client";

import { CircleAlert, CircleCheck } from "lucide-react";
import {
	Dialog,
	DialogButton,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { ConnectionTestStatus } from "../lib/use-connection-test";

export function ConnectionTestDialog({
	status,
	message,
	onClose,
}: {
	status: ConnectionTestStatus;
	message: string | null;
	onClose: () => void;
}) {
	const isOpen =
		message !== null && (status === "success" || status === "error");
	const isSuccess = status === "success";

	return (
		<Dialog
			open={isOpen}
			onOpenChange={(open) => {
				if (!open) onClose();
			}}
		>
			<DialogContent>
				<div
					className={`flex size-10 items-center justify-center rounded-[10px] ${
						isSuccess
							? "bg-success-bg text-success dark:bg-emerald-950 dark:text-emerald-300"
							: "bg-destructive/10 text-destructive"
					}`}
				>
					{isSuccess ? (
						<CircleCheck className="size-5" />
					) : (
						<CircleAlert className="size-5" />
					)}
				</div>
				<DialogHeader>
					<DialogTitle>
						{isSuccess ? "Connection successful" : "Connection test failed"}
					</DialogTitle>
					<DialogDescription>{message}</DialogDescription>
				</DialogHeader>
				<DialogFooter>
					<DialogButton onClick={onClose}>Close</DialogButton>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
