import { MCPAuthType } from "@/types/mcp-servers";
import { cn } from "@/lib/utils";

// Exhaustive switch (not a keyed lookup) so static analysis can verify the
// access — the union type guarantees every case is covered.
function badgeFor(authType: MCPAuthType): { label: string; className: string } {
	switch (authType) {
		case "oauth2":
			return {
				label: "OAuth 2.0",
				className:
					"bg-neutral-bg text-subtle dark:bg-white/10 dark:text-panel-body",
			};
		case "api_key":
			return {
				label: "API key",
				className:
					"bg-neutral-bg text-subtle dark:bg-white/10 dark:text-panel-body",
			};
		case "service_identity":
			return {
				label: "Service identity",
				className:
					"bg-neutral-bg text-subtle dark:bg-white/10 dark:text-panel-body",
			};
		case "custom_http":
			return {
				label: "Custom HTTP",
				className:
					"bg-neutral-bg text-subtle dark:bg-white/10 dark:text-panel-body",
			};
		case "none":
			return {
				label: "Open",
				className:
					"bg-neutral-bg text-subtle dark:bg-white/10 dark:text-panel-body",
			};
	}
}

/** Neutral auth chip: OAuth 2.0, API key, Open… */
export function AuthTypeBadge({
	authType,
	className,
}: {
	authType: MCPAuthType;
	className?: string;
}) {
	const badge = badgeFor(authType);
	return (
		<span
			className={cn(
				"inline-flex shrink-0 items-center rounded-[4px] px-2 py-[3px] text-[10.5px] font-medium",
				badge.className,
				className,
			)}
		>
			{badge.label}
		</span>
	);
}
