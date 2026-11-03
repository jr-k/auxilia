"use client";

import { useEffect, useState } from "react";
import { Building2, LockKeyhole, Users } from "lucide-react";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { listTeams } from "@/lib/api/resources/teams";
import { useWorkspacesStore } from "@/stores/workspaces-store";
import type { Team } from "@/types/users";
import type { ResourceVisibility } from "@/types/visibility";

const TEAM_CACHE_TTL_MS = 30_000;
const teamCache = new Map<
	string,
	{
		teams: Team[] | null;
		loadedAt: number;
		promise: Promise<Team[]> | null;
	}
>();

function loadTeams(workspaceId: string | null): Promise<Team[]> {
	const key = workspaceId ?? "active";
	const cached = teamCache.get(key);
	if (
		cached?.teams &&
		Date.now() - cached.loadedAt < TEAM_CACHE_TTL_MS
	) {
		return Promise.resolve(cached.teams);
	}
	if (cached?.promise) return cached.promise;

	const promise = listTeams(workspaceId ?? undefined)
		.then((teams) => {
			teamCache.set(key, {
				teams,
				loadedAt: Date.now(),
				promise: null,
			});
			return teams;
		})
		.catch((error: unknown) => {
			teamCache.delete(key);
			throw error;
		});
	teamCache.set(key, {
		teams: cached?.teams ?? null,
		loadedAt: cached?.loadedAt ?? 0,
		promise,
	});
	return promise;
}

function metaFor(visibility: ResourceVisibility) {
	switch (visibility) {
		case "personal":
			return { label: "Personal", Icon: LockKeyhole };
		case "workspace":
			return { label: "Workspace", Icon: Building2 };
		case "teams":
			return { label: "Teams", Icon: Users };
	}
	throw new Error("Unsupported resource visibility");
}

export function VisibilityBadge({
	visibility,
	teamIds = [],
	showTeams = false,
}: {
	visibility: ResourceVisibility;
	teamIds?: string[];
	showTeams?: boolean;
}) {
	const { label, Icon } = metaFor(visibility);
	const workspaceId = useWorkspacesStore((state) => state.activeWorkspaceId);
	const requestKey =
		visibility === "teams" ? [...teamIds].sort().join(",") : "";
	const [resolved, setResolved] = useState<{
		key: string;
		teams: Team[];
	}>({ key: "", teams: [] });
	useEffect(() => {
		let cancelled = false;
		if (!requestKey) {
			return () => {
				cancelled = true;
			};
		}
		void loadTeams(workspaceId)
			.then((teams) => {
				if (cancelled) return;
				const wanted = new Set(requestKey.split(","));
				setResolved({
					key: requestKey,
					teams: teams.filter((team) => wanted.has(team.id)),
				});
			})
			.catch(() => {
				if (!cancelled) setResolved({ key: requestKey, teams: [] });
			});
		return () => {
			cancelled = true;
		};
	}, [requestKey, workspaceId]);
	const resolvedTeams = resolved.key === requestKey ? resolved.teams : [];
	const teamsById = new Map(resolvedTeams.map((team) => [team.id, team]));
	const selectedTeams = teamIds.map((teamId) => teamsById.get(teamId));
	const teamNames = selectedTeams.flatMap((team) => (team ? [team.name] : []));
	const text =
		showTeams && visibility === "teams" && teamNames.length > 0
			? `${label}: ${teamNames.join(", ")}`
			: label;
	const badge = (
		<span className="inline-flex shrink-0 items-center gap-1.5 rounded-[4px] bg-hover px-2.5 py-1 text-[10.5px] font-semibold text-subtle dark:bg-white/10 dark:text-panel-body">
			<Icon className="size-3" />
			{text}
			{!showTeams && visibility === "teams" && teamIds.length > 0 && (
				<span className="flex items-center -space-x-0.5" aria-hidden="true">
					{selectedTeams.slice(0, 4).map((team, index) => (
						<span
							key={team?.id ?? teamIds[index]}
							className="size-2 rounded-full border border-card"
							style={{ backgroundColor: team?.color ?? "#78909C" }}
						/>
					))}
					{teamIds.length > 4 && (
						<span className="ml-1 text-[9px] text-meta">
							+{teamIds.length - 4}
						</span>
					)}
				</span>
			)}
		</span>
	);
	if (visibility !== "teams" || teamIds.length === 0) return badge;

	return (
		<Tooltip>
			<TooltipTrigger asChild>{badge}</TooltipTrigger>
			<TooltipContent sideOffset={6}>
				<div className="space-y-1.5">
					<p className="font-semibold">Visible to teams</p>
					{selectedTeams.map((team, index) => (
						<div
							key={team?.id ?? teamIds[index]}
							className="flex items-center gap-2"
						>
							<span
								className="size-2 rounded-full"
								style={{ backgroundColor: team?.color ?? "#78909C" }}
							/>
							<span>{team?.name ?? "Selected team"}</span>
						</div>
					))}
				</div>
			</TooltipContent>
		</Tooltip>
	);
}
