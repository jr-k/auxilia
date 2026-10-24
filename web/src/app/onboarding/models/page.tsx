"use client";

import { Suspense } from "react";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import WorkspaceModels from "@/app/(protected)/settings/workspace-models";
import { AuthShell } from "@/components/auth/auth-shell";

export default function ModelOnboardingPage() {
	const continueToAgents = () => {
		window.location.assign("/agents");
	};

	return (
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

			<Link
				href="/agents"
				className="mt-1.5 cursor-pointer rounded-md bg-ink p-3.5 text-center text-[15px] font-semibold text-white transition-opacity hover:opacity-90"
			>
				Continue to agents →
			</Link>
		</AuthShell>
	);
}
