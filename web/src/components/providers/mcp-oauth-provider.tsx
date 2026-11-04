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
	ArrowRight,
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
	signInUrl?: string | null;
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
	const [manualStep, setManualStep] = useState(0);
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
		setManualStep(0);
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
				const signInUrl = request.signInUrl
					? safeAuthorizationUrl(request.signInUrl)
					: null;
				if (request.signInUrl && !signInUrl) {
					request.popup?.close();
					toast.error("The service sign-in URL is invalid.");
					return false;
				}
				request.popup?.close();
				if (manualPopupRef.current && !manualPopupRef.current.closed) {
					manualPopupRef.current.close();
				}
				manualPopupRef.current = null;
				setCallbackUrl("");
				setError(null);
				setSubmitting(false);
				setManualStep(0);
				setManualAttempt({ ...request, authUrl, signInUrl, popup: null });
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

	const openServiceSignIn = useCallback(() => {
		if (!manualAttempt) return;
		if (!manualAttempt.signInUrl) {
			setManualStep(1);
			return;
		}
		const popup = window.open(manualAttempt.signInUrl, "_blank");
		if (!popup) {
			setError("Allow pop-ups for this site, then try again.");
			return;
		}
		if (manualPopupRef.current && !manualPopupRef.current.closed) {
			manualPopupRef.current.close();
		}
		manualPopupRef.current = popup;
		setError(null);
	}, [manualAttempt]);

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
				<DialogContent className="gap-0 overflow-hidden p-0 sm:max-w-[960px]">
					<DialogHeader className="border-b border-border px-7 py-6 pr-14 dark:border-white/10">
						<DialogTitle>
							Connect {manualAttempt?.serverName ?? "the MCP server"}
						</DialogTitle>
						<DialogDescription>
							Sign in first, then start authorization and return the redirect
							address.
						</DialogDescription>
					</DialogHeader>

					<div className="grid min-h-[420px] grid-cols-[160px_minmax(0,1fr)] sm:grid-cols-[220px_minmax(0,1fr)]">
						<nav
							aria-label="OAuth connection steps"
							className="border-r border-border bg-card/45 py-4 dark:border-white/10 dark:bg-white/[0.025]"
						>
							<p className="mb-2 px-4 text-[10.5px] font-semibold text-meta sm:px-5">
								Connection steps
							</p>
							<ol>
								{[
									"Sign in to the service",
									"Get the redirect address",
									"Paste the callback address",
								].map((title, index) => (
									<li key={title}>
										<button
											type="button"
											aria-current={manualStep === index ? "step" : undefined}
											onClick={() => {
												setManualStep(index);
												setError(null);
											}}
											className={`group flex w-full cursor-pointer items-center gap-2.5 px-3 py-3 text-left transition-colors sm:px-4 ${
												manualStep === index
													? "bg-petrol/[0.07]"
													: "hover:bg-hover"
											}`}
										>
											<span
												className={`flex size-6 shrink-0 items-center justify-center rounded-full border font-mono text-[10.5px] font-semibold transition-colors ${
													manualStep === index
														? "border-petrol bg-petrol text-white"
														: "border-border bg-card text-meta group-hover:text-foreground dark:border-white/10"
												}`}
											>
												{index + 1}
											</span>
											<span
												className={`min-w-0 text-[12.5px] leading-[1.3] font-semibold ${
													manualStep === index
														? "text-foreground"
														: "text-subtle"
												}`}
											>
												{title}
											</span>
										</button>
									</li>
								))}
							</ol>
						</nav>

						<section className="flex min-w-0 flex-col">
							<div className="flex-1 p-6">
								{manualStep === 0 && (
									<div className="space-y-3">
										<h3 className="text-[15px] font-semibold text-foreground">
											Sign in to {manualAttempt?.serverName ?? "the service"}
										</h3>
										<p className="text-[12.5px] leading-[1.6] text-meta dark:text-panel-dim">
											Open the service and complete sign-in first. This step
											does not start OAuth and will not redirect you to
											127.0.0.1.
										</p>
										{manualAttempt?.signInUrl ? (
											<DialogButton
												variant="outline"
												onClick={openServiceSignIn}
												disabled={submitting}
											>
												<ExternalLink className="size-3.5" />
												Open {manualAttempt.serverName ?? "the service"}
											</DialogButton>
										) : (
											<p className="rounded-[8px] border border-border bg-hover/60 px-3 py-2.5 text-[12px] leading-[1.5] text-meta dark:border-white/10 dark:bg-white/5">
												A separate service sign-in page is not available.
												Continue when you are already signed in.
											</p>
										)}
									</div>
								)}

								{manualStep === 1 && (
									<div className="space-y-3">
										<h3 className="text-[15px] font-semibold text-foreground">
											Get the redirect address
										</h3>
										<p className="text-[12.5px] leading-[1.6] text-meta dark:text-panel-dim">
											Now start authorization. The service opens again and,
											after approval, redirects the browser to 127.0.0.1.
										</p>
										<p className="text-[12px] leading-[1.55] text-meta dark:text-panel-dim">
											The browser may report that it cannot connect. This is
											expected. Keep that page open so you can copy its
											complete address.
										</p>
										<DialogButton
											variant="outline"
											onClick={openManualAuthorization}
											disabled={submitting}
										>
											<ExternalLink className="size-3.5" />
											Get redirect address
										</DialogButton>
									</div>
								)}

								{manualStep === 2 && (
									<div className="space-y-4">
										<div>
											<h3 className="text-[15px] font-semibold text-foreground">
												Paste the callback address
											</h3>
											<p className="mt-2 text-[12.5px] leading-[1.6] text-meta dark:text-panel-dim">
												Copy the complete 127.0.0.1 address from the browser
												address bar, then paste it below.
											</p>
										</div>
										<DialogButton
											variant="outline"
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
										<div className="flex gap-2.5 text-[11.5px] leading-[1.5] text-meta dark:text-panel-dim">
											<LockKeyhole className="mt-0.5 size-3.5 shrink-0" />
											<p>
												The callback address is sensitive and temporary. Do
												not share it.
											</p>
										</div>
									</div>
								)}

								{error && (
									<p
										className="mt-4 rounded-[8px] bg-destructive/8 px-3 py-2.5 text-[12px] leading-[1.5] text-destructive"
										role="alert"
									>
										{error}
									</p>
								)}
							</div>

							<DialogFooter className="flex-nowrap border-t border-border px-7 py-5 dark:border-white/10">
								<DialogButton
									variant="outline"
									onClick={closeManualAttempt}
									disabled={submitting}
								>
									Cancel
								</DialogButton>
								<DialogButton
									onClick={() => {
										if (manualStep < 2) {
											setManualStep((current) => current + 1);
											setError(null);
											return;
										}
										void finishManualConnection();
									}}
									disabled={
										submitting || (manualStep === 2 && !callbackUrl.trim())
									}
								>
									{submitting ? (
										<Loader2 className="size-3.5 animate-spin" />
									) : (
										<ArrowRight className="size-3.5" />
									)}
									Continue
								</DialogButton>
							</DialogFooter>
						</section>
					</div>
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
