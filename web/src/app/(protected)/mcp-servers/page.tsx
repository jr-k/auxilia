"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Unplug } from "lucide-react";
import MCPServerTable from "@/app/(protected)/mcp-servers/components/mcp-server-table";
import { DisconnectSummaryDialog } from "@/app/(protected)/mcp-servers/components/disconnect-summary-dialog";
import ForbiddenErrorDialog from "@/components/forbidden-error-dialog";
import { useConfirmDialog } from "@/components/providers/dialog-provider";
import { Alert } from "@/components/ui/alert";
import { ResourceScopeFilterDropdown } from "@/components/ui/resource-scope-filter";
import { ViewToggle } from "@/components/ui/view-toggle";
import {
	WorkspacePage,
	WorkspaceTopBarButton,
} from "@/components/layout/workspace-page";
import { usePersistedViewMode } from "@/hooks/use-persisted-view-mode";
import { useQueryParamState } from "@/hooks/use-query-param-state";
import { getApiErrorMessage } from "@/lib/api/errors";
import * as mcpServersApi from "@/lib/api/resources/mcp-servers";
import type { ResourceScopeFilter } from "@/lib/resource-scope-filter";
import { useUserStore } from "@/stores/user-store";
import type { MCPConnectionDisconnectSummary } from "@/types/mcp-servers";

export default function MCPServersPage() {
	const router = useRouter();
	const confirmDialog = useConfirmDialog();
	const user = useUserStore((state) => state.user);
	const [search, setSearch] = useQueryParamState("q");
	const [scopeParam, setScopeParam] = useQueryParamState("scope", "all");
	const [teamParam, setTeamParam] = useQueryParamState("teams");
	const scope: ResourceScopeFilter =
		scopeParam === "personal" ||
		scopeParam === "workspace" ||
		scopeParam === "teams"
			? scopeParam
			: "all";
	const filterTeamIds = teamParam.split(",").filter(Boolean);
	const [errorDialogOpen, setErrorDialogOpen] = useState(false);
	const [viewMode, setViewMode] = usePersistedViewMode("mcp-servers:view-mode");
	const [isDisconnectingAll, setIsDisconnectingAll] = useState(false);
	const [disconnectError, setDisconnectError] = useState<string | null>(null);
	const [disconnectSummary, setDisconnectSummary] =
		useState<MCPConnectionDisconnectSummary | null>(null);
	const [summaryOpen, setSummaryOpen] = useState(false);

	const handleAddServer = () => {
		if (!user) return;
		if (user.role !== "admin") {
			setErrorDialogOpen(true);
			return;
		}
		router.push("/mcp-servers/add");
	};

	const handleDisconnectAll = async () => {
		if (
			!(await confirmDialog({
				title: "Disconnect all your MCP accounts?",
				description:
					"Only your personal OAuth accounts in this workspace will be disconnected. Other users, API keys, service accounts, and shared integrations will be preserved.",
				confirmLabel: "Disconnect all my accounts",
				destructive: true,
			}))
		)
			return;

		setDisconnectError(null);
		setIsDisconnectingAll(true);
		try {
			const result = await mcpServersApi.disconnectAllMyMcpConnections();
			setDisconnectSummary(result);
			setSummaryOpen(true);
		} catch (error) {
			setDisconnectError(
				getApiErrorMessage(error, "Failed to disconnect your MCP accounts."),
			);
		} finally {
			setIsDisconnectingAll(false);
		}
	};

	return (
		<WorkspacePage
			slug="mcp-servers"
			title="MCP servers"
			intro="Remote Model Context Protocol endpoints wired into your workspace."
			fillHeight={viewMode === "table"}
			search={{
				placeholder: "Search servers…",
				value: search,
				onChange: setSearch,
			}}
			actions={
				<>
					<WorkspaceTopBarButton
						aria-label="Disconnect all my MCP accounts"
						title="Disconnect all my MCP accounts"
						className="size-9 justify-center p-0 lg:h-auto lg:w-auto lg:px-[14px] lg:py-[9px]"
						disabled={!user || isDisconnectingAll}
						onClick={() => {
							void handleDisconnectAll();
						}}
					>
						<Unplug className="size-3.5" />
						<span className="hidden lg:inline">
							{isDisconnectingAll
								? "Disconnecting…"
								: "Disconnect all my MCP accounts"}
						</span>
					</WorkspaceTopBarButton>
					<WorkspaceTopBarButton
						aria-label="Add MCP server"
						title="Add MCP server"
						className="size-9 justify-center p-0 lg:h-auto lg:w-auto lg:px-[18px] lg:py-[9px]"
						// Until /auth/me resolves the role check can't run, so keep it
						// disabled rather than letting a click silently do nothing.
						disabled={!user}
						onClick={() => {
							handleAddServer();
						}}
					>
						<Plus className="size-3.5" />
						<span className="hidden lg:inline">Add MCP server</span>
					</WorkspaceTopBarButton>
				</>
			}
			headerRight={
				<div className="flex w-full min-w-0 items-center gap-3">
					<ResourceScopeFilterDropdown
						value={scope}
						teamIds={filterTeamIds}
						onChange={(next, teamIds) => {
							setScopeParam(next);
							setTeamParam(teamIds.join(","));
						}}
					/>
					<ViewToggle
						value={viewMode}
						onChange={setViewMode}
						className="ml-auto"
					/>
				</div>
			}
		>
			<ForbiddenErrorDialog
				open={errorDialogOpen}
				onOpenChange={setErrorDialogOpen}
				title="Insufficient privileges"
				message="You need admin permissions to add MCP servers."
			/>
			{disconnectError && (
				<Alert
					key={disconnectError}
					message={disconnectError}
					className="mb-4"
				/>
			)}
			<MCPServerTable
				mode={viewMode}
				search={search}
				scope={scope}
				filterTeamIds={filterTeamIds}
				onClearSearch={() => {
					setSearch("");
				}}
			/>
			<DisconnectSummaryDialog
				open={summaryOpen}
				onOpenChange={setSummaryOpen}
				summary={disconnectSummary}
			/>
		</WorkspacePage>
	);
}
