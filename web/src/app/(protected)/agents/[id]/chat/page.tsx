"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
	type PromptInputMessage,
	usePromptInputController,
} from "@/components/ai-elements/prompt-input";
import ChatPromptInput from "./components/prompt-input";
import { SelectAgentDialog } from "./components/select-agent-dialog";
import { useThreadsStore } from "@/stores/threads-store";
import { useActiveRunsStore } from "@/stores/active-runs-store";
import { useModelsStore } from "@/stores/models-store";
import { usePendingMessageStore } from "@/stores/pending-message-store";
import * as agentsApi from "@/lib/api/resources/agents";
import * as threadsApi from "@/lib/api/resources/threads";
import { generateUuid } from "@/lib/utils/uuid";
import { ChevronDown, Loader2 } from "lucide-react";
import { Agent } from "@/types/agents";
import { AgentAvatar } from "@/components/ui/agent-avatar";
import { getDefaultModel } from "@/lib/utils/get-default-model";
import { useAgentReadiness } from "@/hooks/use-agent-readiness";
import type { ThreadResourceSettings } from "@/types/threads";
import { toast } from "sonner";
import { getApiErrorMessage } from "@/lib/api/errors";

const EMPTY_RESOURCE_SETTINGS: ThreadResourceSettings = {
	disabledMcpServerIds: [],
	disabledSkillIds: [],
	disabledSandboxIds: [],
	disabledSubagentIds: [],
};

