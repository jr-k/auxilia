"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { appearanceLogoUrl } from "@/lib/api/resources/appearance";
import { useAppearanceStore } from "@/stores/appearance-store";

export function AppearanceInitializer() {
	const pathname = usePathname();
	const isPublicShare =
		pathname === "/share" || pathname.startsWith("/share/");
	const appearance = useAppearanceStore((state) => state.appearance);
	const fetchAppearance = useAppearanceStore((state) => state.fetchAppearance);

	useEffect(() => {
		if (isPublicShare) return;
		const retry = () => {
			void fetchAppearance();
		};
		retry();
		window.addEventListener("online", retry);
		window.addEventListener("focus", retry);
		return () => {
			window.removeEventListener("online", retry);
			window.removeEventListener("focus", retry);
		};
	}, [fetchAppearance, isPublicShare]);

	useEffect(() => {
		if (isPublicShare) return;
		const applyTitle = () => {
			if (document.title !== appearance.appName) {
				document.title = appearance.appName;
			}
		};

		applyTitle();
		const observer = new MutationObserver(applyTitle);
		observer.observe(document.head, {
			childList: true,
			subtree: true,
			characterData: true,
		});

		return () => {
			observer.disconnect();
		};
	}, [appearance.appName, isPublicShare]);

	useEffect(() => {
		let favicon = document.querySelector<HTMLLinkElement>(
			'link[data-workspace-favicon="true"]',
		);
		if (!favicon) {
			favicon = document.createElement("link");
			favicon.rel = "icon";
			favicon.dataset.workspaceFavicon = "true";
			document.head.appendChild(favicon);
		}
		favicon.href = isPublicShare
			? "/pwa-icon.svg"
			: appearance.logoRevision
			? appearanceLogoUrl(appearance.logoRevision)
			: "/pwa-icon.svg";
	}, [appearance.logoRevision, isPublicShare]);

	return null;
}
