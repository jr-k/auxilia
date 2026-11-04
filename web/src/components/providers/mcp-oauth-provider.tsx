"use client";

import {
	createContext,
	useCallback,
	useContext,
	useMemo,
	useRef,
	useState,
} from "react";
import {
	ClipboardPaste,
	ExternalLink,
	Loader2,
	LockKeyhole,
} from "lucide-react";
import { toast } from "sonner";
import {
	Dialog,
	DialogButton,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { getApiErrorMessage } from "@/lib/api/errors";
import * as mcpServersApi from "@/lib/api/resources/mcp-servers";
import type {
	OAuthManualCallbackResponse,
	OAuthRedirectMode,
} from "@/types/mcp-servers";

interface OAuthAuthorizationRequest {
	authUrl: string;
	redirectMode?: OAuthRedirectMode;
	serverId?: string;
	serverName?: string;
	popup?: Window | null;
	onSuccess?: (result: OAuthManualCallbackResponse) => void | Promise<void>;
}

interface ManualAttempt extends OAuthAuthorizationRequest {
	popup: Window | null;
}

interface McpOAuthContextValue {
	startAuthorization: (request: OAuthAuthorizationRequest) => boolean;
}

const McpOAuthContext = createContext<McpOAuthContextValue | null>(null);

function safeAuthorizationUrl(value: string): string | null {
	try {
		const url = new URL(value);
		return url.protocol === "https:" || url.protocol === "http:"
			? url.href
			: null;
	} catch {
		return null;
	}
}

export function McpOAuthProvider({ children }: { children: React.ReactNode }) {
	const [manualAttempt, setManualAttempt] = useState<ManualAttempt | null>(null);
	const [callbackUrl, setCallbackUrl] = useState("");
	const [error, setError] = useState<string | null>(null);
	const [submitting, setSubmitting] = useState(false);
	const manualPopupRef = useRef<Window | null>(null);

	const closeManualAttempt = useCallback(() => {
		if (manualPopupRef.current && !manualPopupRef.current.closed) {
			manualPopupRef.current.close();
		}
		manualPopupRef.current = null;
		setManualAttempt(null);
		setCallbackUrl("");
		setError(null);
		setSubmitting(false);
	}, []);

	const startAuthorization = useCallback(
		(request: OAuthAuthorizationRequest): boolean => {
			const authUrl = safeAuthorizationUrl(request.authUrl);
			if (!authUrl) {
				request.popup?.close();
				toast.error("The authorization URL is invalid.");
				return false;
			}

			if (request.redirectMode === "loopback_manual") {
				request.popup?.close();
				if (manualPopupRef.current && !manualPopupRef.current.closed) {
					manualPopupRef.current.close();
				}
				manualPopupRef.current = null;
				setCallbackUrl("");
				setError(null);
				setSubmitting(false);
				setManualAttempt({ ...request, authUrl, popup: null });
				return true;
			}

			const popup =
				request.popup ??
				window.open("", "_blank", "width=600,height=700");
			if (!popup) {
				toast.error("Allow pop-ups for this site, then try again.");
				return false;
			}
			popup.location.href = authUrl;
			return true;
		},
		[],
	);

	const openManualAuthorization = useCallback(() => {
		if (!manualAttempt) return;
		const popup = window.open(manualAttempt.authUrl, "_blank");
		if (!popup) {
			setError("Allow pop-ups for this site, then try again.");
			return;
		}
		if (manualPopupRef.current && !manualPopupRef.current.closed) {
			manualPopupRef.current.close();
		}
		manualPopupRef.current = popup;
		setManualAttempt((current) => (current ? { ...current, popup } : null));
		setError(null);
	}, [manualAttempt]);

	const pasteManualCallback = useCallback(async () => {
		try {
			const value = (await navigator.clipboard.readText()).trim();
			if (!value) {
				setError("The clipboard is empty.");
				return;
			}
			setCallbackUrl(value);
			setError(null);
		} catch {
			setError(
				"Could not read the clipboard. Paste the complete address into the field instead.",
			);
		}
	}, []);

	const finishManualConnection = useCallback(async () => {
		if (!manualAttempt || submitting) return;
		const value = callbackUrl.trim();
		if (!value) {
			setError("Paste the complete address from your browser.");
			return;
		}
		setSubmitting(true);
		setError(null);
		let result: OAuthManualCallbackResponse;
		try {
			result = await mcpServersApi.completeManualOAuth(value);
		} catch (caught: unknown) {
			setError(
				getApiErrorMessage(
					caught,
					"Could not finish the connection. Restart authorization and try again.",
				),
			);
			setSubmitting(false);
			return;
		}
		const onSuccess = manualAttempt.onSuccess;
		if (manualAttempt.popup && !manualAttempt.popup.closed) {
			manualAttempt.popup.close();
		}
		manualPopupRef.current = null;
		setManualAttempt(null);
		setCallbackUrl("");
		setSubmitting(false);
		toast.success(`${result.serverName} is connected.`);
		try {
			await onSuccess?.(result);
		} catch {
			toast.error("Connected, but this page could not refresh automatically.");
		}
	}, [callbackUrl, manualAttempt, submitting]);

	const value = useMemo(
		() => ({ startAuthorization }),
		[startAuthorization],
	);

	return (
		<McpOAuthContext.Provider value={value}>
			{children}
			<Dialog
				open={manualAttempt !== null}
				onOpenChange={(open) => {
					if (!open && !submitting) closeManualAttempt();
				}}
			>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>
							Connect {manualAttempt?.serverName ?? "the MCP server"}
						</DialogTitle>
						<DialogDescription>
							Complete these two steps to finish the secure connection.
						</DialogDescription>
					</DialogHeader>

					<div className="space-y-4">
						<div className="rounded-[10px] border border-border bg-hover/60 p-4 dark:bg-white/5">
							<div className="flex gap-3.5">
								<div className="flex size-6 shrink-0 items-center justify-center rounded-full bg-petrol text-[12px] font-semibold text-white">
									1
								</div>
								<div className="min-w-0 flex-1 space-y-2.5">
									<div>
										<p className="text-[13px] font-semibold text-foreground">
											Sign in with Adobe
										</p>
										<p className="mt-1 text-[12px] leading-[1.5] text-meta dark:text-panel-dim">
											Open the authorization page and sign in with the Adobe
											account connected to Frame.io.
										</p>
									</div>
									<DialogButton
										variant="outline"
										className="w-full sm:w-auto"
										onClick={openManualAuthorization}
									>
										<ExternalLink className="size-3.5" />
										Open {manualAttempt?.serverName ?? "service"} sign-in
									</DialogButton>
								</div>
							</div>
						</div>

						<div className="rounded-[10px] border border-border p-4">
							<div className="flex gap-3.5">
								<div className="flex size-6 shrink-0 items-center justify-center rounded-full border border-petrol/30 bg-petrol/8 text-[12px] font-semibold text-petrol dark:text-panel-terminal">
									2
								</div>
								<div className="min-w-0 flex-1 space-y-3">
									<div>
										<p className="text-[13px] font-semibold text-foreground">
											Retrieve the callback address
										</p>
										<p className="mt-1 text-[12px] leading-[1.5] text-meta dark:text-panel-dim">
											After authorization, Adobe redirects to 127.0.0.1. The
											browser may report that it cannot connect. Copy the
											complete address from its address bar.
										</p>
									</div>
									<DialogButton
										variant="outline"
										className="w-full sm:w-auto"
										onClick={() => {
											void pasteManualCallback();
										}}
										disabled={submitting}
									>
										<ClipboardPaste className="size-3.5" />
										Paste address from clipboard
									</DialogButton>
									<div>
										<label
											htmlFor="manual-oauth-callback-url"
											className="text-[12px] font-semibold text-foreground"
										>
											Callback address
										</label>
										<Textarea
											id="manual-oauth-callback-url"
											value={callbackUrl}
											onChange={(event) => {
												setCallbackUrl(event.target.value);
												if (error) setError(null);
											}}
											placeholder="http://127.0.0.1:4789/oauth/callback?code=…&state=…"
											autoComplete="off"
											autoCapitalize="none"
											spellCheck={false}
											disabled={submitting}
											aria-invalid={Boolean(error)}
											className="mt-1.5 min-h-24 resize-y font-mono text-[12px] leading-[1.5]"
										/>
									</div>
								</div>
							</div>
						</div>

						<div className="flex gap-2.5 text-[11.5px] leading-[1.5] text-meta dark:text-panel-dim">
							<LockKeyhole className="mt-0.5 size-3.5 shrink-0" />
							<p>
								Nothing needs to be installed or run. The callback address is
								sensitive and temporary, so do not share it.
							</p>
						</div>

						{error && (
							<p
								className="rounded-[8px] bg-destructive/8 px-3 py-2.5 text-[12px] leading-[1.5] text-destructive"
								role="alert"
							>
								{error}
							</p>
						)}
					</div>

					<DialogFooter className="flex-col-reverse sm:flex-row">
						<DialogButton
							variant="outline"
							className="w-full sm:w-auto"
							onClick={closeManualAttempt}
							disabled={submitting}
						>
							Cancel
						</DialogButton>
						<DialogButton
							className="w-full sm:w-auto"
							onClick={() => {
								void finishManualConnection();
							}}
							disabled={submitting || !callbackUrl.trim()}
						>
							{submitting && <Loader2 className="size-3.5 animate-spin" />}
							{submitting ? "Finishing connection…" : "Finish connection"}
						</DialogButton>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</McpOAuthContext.Provider>
	);
}

export function useMcpOAuth() {
	const context = useContext(McpOAuthContext);
	if (!context) {
		throw new Error("useMcpOAuth must be used within McpOAuthProvider");
	}
	return context;
}
