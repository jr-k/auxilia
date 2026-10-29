"use client";

import { useEffect, useState } from "react";
import { LogOut } from "lucide-react";
import { toast } from "sonner";

import * as authApi from "@/lib/api/resources/auth";
import { getApiErrorMessage } from "@/lib/api/errors";
import { useUserStore } from "@/stores/user-store";

export function SupervisionBanner({
	loadSession = false,
}: {
	loadSession?: boolean;
}) {
	const user = useUserStore((state) => state.user);
	const setUser = useUserStore((state) => state.setUser);
	const [leaving, setLeaving] = useState(false);

	useEffect(() => {
		if (!loadSession || user) return;
		let active = true;
		void authApi
			.getCurrentUser()
			.then((currentUser) => {
				if (active) setUser(currentUser);
			})
			.catch(() => {
				// The route owns its unauthenticated/error state.
			});
		return () => {
			active = false;
		};
	}, [loadSession, setUser, user]);

	if (!user?.supervision) return null;

	const identity = user.name || user.email || "this user";

	const exitSupervision = async () => {
		if (leaving) return;
		setLeaving(true);
		try {
			await authApi.stopSupervision();
			window.location.assign("/users");
		} catch (error) {
			setLeaving(false);
			toast.error(
				getApiErrorMessage(error, "Could not exit supervision."),
			);
		}
	};

	return (
		<div
			role="status"
			className="flex h-11 shrink-0 items-center gap-3 border-b border-orange-400/50 bg-orange-100 px-3 text-orange-950 dark:border-orange-400/30 dark:bg-orange-950 dark:text-orange-100 sm:px-5"
		>
			<span className="size-2 shrink-0 rounded-full bg-orange-500" />
			<p className="min-w-0 flex-1 truncate text-[12px] font-semibold sm:text-[13px]">
				Supervising {identity}
				<span className="hidden font-normal text-orange-800/80 dark:text-orange-200/75 sm:inline">
					{" "}
					with this user&apos;s permissions
				</span>
			</p>
			<button
				type="button"
				disabled={leaving}
				onClick={() => {
					void exitSupervision();
				}}
				className="inline-flex shrink-0 cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-[7px] border border-orange-500/35 bg-orange-50 px-3 py-1.5 text-[11.5px] font-semibold text-orange-950 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-60 dark:bg-orange-900 dark:text-orange-50 dark:hover:bg-orange-800"
			>
				<LogOut className="size-3.5" />
				{leaving ? "Exiting…" : "Exit supervision"}
			</button>
		</div>
	);
}
