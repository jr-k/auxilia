"use client";

import { useEffect, useId, useState } from "react";
import { ChevronDown } from "lucide-react";
import {
	Dialog,
	DialogButton,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { DropdownMenu } from "@/components/ui/dropdown-menu";
import { Textarea } from "@/components/ui/textarea";
import { getApiErrorMessage } from "@/lib/api/errors";
import * as langfuseApi from "@/lib/api/resources/langfuse";

const PRODUCTION = "production";

interface LangfusePublishDialogProps {
	agentId: string;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	messagePlaceholder: string;
	onPublished: (
		version: langfuseApi.LangfusePromptVersion,
		label: string,
	) => void;
}

export default function LangfusePublishDialog({
	agentId,
	open,
	onOpenChange,
	messagePlaceholder,
	onPublished,
}: LangfusePublishDialogProps) {
	const labelId = useId();
	const [labels, setLabels] = useState<string[] | null>(null);
	const [commitMessage, setCommitMessage] = useState("");
	const [label, setLabel] = useState(PRODUCTION);
	const [configJson, setConfigJson] = useState("");
	const [isPublishing, setIsPublishing] = useState(false);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		if (!open) return;
		setLabels(null);
		setError(null);
		setCommitMessage("");
		setLabel(PRODUCTION);
		setConfigJson("");
		let stale = false;
		void langfuseApi
			.getLangfusePublishDraft(agentId)
			.then((draft) => {
				if (stale) return;
				setLabels(draft.labels);
				setConfigJson(draft.configJson);
			})
			.catch((err: unknown) => {
				if (stale) return;
				setError(getApiErrorMessage(err, "Failed to reach Langfuse"));
			});
		return () => {
			stale = true;
		};
	}, [agentId, open]);

	const publish = async () => {
		setIsPublishing(true);
		setError(null);
		try {
			const version = await langfuseApi.publishLangfusePrompt(agentId, {
				commitMessage: commitMessage.trim() || null,
				label,
				configJson,
			});
			onPublished(version, label);
			onOpenChange(false);
		} catch (err) {
			setError(getApiErrorMessage(err, "Failed to publish to Langfuse"));
		} finally {
			setIsPublishing(false);
		}
	};

	const fieldLabel = "text-[12.5px] font-semibold text-foreground";
	const control =
		"w-full rounded-lg border border-input bg-card px-3 py-[7px] text-[13px] outline-none transition-[border-color,box-shadow] placeholder:text-meta focus:border-petrol focus:shadow-[0_0_0_3px_rgba(22,96,110,0.10)] dark:placeholder:text-panel-dim";

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="sm:max-w-[640px]">
				<DialogHeader>
					<DialogTitle>Publish to Langfuse</DialogTitle>
					<DialogDescription>
						Review the label and public config before publishing the saved
						instructions as a new prompt version.
					</DialogDescription>
				</DialogHeader>
				{error && (
					<div className="rounded-md bg-destructive/10 px-4 py-2.5 text-[13px] text-destructive">
						{error}
					</div>
				)}
				<label className="flex flex-col gap-1.5">
					<span className={fieldLabel}>Commit message</span>
					<input
						type="text"
						value={commitMessage}
						onChange={(event) => {
							setCommitMessage(event.target.value);
						}}
						placeholder={messagePlaceholder}
						className={control}
					/>
				</label>
				<div className="flex flex-col gap-1.5">
					<span id={labelId} className={fieldLabel}>
						Label
					</span>
					<DropdownMenu
						align="start"
						className="w-[var(--radix-dropdown-menu-trigger-width)]"
						trigger={
							<button
								type="button"
								aria-labelledby={labelId}
								disabled={!labels}
								className={`${control} flex cursor-pointer items-center gap-2 text-left disabled:cursor-not-allowed disabled:opacity-50`}
							>
								<span className="flex-1">{label}</span>
								<ChevronDown className="size-3.5 shrink-0 text-meta" />
							</button>
						}
						items={(labels ?? [PRODUCTION]).map((item) => ({
							label: item,
							active: item === label,
							onClick: () => {
								setLabel(item);
							},
						}))}
					/>
				</div>
				<label className="flex flex-col gap-1.5">
					<span className={fieldLabel}>Public config</span>
					<Textarea
						value={configJson}
						disabled={!labels}
						spellCheck={false}
						onChange={(event) => {
							setConfigJson(event.target.value);
						}}
						className={`${control} max-h-72 min-h-40 overflow-auto font-mono text-[12px] md:text-[12px]`}
					/>
				</label>
				<p className="text-[12px] leading-relaxed text-muted-foreground">
					This config is visible to every user with access to the Langfuse
					project. Do not include credentials, tokens, or secrets. URLs with
					credentials, query parameters, or fragments are rejected.
				</p>
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
						disabled={!labels || isPublishing}
						onClick={() => {
							void publish();
						}}
					>
						{isPublishing ? "Publishing…" : "Publish"}
					</DialogButton>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
