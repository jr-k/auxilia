import type { NextConfig } from "next";

const nextConfig: NextConfig = {
	reactCompiler: true,
	output: "standalone",
	// The demo recording builds into its own dist dir (npm run demo:web) so
	// `next build` never clobbers the `.next` of a running `next dev`.
	distDir: process.env.NEXT_DIST_DIR ?? ".next",
	images: {
		remotePatterns: [
			{
				protocol: "https",
				hostname: "pub-7a6e8912b3c448b8a8bfa47a0363f7bc.r2.dev",
			},
			{
				protocol: "https",
				hostname: "models.dev",
			},
		],
	},
	async rewrites() {
		return [
			{ source: "/docs", destination: "/api/backend/docs" },
			{
				source: "/docs/oauth2-redirect",
				destination: "/api/backend/docs/oauth2-redirect",
			},
			{ source: "/openapi.json", destination: "/api/backend/openapi.json" },
			{ source: "/mcp", destination: "/api/backend/mcp" },
			{ source: "/register", destination: "/api/backend/register" },
			{ source: "/authorize", destination: "/api/backend/authorize" },
			{ source: "/token", destination: "/api/backend/token" },
			{ source: "/revoke", destination: "/api/backend/revoke" },
			{
				source: "/.well-known/:path*",
				destination: "/api/backend/.well-known/:path*",
			},
		];
	},
	async redirects() {
		return [
			{
				source: "/",
				destination: "/agents",
				permanent: true,
			},
		];
	},
};

export default nextConfig;
