"use client";

import Link from "next/link";
import { Lock } from "lucide-react";
import { Fragment } from "react";
import { cn } from "@/lib/utils";
import { useWorkspacesStore } from "@/stores/workspaces-store";

export interface BreadcrumbSegment {
	label: string;
	href?: string;
}

/**
 * Breadcrumb trail of every top bar. The active workspace is always the
 * root, so callers pass only the segments below it, with page names
 * ("MCP servers"), never route slugs.
 */
export function Breadcrumbs({ trail }: { trail: BreadcrumbSegment[] }) {
	const workspaceName = useWorkspacesStore(
		(state) =>
			state.workspaces.find(
				(workspace) => workspace.id === state.activeWorkspaceId,
			)?.name,
	);
	const segments: BreadcrumbSegment[] = [
		{ label: workspaceName ?? "Workspace", href: "/" },
		...trail,
	];
	return (
		<nav
			aria-label="Breadcrumb"
			className="flex min-w-0 items-center overflow-hidden whitespace-nowrap text-[12px] text-meta dark:text-panel-dim"
		>
			{segments.map((segment, i) => {
				const isLast = i === segments.length - 1;
				const segmentClass = cn(
					"block truncate",
					isLast ? "max-w-[60%] shrink-0 font-medium text-foreground" : "min-w-0",
				);
				return (
					<Fragment key={`${segment.label}-${i}`}>
						{i > 0 && (
							<span className="mx-1.5 shrink-0 text-ghost dark:text-panel-dim">
								/
							</span>
						)}
						{segment.href && !isLast ? (
							<Link
								href={segment.href}
								className={cn(
									segmentClass,
									"rounded-[3px] transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-petrol/35",
								)}
							>
								{segment.label}
							</Link>
						) : (
							<span className={segmentClass}>{segment.label}</span>
						)}
					</Fragment>
				);
			})}
		</nav>
	);
}

/**
 * 52px top bar for workspace subpages (MCP servers add/custom/detail,
 * trigger editor/detail): breadcrumb trail on the left, an optional
 * status badge (e.g. Unsaved), action buttons on the right. Mirrors the
 * agent editor's header bar.
 */
export function SubpageHeader({
	trail,
	badge,
	children,
}: {
	trail: BreadcrumbSegment[];
	badge?: React.ReactNode;
	children?: React.ReactNode;
}) {
	return (
		<header className="flex h-[52px] shrink-0 items-center gap-3 border-b border-border pl-14 pr-4 md:px-7">
			<Breadcrumbs trail={trail} />
			{badge}
			<div className="ml-auto flex shrink-0 items-center gap-2">{children}</div>
		</header>
	);
}

/** Amber UNSAVED chip for explicit-save editors (matches the agent editor). */
export function UnsavedBadge() {
	return (
		<span className="rounded-[4px] bg-warning-bg px-2 py-0.5 text-[10px] font-semibold text-warning">
			Unsaved
		</span>
	);
}

/**
 * Inert "Read-only" marker, sized like a header button so it sits in the
 * slot the Edit button would occupy. Muted and cursor-default: it holds the
 * place of an action rather than offering one.
 */
export function HeaderReadOnly({ title }: { title?: string }) {
	return (
		<span
			title={title}
			className="flex cursor-default items-center gap-1.5 rounded-[7px] border border-input bg-card px-3.5 py-2 text-[13px] font-semibold text-meta dark:text-panel-dim"
		>
			<Lock className="size-3.5" />
			Read-only
		</span>
	);
}

/** Outline header button (Cancel, Edit server…). Teal text via `accent`. */
export function HeaderButton({
	accent = false,
	className,
	children,
	...props
}: React.ComponentProps<"button"> & { accent?: boolean }) {
	return (
		<button
			type="button"
			className={cn(
				"flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-[7px] border border-input bg-card px-4 py-2 text-[13px] font-semibold transition-colors hover:border-border-hover disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/10 dark:bg-white/[0.03] dark:hover:border-white/20",
				accent
					? "text-petrol dark:text-panel-terminal"
					: "text-foreground",
				className,
			)}
			{...props}
		>
			{children}
		</button>
	);
}

/** Filled petrol primary header button (Save changes, Add server…). */
export function HeaderPrimaryButton({
	className,
	children,
	...props
}: React.ComponentProps<"button">) {
	return (
		<button
			type="button"
			className={cn(
				"cursor-pointer whitespace-nowrap rounded-[7px] bg-petrol px-[18px] py-2 text-[13px] font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50",
				className,
			)}
			{...props}
		>
			{children}
		</button>
	);
}
