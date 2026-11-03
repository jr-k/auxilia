"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import {
	AsyncSearchSelect,
	type AsyncSearchOption,
} from "@/components/ui/async-search-select";
import {
	Dialog,
	DialogButton,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { getApiErrorMessage } from "@/lib/api/errors";
import * as projectsApi from "@/lib/api/resources/projects";
import { getProjectFolderPath } from "@/lib/project-folders";
import { useProjectsStore } from "@/stores/projects-store";
import { useThreadsStore } from "@/stores/threads-store";

export interface ThreadPlacementTarget {
	id: string;
	title: string;
	projectId: string | null;
	folderId: string | null;
}

export function ThreadPlacementDialog({
	open,
	onOpenChange,
	thread,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	thread: ThreadPlacementTarget | null;
}) {
	const projects = useProjectsStore((state) => state.tree);
	const refreshTree = useProjectsStore((state) => state.refreshTree);
	const setThreadPlacement = useThreadsStore((state) => state.setThreadPlacement);
	const [projectId, setProjectId] = useState<string | null>(null);
	const [folderId, setFolderId] = useState<string | null>(null);
	const [saving, setSaving] = useState(false);

	useEffect(() => {
		if (!open) return;
		setProjectId(thread?.projectId ?? null);
		setFolderId(thread?.folderId ?? null);
	}, [open, thread]);

	const selectedProject = projects.find((project) => project.id === projectId);
	const folders = selectedProject?.folders ?? [];
	const selectedFolder = folders.find((folder) => folder.id === folderId);
	const selectedProjectOption: AsyncSearchOption | null = selectedProject
		? {
				value: selectedProject.id,
				label: selectedProject.emoji
					? `${selectedProject.emoji} ${selectedProject.name}`
					: selectedProject.name,
				description: selectedProject.description || undefined,
			}
		: null;
	const selectedFolderOption: AsyncSearchOption | null = selectedFolder
		? {
				value: selectedFolder.id,
				label: getProjectFolderPath(selectedFolder, folders),
			}
		: null;
	const loadProjectOptions = useCallback(
		async (query: string, signal: AbortSignal) =>
			(await projectsApi.searchProjects(query, signal)).map((project) => ({
				value: project.id,
				label: project.emoji
					? `${project.emoji} ${project.name}`
					: project.name,
				description: project.description || undefined,
			})),
		[],
	);
	const loadFolderOptions = useCallback(
		async (query: string, signal: AbortSignal) => {
			if (!projectId) return [];
			return (
				await projectsApi.searchProjectFolders(projectId, query, signal)
			).map((folder) => ({
				value: folder.id,
				label: folder.path,
			}));
		},
		[projectId],
	);

	const save = async () => {
		if (!thread || saving) return;
		setSaving(true);
		try {
			await setThreadPlacement(thread.id, projectId, folderId);
			await refreshTree();
			onOpenChange(false);
		} catch (error) {
			toast.error(
				getApiErrorMessage(error, "The conversation could not be moved."),
			);
		} finally {
			setSaving(false);
		}
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>Move conversation</DialogTitle>
					<DialogDescription className="truncate">
						Choose a project and folder for {thread?.title ?? "this conversation"}.
					</DialogDescription>
				</DialogHeader>
				<div className="grid gap-3 sm:grid-cols-2">
					<AsyncSearchSelect
						label="Project"
						value={projectId}
						selectedOption={selectedProjectOption}
						placeholder="Search projects"
						emptyValueLabel="No project"
						loadOptions={loadProjectOptions}
						onChange={(nextProjectId) => {
							setProjectId(nextProjectId);
							setFolderId(null);
						}}
					/>
					<AsyncSearchSelect
						label="Folder"
						value={folderId}
						selectedOption={selectedFolderOption}
						placeholder="Search folders"
						emptyValueLabel="Project root"
						disabled={projectId === null}
						loadOptions={loadFolderOptions}
						onChange={(nextFolderId) => {
							setFolderId(nextFolderId);
						}}
					/>
				</div>
				<DialogFooter>
					<DialogButton
						variant="outline"
						onClick={() => {
							onOpenChange(false);
						}}
					>
						Cancel
					</DialogButton>
					<DialogButton
						disabled={!thread || saving}
						onClick={() => {
							void save();
						}}
					>
						{saving ? "Moving…" : "Move"}
					</DialogButton>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
