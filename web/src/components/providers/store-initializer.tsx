"use client";

import { useEffect } from "react";
import { ensureSignedIn } from "@/lib/api/session";
import { useMcpServersStore } from "@/stores/mcp-servers-store";

export function StoreInitializer() {
	const { fetchMcpServers } = useMcpServersStore();

	useEffect(() => {
		// Initialize MCP servers store on app mount
		fetchMcpServers();
	}, [fetchMcpServers]);

	useEffect(() => {
		const onVisible = () => {
			if (document.visibilityState === "visible") void ensureSignedIn();
		};
		document.addEventListener("visibilitychange", onVisible);
		window.addEventListener("focus", onVisible);
		return () => {
			document.removeEventListener("visibilitychange", onVisible);
			window.removeEventListener("focus", onVisible);
		};
	}, []);

	return null;
}
