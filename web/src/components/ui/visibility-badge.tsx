"use client";

import { useEffect, useState } from "react";
import { Building2, LockKeyhole, Users } from "lucide-react";
import { listTeams } from "@/lib/api/resources/teams";
import type { ResourceVisibility } from "@/types/visibility";

const META = {
	personal: { label: "Personal", Icon: LockKeyhole },
	workspace: { label: "Workspace", Icon: Building2 },
	teams: { label: "Teams", Icon: Users },
} as const;

export function VisibilityBadge({
	visibility,
	teamIds = [],
	showTeams = false,
}: {
	visibility: ResourceVisibility;
	teamIds?: string[];
	showTeams?: boolean;
}) {
	const { label, Icon } = META[visibility];
	const requestKey =
		showTeams && visibility === "teams" ? [...teamIds].sort().join(",") : "";
	const [resolved, setResolved] = useState<{
		key: string;
		names: string[];
	}>({ key: "", names: [] });
	useEffect(() => {
		let cancelled = false;
		if (!requestKey) {
			return () => {
				cancelled = true;
			};
		}
		void listTeams()
			.then((teams) => {
				if (cancelled) return;
				const wanted = new Set(requestKey.split(","));
				setResolved({
					key: requestKey,
					names: teams
						.filter((team) => wanted.has(team.id))
						.map((team) => team.name),
				});
			})
			.catch(() => {
				if (!cancelled) setResolved({ key: requestKey, names: [] });
			});
		return () => {
			cancelled = true;
		};
	}, [requestKey]);
	const teamNames = resolved.key === requestKey ? resolved.names : [];
	const text =
		showTeams && visibility === "teams" && teamNames.length > 0
			? `${label}: ${teamNames.join(", ")}`
			: label;
	return (
		<span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-hover px-2.5 py-1 text-[10.5px] font-semibold text-subtle dark:bg-white/10 dark:text-panel-body">
			<Icon className="size-3" />
			{text}
		</span>
	);
}
