"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import TriggerList from "@/app/(protected)/triggers/components/trigger-list";
import { UnderlineTabs } from "@/components/ui/underline-tabs";
import { ViewToggle } from "@/components/ui/view-toggle";
import {
	WorkspacePage,
	WorkspaceTopBarButton,
} from "@/components/layout/workspace-page";
import { usePersistedViewMode } from "@/hooks/use-persisted-view-mode";
import { useTriggersStore } from "@/stores/triggers-store";
import { useUserStore } from "@/stores/user-store";

export default function TriggersPage() {
	const router = useRouter();
	const canCreate = useUserStore(
		(state) => state.user !== null && state.user.role !== "member",
	);
	const triggers = useTriggersStore((state) => state.triggers);
	const [view, setView] = useState<"active" | "paused">("active");
	const [viewMode, setViewMode] = usePersistedViewMode("triggers:view-mode");

	const activeCount = triggers.filter((trigger) => trigger.isActive).length;
	const pausedCount = triggers.length - activeCount;

	const handleCreate = () => {
		router.push("/triggers/new");
	};

	return (
		<WorkspacePage
			slug="triggers"
			title="Triggers"
			intro="Run agents automatically on a schedule or from an external webhook."
			fillHeight={viewMode === "table"}
			fullWidth
			actions={canCreate ? (
				<WorkspaceTopBarButton
					onClick={() => {
						handleCreate();
					}}
				>
					<Plus className="size-3.5" />
					New trigger
				</WorkspaceTopBarButton>
			) : undefined}
			headerRight={
				<div className="flex items-center gap-3">
					<UnderlineTabs
						tabs={[
							{ key: "active", label: "Active", count: activeCount },
							{ key: "paused", label: "Paused", count: pausedCount },
						]}
						value={view}
						onChange={setView}
					/>
					<ViewToggle value={viewMode} onChange={setViewMode} />
				</div>
			}
		>
			<TriggerList
				view={view}
				mode={viewMode}
				onCreate={handleCreate}
				canCreate={canCreate}
			/>
		</WorkspacePage>
	);
}
