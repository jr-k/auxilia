"use client";

import { Suspense, useState } from "react";
import { Loader2 } from "lucide-react";
import WorkspaceModels from "@/app/(protected)/settings/workspace-models";
import { AuthShell } from "@/components/auth/auth-shell";
import { SupervisionPageFrame } from "@/components/layout/supervision-page-frame";

export default function ModelOnboardingPage() {
	const [isContinuing, setIsContinuing] = useState(false);

	const continueToAgents = () => {
		if (isContinuing) return;
		setIsContinuing(true);
		window.location.assign("/agents");
	};

	return (
		<SupervisionPageFrame>
			<AuthShell
				wide
				title="Connect an LLM"
				description="Connect a provider with an API key or an Ollama endpoint, then choose which models your workspace can use. Keys are encrypted before they are stored."
				footer={
					<>
						You can add or replace keys later in{" "}
						<span className="font-semibold text-petrol">Settings → Models</span>
					</>
				}
			>
				<Suspense
					fallback={
						<div className="flex items-center justify-center gap-2 px-4 py-12 text-[14px] font-medium text-faint dark:text-muted-foreground">
							<Loader2 className="size-4 animate-spin" aria-hidden="true" />
							<span>Loading…</span>
						</div>
					}
				>
					<WorkspaceModels
						syncOnMount
						showSyncControl={false}
						onForbidden={continueToAgents}
					/>
				</Suspense>

				<button
					type="button"
					disabled={isContinuing}
					aria-busy={isContinuing}
					onClick={continueToAgents}
					className="mt-1.5 flex cursor-pointer items-center justify-center gap-2 rounded-md bg-ink p-3.5 text-center text-[15px] font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-default disabled:opacity-60"
				>
					{isContinuing && (
						<Loader2 className="size-4 animate-spin" aria-hidden="true" />
					)}
					{isContinuing ? "Opening agents…" : "Continue to agents →"}
				</button>
			</AuthShell>
		</SupervisionPageFrame>
	);
}
