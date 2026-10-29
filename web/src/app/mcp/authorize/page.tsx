"use client";

import { Suspense, useEffect, useState } from "react";
import { ArrowRight, Check, Loader2, ShieldCheck, X } from "lucide-react";
import { useSearchParams } from "next/navigation";

import { AuthShell } from "@/components/auth/auth-shell";
import { SupervisionPageFrame } from "@/components/layout/supervision-page-frame";
import { WorkspaceAvatar } from "@/components/ui/workspace-avatar";
import { getApiErrorMessage } from "@/lib/api/errors";
import * as mcpOAuthApi from "@/lib/api/resources/mcp-oauth";
import { cn } from "@/lib/utils";
import type { MCPOAuthAuthorization } from "@/types/mcp-oauth";

function clientHostname(uri: string | null | undefined): string | null {
	if (!uri) return null;
	try {
		return new URL(uri).host;
	} catch {
		return uri;
	}
}

function AuthorizationContent() {
	const searchParams = useSearchParams();
	const request = searchParams.get("request");
	const [authorization, setAuthorization] =
		useState<MCPOAuthAuthorization | null>(null);
	const [workspaceId, setWorkspaceId] = useState("");
	const [error, setError] = useState<string | null>(null);
	const [action, setAction] = useState<"approve" | "deny" | null>(null);

	useEffect(() => {
		if (!request) return;
		let active = true;
		void mcpOAuthApi
			.getAuthorization(request)
			.then((data) => {
				if (!active) return;
				setAuthorization(data);
				const preferred = data.workspaces.some(
					(workspace) => workspace.id === data.activeWorkspaceId,
				)
					? data.activeWorkspaceId
					: data.workspaces[0]?.id;
				setWorkspaceId(preferred ?? "");
			})
			.catch((cause: unknown) => {
				if (active) {
					setError(
						getApiErrorMessage(
							cause,
							"This authorization request is invalid or has expired.",
						),
					);
				}
			});
		return () => {
			active = false;
		};
	}, [request]);

	const displayError = request
		? error
		: "This authorization link is incomplete.";
	const clientHost = clientHostname(authorization?.client.uri);

	const finish = async (decision: "approve" | "deny") => {
		if (!request || (decision === "approve" && !workspaceId)) return;
		setAction(decision);
		setError(null);
		try {
			const result =
				decision === "approve"
					? await mcpOAuthApi.approveAuthorization(request, workspaceId)
					: await mcpOAuthApi.denyAuthorization(request);
			window.location.replace(result.redirectUrl);
		} catch (cause: unknown) {
			setError(
				getApiErrorMessage(cause, "Could not complete this authorization."),
			);
			setAction(null);
		}
	};

	const clientName = authorization?.client.name ?? "MCP client";

	return (
		<SupervisionPageFrame>
			<AuthShell
				title="Connect to Auxilia"
				description={
					authorization
						? `${clientName} is requesting access to one of your workspaces.`
						: "Review and approve this MCP connection."
				}
				footer="You can revoke this connection at any time from the MCP client."
			>
			{displayError ? (
				<div
					role="alert"
					className="rounded-[10px] border border-destructive/20 bg-destructive/5 px-4 py-3 text-[13px] leading-5 text-destructive"
				>
					{displayError}
				</div>
			) : !authorization ? (
				<div className="flex items-center gap-3 rounded-[10px] border border-border bg-card px-4 py-5 text-[13px] text-body">
					<Loader2 className="size-4 animate-spin text-petrol" />
					Loading authorization request…
				</div>
			) : (
				<>
					<div className="rounded-[12px] border border-border bg-card p-4 shadow-sm">
						<div className="flex items-start gap-3">
							<div className="flex size-10 shrink-0 items-center justify-center rounded-[10px] bg-petrol/10 text-petrol">
								<ShieldCheck className="size-5" />
							</div>
							<div className="min-w-0">
								<p className="font-display text-[16px] font-bold text-foreground">
									{clientName}
								</p>
								{clientHost && (
									<p className="mt-0.5 truncate text-[12px] text-meta">
										{clientHost}
									</p>
								)}
								<p className="mt-2 text-[13px] leading-5 text-body">
									This connection can manage agents and skills, configure MCP
									servers, and search conversations as you.
								</p>
							</div>
						</div>
					</div>

					<fieldset className="space-y-2">
						<legend className="mb-2 text-[12px] font-semibold text-label">
							Choose a workspace
						</legend>
						{authorization.workspaces.length === 0 ? (
							<p className="rounded-[10px] border border-border bg-card px-4 py-3 text-[13px] text-body">
								Your account does not belong to a workspace.
							</p>
						) : (
							authorization.workspaces.map((workspace) => {
								const selected = workspace.id === workspaceId;
								return (
									<label
										key={workspace.id}
										className={cn(
											"flex cursor-pointer items-center gap-3 rounded-[10px] border px-3.5 py-3 transition-colors",
											selected
												? "border-petrol bg-petrol/5"
												: "border-border bg-card hover:border-border-hover",
										)}
									>
										<input
											type="radio"
											name="workspace"
											value={workspace.id}
											checked={selected}
											onChange={() => {
												setWorkspaceId(workspace.id);
											}}
											className="sr-only"
										/>
										<WorkspaceAvatar
											workspaceId={workspace.id}
											name={workspace.name}
											emoji={workspace.emoji}
											color={workspace.color}
											imageRevision={workspace.imageRevision}
											size="sm"
										/>
										<span className="min-w-0 flex-1">
											<span className="block truncate text-[13.5px] font-semibold text-foreground">
												{workspace.name}
											</span>
											<span className="block text-[11.5px] capitalize text-meta">
												{workspace.role}
											</span>
										</span>
										<span
											className={cn(
												"flex size-5 items-center justify-center rounded-full border",
												selected
													? "border-petrol bg-petrol text-white"
													: "border-input",
											)}
										>
											{selected && <Check className="size-3" />}
										</span>
									</label>
								);
							})
						)}
					</fieldset>

					<div className="flex gap-2.5 pt-1">
						<button
							type="button"
							disabled={action !== null}
							onClick={() => {
								void finish("deny");
							}}
							className="flex h-10 flex-1 cursor-pointer items-center justify-center gap-2 rounded-md border border-input bg-canvas px-4 text-[13.5px] font-semibold text-foreground transition-colors hover:border-border-hover disabled:cursor-not-allowed disabled:opacity-50"
						>
							{action === "deny" ? (
								<Loader2 className="size-4 animate-spin" />
							) : (
								<X className="size-4" />
							)}
							Deny
						</button>
						<button
							type="button"
							disabled={action !== null || !workspaceId}
							onClick={() => {
								void finish("approve");
							}}
							className="flex h-10 flex-[1.6] cursor-pointer items-center justify-center gap-2 rounded-md bg-petrol px-4 text-[13.5px] font-semibold text-white transition-colors hover:bg-petrol/90 disabled:cursor-not-allowed disabled:opacity-50"
						>
							{action === "approve" ? (
								<Loader2 className="size-4 animate-spin" />
							) : (
								<ArrowRight className="size-4" />
							)}
							Allow access
						</button>
					</div>
				</>
			)}
			</AuthShell>
		</SupervisionPageFrame>
	);
}

export default function MCPAuthorizePage() {
	return (
		<Suspense>
			<AuthorizationContent />
		</Suspense>
	);
}