const StarterChatPage = () => {
	const params = useParams();
	const router = useRouter();
	const agentId = params.id as string;
	const [isCreating, setIsCreating] = useState(false);
	const { modelSelection, starterAgent } = usePromptInputController();
	const setStarterAgent = starterAgent.set;
	const selectedModel = modelSelection.value;
	const setSelectedModel = modelSelection.setModel;
	// Reasoning-effort choice for the selected model; null = the model's
	// default. Pinned onto the thread at creation, like the model.
	const [reasoningEffort, setReasoningEffort] = useState<string | null>(null);
	const [resourceSettingsState, setResourceSettingsState] = useState<{
		agentId: string | null;
		settings: ThreadResourceSettings;
	}>({ agentId: null, settings: EMPTY_RESOURCE_SETTINGS });
	const resourceSettings =
		resourceSettingsState.agentId === agentId
			? resourceSettingsState.settings
			: EMPTY_RESOURCE_SETTINGS;
	const addThread = useThreadsStore((state) => state.addThread);
	const models = useModelsStore((state) => state.models);
	const fetchModels = useModelsStore((state) => state.fetchModels);
	const [agent, setAgent] = useState<Agent | null>(null);
	const [loadedAgentId, setLoadedAgentId] = useState<string | null>(null);
	const [isAgentDialogOpen, setIsAgentDialogOpen] = useState(false);
	const agentRequestIdRef = useRef(0);
	const defaultsAppliedAgentIdRef = useRef<string | null>(null);
	const currentAgent = loadedAgentId === agentId ? agent : null;
	const {
		ready: agentReady,
		acceptsFiles,
		status,
		detail: statusDetail,
		disconnectedMcpServers,
		refetch: refetchReady,
	} = useAgentReadiness(agentId, resourceSettings);

	const handleSubmit = async (message: PromptInputMessage) => {
		if (!message) return;

		const hasText = "text" in message && message.text?.trim();
		const hasFiles =
			"files" in message && message.files && message.files.length > 0;

		if (!hasText && !hasFiles) {
			return;
		}

		const modelId = selectedModel ?? getDefaultModel(models);
		if (!modelId) {
			console.error("No model available to create thread");
			return;
		}

		setIsCreating(true);
		const submittedAgentId = agentId;
		const submittedAgent = currentAgent;
		const submittedAgentRequestId = agentRequestIdRef.current;
		const submittedResourceSettings =
			resourceSettingsState.agentId === submittedAgentId
				? resourceSettingsState.settings
				: null;
		const threadId = generateUuid();

		try {
			const includeImages =
				models.find((model) => model.id === modelId)?.multimodal !== false;
			const created = await threadsApi.startThread(
				{
					id: threadId,
					agentId: submittedAgentId,
					modelId,
					reasoningEffort,
					...(submittedResourceSettings ?? {}),
				},
				message,
				includeImages,
				acceptsFiles === true,
			);
			if (agentRequestIdRef.current !== submittedAgentRequestId) {
				setIsCreating(false);
				const error = new Error("Conversation creation was superseded");
				error.name = "AbortError";
				throw error;
			}

			const thread = {
				...created,
				agentName: submittedAgent?.name ?? null,
				agentEmoji: submittedAgent?.emoji ?? null,
				agentColor: submittedAgent?.color ?? null,
				agentImageRevision: submittedAgent?.imageRevision ?? null,
			};

			addThread(thread);
			usePendingMessageStore
				.getState()
				.setOptimisticMessage(threadId, message);
			useActiveRunsStore.getState().markThreadRunning(threadId);

			router.push(`/agents/${submittedAgentId}/chat/${threadId}`);
		} catch (error) {
			setIsCreating(false);
			const aborted = error instanceof Error && error.name === "AbortError";
			if (!aborted) {
				console.error("Error creating thread:", error);
				toast.error(
					getApiErrorMessage(
						error,
						"Could not start the conversation. Try again.",
					),
				);
			}
			throw error;
		}
	};

	useEffect(() => {
		if (models.length === 0) {
			fetchModels().catch((error) => {
				console.error("Error fetching models:", error);
			});
		}
	}, [fetchModels, models.length]);

	useEffect(() => {
		if (
			currentAgent === null ||
			models.length === 0 ||
			defaultsAppliedAgentIdRef.current === agentId
		) {
			return;
		}
		const configuredModel = currentAgent.defaultModelId
			? models.find((model) => model.id === currentAgent.defaultModelId)
			: undefined;
		const modelId = configuredModel?.id ?? getDefaultModel(models);
		if (!modelId) return;

		defaultsAppliedAgentIdRef.current = agentId;
		let cancelled = false;
		queueMicrotask(() => {
			if (cancelled) return;
			setSelectedModel(modelId);
			setReasoningEffort(
				configuredModel &&
					currentAgent.defaultReasoningEffort &&
					configuredModel.reasoningEffortLevels.includes(
						currentAgent.defaultReasoningEffort,
					)
					? currentAgent.defaultReasoningEffort
					: null,
			);
		});
		return () => {
			cancelled = true;
		};
	}, [agentId, currentAgent, models, setSelectedModel]);

	useEffect(() => {
		const requestId = ++agentRequestIdRef.current;
		const fetchAgent = async () => {
			try {
				const [fetchedAgent, resources] = await Promise.all([
					agentsApi.getAgent(agentId),
					agentsApi.getAgentResources(agentId),
				]);
				if (requestId !== agentRequestIdRef.current) return;
				setAgent(fetchedAgent);
				setLoadedAgentId(agentId);
				setResourceSettingsState((current) =>
					current.agentId === agentId
						? current
						: {
								agentId,
								settings: {
									...EMPTY_RESOURCE_SETTINGS,
									disabledMcpServerIds: resources.mcpServers
										.filter((server) => !server.enabledByDefault)
										.map((server) => server.id),
									disabledSkillIds: resources.skills
										.filter((skill) => skill.enabledByDefault === false)
										.map((skill) => skill.id),
									disabledSandboxIds: resources.sandboxes
										.filter((sandbox) => !sandbox.enabledByDefault)
										.map((sandbox) => sandbox.id),
									disabledSubagentIds: resources.subagents
										.filter((subagent) => subagent.enabledByDefault === false)
										.map((subagent) => subagent.id),
								},
							},
				);
				setStarterAgent({
					name: fetchedAgent.name,
					emoji: fetchedAgent.emoji ?? null,
				});
			} catch (error) {
				if (requestId === agentRequestIdRef.current) {
					console.error("Error fetching agent:", error);
				}
			}
		};
		void fetchAgent();
		return () => {
			agentRequestIdRef.current += 1;
		};
	}, [agentId, setStarterAgent]);

	return (
		<div className="container mx-auto h-full flex flex-col items-center justify-center max-w-4xl px-6">
			<div className="w-full max-w-3xl space-y-8">
				<div className="text-center space-y-4">
					{currentAgent ? (
						<button
							onClick={() => {
								setIsAgentDialogOpen(true);
							}}
							className="mx-auto flex cursor-pointer items-center justify-center gap-2 transition-opacity hover:opacity-80"
						>
							<AgentAvatar
								agentId={currentAgent.id}
								name={currentAgent.name}
								imageRevision={currentAgent.imageRevision}
								color={currentAgent.color}
								emoji={currentAgent.emoji}
								size="lg"
							/>
							<h1 className="text-4xl font-bold">{currentAgent.name}</h1>
							<ChevronDown className="ml-8 mt-1 size-5 text-muted-foreground" />
						</button>
					) : (
						<div
							className="mx-auto flex h-[52px] items-center justify-center"
							role="status"
							aria-label="Loading agent"
						>
							<Loader2
								className="size-7 animate-spin text-petrol"
								aria-hidden="true"
							/>
						</div>
					)}
					{status !== "sandbox_unavailable" && (
						<p className="text-lg text-muted-foreground">
							Ask me anything to begin
						</p>
					)}
				</div>

				<div className="w-full">
					{status === "sandbox_unavailable" ? (
						<div className="flex items-center gap-3 rounded-lg border border-border bg-muted/50 px-4 py-3">
							<p className="flex-1 text-sm text-muted-foreground">
								{statusDetail ?? "This agent's sandbox is not available right now."}{" "}
								Try again in a moment, or ask a workspace admin.
							</p>
							<button
								type="button"
								className="shrink-0 cursor-pointer rounded-[7px] border border-input bg-card px-3 py-1.5 text-[12.5px] font-semibold text-foreground transition-colors hover:border-border-hover"
								onClick={() => {
									refetchReady();
								}}
							>
								Check again
							</button>
						</div>
					) : (
						<ChatPromptInput
							agentId={agentId}
							draftKey={`new:${agentId}`}
							onSubmit={handleSubmit}
							status={isCreating ? "streaming" : "ready"}
							className="w-full"
							selectedModel={selectedModel}
							onModelChange={(modelId) => {
								setSelectedModel(modelId);
								// Levels differ per model — a carried-over choice could be
								// one the new model rejects.
								setReasoningEffort(null);
							}}
							selectedEffort={reasoningEffort}
							onEffortChange={setReasoningEffort}
							agentReady={agentReady}
							acceptsFiles={acceptsFiles}
							disconnectedServers={disconnectedMcpServers}
							onAllConnected={() => {
								refetchReady();
							}}
							resourceSettings={resourceSettings}
							onResourceSettingsChange={(settings) => {
								setResourceSettingsState({ agentId, settings });
							}}
						/>
					)}
				</div>

				<SelectAgentDialog
					open={isAgentDialogOpen}
					onOpenChange={setIsAgentDialogOpen}
					onAgentSelect={(a) => {
						setStarterAgent({ name: a.name, emoji: a.emoji ?? null });
					}}
				/>
			</div>
		</div>
	);
};

export default StarterChatPage;
