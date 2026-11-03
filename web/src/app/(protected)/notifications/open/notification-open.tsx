"use client";

import { AlertCircle, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useWorkspacesStore } from "@/stores/workspaces-store";

export default function NotificationOpen({
	workspaceId,
	agentId,
	threadId,
}: {
	workspaceId: string | null;
	agentId: string | null;
	threadId: string | null;
}) {
	const router = useRouter();
	const activeWorkspaceId = useWorkspacesStore(
		(state) => state.activeWorkspaceId,
	);
	const workspaces = useWorkspacesStore((state) => state.workspaces);
	const selectWorkspace = useWorkspacesStore(
		(state) => state.selectWorkspace,
	);
	const [navigationError, setNavigationError] = useState<string | null>(null);
	const validationError =
		!workspaceId || !agentId || !threadId
			? "This notification link is incomplete."
			: !workspaces.some((workspace) => workspace.id === workspaceId)
				? "You no longer have access to this workspace."
				: null;
	const error = validationError ?? navigationError;

	useEffect(() => {
		if (validationError || !workspaceId || !agentId || !threadId) return;
		const destination = `/agents/${encodeURIComponent(agentId)}/chat/${encodeURIComponent(threadId)}`;
		if (workspaceId === activeWorkspaceId) {
			router.replace(destination);
			return;
		}
		void selectWorkspace(workspaceId)
			.then(() => {
				window.location.replace(destination);
			})
			.catch(() => {
				setNavigationError("Could not switch to the notification workspace.");
			});
	}, [
		activeWorkspaceId,
		agentId,
		router,
		selectWorkspace,
		threadId,
		validationError,
		workspaceId,
	]);

	return (
		<div className="flex min-h-[60vh] items-center justify-center px-6">
			<div className="flex max-w-sm flex-col items-center text-center">
				{error ? (
					<>
						<span className="flex size-11 items-center justify-center rounded-full bg-destructive/10 text-destructive">
							<AlertCircle className="size-5" aria-hidden="true" />
						</span>
						<p className="mt-4 text-[14px] font-semibold text-foreground">
							Could not open the conversation
						</p>
						<p className="mt-1.5 text-[12.5px] leading-5 text-subtle">
							{error}
						</p>
					</>
				) : (
					<>
						<Loader2
							className="size-6 animate-spin text-petrol"
							aria-hidden="true"
						/>
						<p className="mt-3 text-[12.5px] font-medium text-subtle">
							Opening the conversation…
						</p>
					</>
				)}
			</div>
		</div>
	);
}
