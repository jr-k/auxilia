import type { MetadataRoute } from "next";

const DEFAULT_APP_NAME = "auxilia";
const DEFAULT_ICONS: MetadataRoute.Manifest["icons"] = [
	{
		src: "/pwa-icon-192.png",
		sizes: "192x192",
		type: "image/png",
		purpose: "any",
	},
	{
		src: "/pwa-icon-512.png",
		sizes: "512x512",
		type: "image/png",
		purpose: "any",
	},
	{
		src: "/pwa-icon-512.png",
		sizes: "512x512",
		type: "image/png",
		purpose: "maskable",
	},
];

interface AppearanceResponse {
	app_name: string;
	logo_revision: string | null;
}

export const dynamic = "force-dynamic";

async function getAppearance(): Promise<AppearanceResponse> {
	const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
	try {
		const response = await fetch(`${backendUrl}/appearance/`, {
			cache: "no-store",
		});
		if (!response.ok) throw new Error(`Appearance request failed: ${response.status}`);
		return (await response.json()) as AppearanceResponse;
	} catch {
		return {
			app_name: DEFAULT_APP_NAME,
			logo_revision: null,
		};
	}
}

export default async function manifest(): Promise<MetadataRoute.Manifest> {
	const appearance = await getAppearance();
	const name = appearance.app_name.trim() || DEFAULT_APP_NAME;
	const icons = appearance.logo_revision
		? [
				{
					src: `/api/backend/appearance/logo?revision=${encodeURIComponent(appearance.logo_revision)}`,
					sizes: "512x512",
					type: "image/webp",
					purpose: "any" as const,
				},
				{
					src: `/api/backend/appearance/logo?revision=${encodeURIComponent(appearance.logo_revision)}`,
					sizes: "512x512",
					type: "image/webp",
					purpose: "maskable" as const,
				},
			]
		: DEFAULT_ICONS;

	return {
		name,
		short_name: name,
		description: "Build and use MCP-powered AI assistants.",
		start_url: "/agents",
		scope: "/",
		display: "standalone",
		background_color: "#ffffff",
		theme_color: "#16606e",
		orientation: "any",
		categories: ["productivity", "utilities"],
		icons,
	};
}
