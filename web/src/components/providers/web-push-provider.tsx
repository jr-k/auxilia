"use client";

import { useEffect } from "react";

import { useUserStore } from "@/stores/user-store";
import { useWebPushStore } from "@/stores/web-push-store";

export function WebPushProvider({ children }: { children: React.ReactNode }) {
	const userId = useUserStore((state) => state.user?.id);
	const reconcile = useWebPushStore((state) => state.reconcile);

	useEffect(() => {
		if (!userId) return;
		void reconcile();
	}, [reconcile, userId]);

	return children;
}
