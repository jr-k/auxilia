"use client";

import {
	ArrowLeft,
	ArrowRight,
	BellRing,
	Check,
	Loader2,
	Menu,
	ShieldCheck,
	Volume2,
	type LucideIcon,
} from "lucide-react";
import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useState,
} from "react";
import {
	Dialog,
	DialogButton,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import * as usersApi from "@/lib/api/resources/users";
import {
	setConfirmExternalLinks,
	setResponseSoundEnabled,
	setShowShortcutsInMenu,
	useConfirmExternalLinks,
	useResponseSoundEnabled,
	useShowShortcutsInMenu,
} from "@/lib/user-preferences";
import { cn } from "@/lib/utils";
import { useAppearanceStore } from "@/stores/appearance-store";
import { useUserStore } from "@/stores/user-store";
import { useWebPushStore } from "@/stores/web-push-store";

const PREFERENCES_ONBOARDING_VERSION = 1;

interface PreferencesOnboardingContextValue {
	openOnboarding: () => void;
}

const PreferencesOnboardingContext =
	createContext<PreferencesOnboardingContextValue | null>(null);

export function usePreferencesOnboarding(): PreferencesOnboardingContextValue {
	const context = useContext(PreferencesOnboardingContext);
	if (context === null) {
		throw new Error(
			"usePreferencesOnboarding must be used within PreferencesOnboardingProvider",
		);
	}
	return context;
}

interface OnboardingStep {
	title: string;
	description: string;
	icon: LucideIcon;
	settingTitle: string;
	settingDescription: string;
	checked: boolean;
	disabled?: boolean;
	onCheckedChange: (checked: boolean) => void;
	status?: string;
	statusError?: boolean;
}

export function PreferencesOnboardingProvider({
	children,
}: {
	children: React.ReactNode;
}) {
	const user = useUserStore((state) => state.user);
	const setUser = useUserStore((state) => state.setUser);
	const appName = useAppearanceStore((state) => state.appearance.appName);
	const confirmExternalLinks = useConfirmExternalLinks();
	const responseSoundEnabled = useResponseSoundEnabled();
	const showShortcutsInMenu = useShowShortcutsInMenu();
	const webPushState = useWebPushStore((state) => state.state);
	const webPushError = useWebPushStore((state) => state.error);
	const enableWebPush = useWebPushStore((state) => state.enable);
	const disableWebPush = useWebPushStore((state) => state.disable);
	const [open, setOpen] = useState(false);
	const [activeStep, setActiveStep] = useState(0);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const onboardingUserId = user?.id ?? null;
	const shouldOpenAutomatically =
		user !== null &&
		user.supervision === null &&
		user.preferencesOnboardingVersion < PREFERENCES_ONBOARDING_VERSION;

	const openOnboarding = useCallback(() => {
		setActiveStep(0);
		setError(null);
		setOpen(true);
	}, []);

	useEffect(() => {
		if (shouldOpenAutomatically) openOnboarding();
	}, [onboardingUserId, openOnboarding, shouldOpenAutomatically]);

	const webPushDescription = {
		loading: "Checking notification status…",
		unsupported: "This browser does not support Web Push notifications.",
		"not-configured":
			"Browser notifications are not configured on this deployment.",
		denied:
			"Permission is blocked. Allow notifications in your browser settings first.",
		disabled:
			"Receive a system notification when an agent finishes, even in the background.",
		enabled: "System notifications are enabled on this browser.",
		error: webPushError ?? "Could not check notification status.",
	}[webPushState];
	const webPushCanToggle = ![
		"loading",
		"unsupported",
		"not-configured",
	].includes(webPushState);

	const steps: OnboardingStep[] = [
		{
			title: "Browser notifications",
			description: `Let ${appName} tell you when an answer is ready, even when you are working in another tab or app.`,
			icon: BellRing,
			settingTitle: "Notify me when an agent finishes",
			settingDescription:
				"This permission belongs to this browser and can be changed later.",
			checked: webPushState === "enabled",
			disabled: !webPushCanToggle,
			onCheckedChange: (checked) => {
				if (checked) void enableWebPush();
				else void disableWebPush();
			},
			status: webPushDescription,
			statusError: webPushState === "error" || webPushState === "denied",
		},
		{
			title: "Response sound",
			description:
				"Use a short sound as a quiet cue that the current response has finished.",
			icon: Volume2,
			settingTitle: "Play a sound when a response is ready",
			settingDescription:
				"Useful when a long-running answer is open in the background.",
			checked: responseSoundEnabled,
			onCheckedChange: setResponseSoundEnabled,
		},
		{
			title: "External links",
			description:
				"Choose whether assistant links pause for a safety confirmation before leaving the app.",
			icon: ShieldCheck,
			settingTitle: "Confirm before opening external links",
			settingDescription:
				"Ctrl/Cmd+click can still open a link directly in a new tab.",
			checked: confirmExternalLinks,
			onCheckedChange: setConfirmExternalLinks,
		},
		{
			title: "Navigation shortcuts",
			description:
				"Keep your main workspace destinations visible in the desktop sidebar.",
			icon: Menu,
			settingTitle: "Show shortcuts in the sidebar",
			settingDescription:
				"When disabled, shortcuts remain available from the overflow menu.",
			checked: showShortcutsInMenu,
			onCheckedChange: setShowShortcutsInMenu,
		},
	];

	const step = steps[activeStep];
	const isLastStep = activeStep === steps.length - 1;

	const complete = async () => {
		if (user === null || saving) return;
		setSaving(true);
		setError(null);
		try {
			const version = await usersApi.updatePreferencesOnboarding(
				PREFERENCES_ONBOARDING_VERSION,
			);
			const currentUser = useUserStore.getState().user;
			if (currentUser?.id === user.id) {
				setUser({
					...currentUser,
					preferencesOnboardingVersion: version,
				});
			}
			setOpen(false);
		} catch {
			setError("Could not save your onboarding progress. Please try again.");
		} finally {
			setSaving(false);
		}
	};

	return (
		<PreferencesOnboardingContext.Provider value={{ openOnboarding }}>
			{children}
			<Dialog
				open={open}
				onOpenChange={(nextOpen) => {
					if (!saving) setOpen(nextOpen);
				}}
			>
				<DialogContent
					showCloseButton={!saving}
					className="gap-0 overflow-hidden p-0 sm:max-w-[760px]"
				>
					<DialogHeader className="border-b border-border px-5 py-4 pr-14 dark:border-white/10 sm:px-6">
						<DialogTitle>Set up your experience</DialogTitle>
						<DialogDescription className="mt-0.5">
							Four quick choices to make {appName} work the way you prefer.
						</DialogDescription>
					</DialogHeader>

					<div className="grid min-h-[430px] grid-cols-[78px_minmax(0,1fr)] sm:grid-cols-[220px_minmax(0,1fr)]">
						<nav
							aria-label="Preference onboarding steps"
							className="border-r border-border bg-card/45 py-3 dark:border-white/10 dark:bg-white/[0.025] sm:py-4"
						>
							<ol className="space-y-1">
								{steps.map((candidate, index) => {
									const Icon = candidate.icon;
									const active = activeStep === index;
									const visited = index < activeStep;
									return (
										<li key={candidate.title}>
											<button
												type="button"
												aria-current={active ? "step" : undefined}
												title={candidate.title}
												onClick={() => {
													setActiveStep(index);
													setError(null);
												}}
												className={cn(
													"group flex w-full cursor-pointer items-center justify-center gap-3 px-3 py-3 text-left transition-colors sm:justify-start sm:px-4",
													active
														? "bg-petrol/[0.08]"
														: "hover:bg-hover dark:hover:bg-white/5",
												)}
											>
												<span
													className={cn(
														"flex size-8 shrink-0 items-center justify-center rounded-[9px] border transition-colors",
														active
															? "border-petrol bg-petrol text-white"
															: visited
																? "border-petrol/25 bg-petrol/10 text-petrol dark:text-panel-terminal"
																: "border-border bg-card text-meta dark:border-white/10",
													)}
												>
													{visited ? (
														<Check className="size-3.5" />
													) : (
														<Icon className="size-3.5" />
													)}
												</span>
												<span
													className={cn(
														"hidden min-w-0 text-[12.5px] font-semibold sm:block",
														active ? "text-foreground" : "text-subtle",
													)}
												>
													{candidate.title}
												</span>
											</button>
										</li>
									);
								})}
							</ol>
						</nav>

						<section
							aria-live="polite"
							className="flex min-w-0 flex-col px-4 py-5 sm:px-7 sm:py-6"
						>
							<div className="flex-1">
								<h3 className="text-[20px] font-bold text-foreground">
									{step.title}
								</h3>
								<p className="mt-2 max-w-[460px] text-[13.5px] leading-6 text-subtle dark:text-panel-body">
									{step.description}
								</p>

								<div className="mt-6 rounded-[11px] border border-border bg-card p-4 dark:border-white/10 dark:bg-white/[0.025]">
									<div className="flex items-start justify-between gap-5">
										<div className="min-w-0">
											<p className="text-[13px] font-semibold text-foreground">
												{step.settingTitle}
											</p>
											<p className="mt-1 text-[12px] leading-5 text-subtle dark:text-panel-body">
												{step.settingDescription}
											</p>
										</div>
										<Switch
											checked={step.checked}
											disabled={step.disabled}
											onCheckedChange={step.onCheckedChange}
											aria-label={step.settingTitle}
											className="mt-0.5 shrink-0 cursor-pointer disabled:cursor-default"
										/>
									</div>
									{step.status && (
										<p
											className={cn(
												"mt-3 border-t border-border pt-3 text-[11.5px] leading-5 dark:border-white/10",
												step.statusError
													? "text-destructive"
													: "text-meta dark:text-panel-dim",
											)}
										>
											{step.status}
										</p>
									)}
								</div>

								{error && (
									<p className="mt-4 rounded-[8px] bg-destructive/10 px-3 py-2 text-[12px] text-destructive">
										{error}
									</p>
								)}
							</div>

							<div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4 dark:border-white/10">
								<button
									type="button"
									disabled={saving}
									onClick={() => {
										void complete();
									}}
									className="cursor-pointer text-[12px] font-semibold text-meta transition-colors hover:text-foreground disabled:cursor-default disabled:opacity-50"
								>
									Skip for now
								</button>
								<div className="ml-auto flex items-center gap-2">
									{activeStep > 0 && (
										<DialogButton
											variant="outline"
											disabled={saving}
											onClick={() => {
												setActiveStep((current) => current - 1);
												setError(null);
											}}
										>
											<ArrowLeft className="size-3.5" />
											Back
										</DialogButton>
									)}
									<DialogButton
										disabled={saving}
										onClick={() => {
											if (isLastStep) void complete();
											else {
												setActiveStep((current) => current + 1);
												setError(null);
											}
										}}
									>
										{saving ? (
											<Loader2 className="size-3.5 animate-spin" />
										) : isLastStep ? (
											<Check className="size-3.5" />
										) : (
											<ArrowRight className="size-3.5" />
										)}
										{saving ? "Saving…" : isLastStep ? "Finish" : "Next"}
									</DialogButton>
								</div>
							</div>
						</section>
					</div>
				</DialogContent>
			</Dialog>
		</PreferencesOnboardingContext.Provider>
	);
}
