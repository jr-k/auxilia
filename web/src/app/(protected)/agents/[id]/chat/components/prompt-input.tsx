"use client";

import { cn } from "@/lib/utils";
import { ModelSelectorLogo } from "@/components/ai-elements/model-selector";
import { handleKeyboardListNavigation } from "@/lib/keyboard-list-navigation";
import {
	PromptInput,
	PromptInputAddAttachmentButton,
	PromptInputAttachment,
	PromptInputAttachments,
	PromptInputBody,
	PromptInputButton,
	PromptInputFooter,
	type PromptInputMessage,
	PromptInputTextarea,
	PromptInputTools,
	usePromptInputController,
} from "@/components/ai-elements/prompt-input";
import type { BaseMessage } from "@langchain/core/messages";
import {
	isAIMessage,
	isHumanMessage,
	isToolMessage,
} from "@langchain/core/messages";
import {
	BrainIcon,
	ChartNoAxesColumnIncreasingIcon,
	CheckIcon,
	Loader2,
	PlugIcon,
	WrenchIcon,
	XIcon,
} from "lucide-react";
import { useRef, useState, useEffect, useMemo } from "react";
import { toast } from "sonner";
import { DropdownMenu } from "@/components/ui/dropdown-menu";
import { useModelsStore } from "@/stores/models-store";
import { useChatHeaderStore } from "@/stores/chat-header-store";
import { Model } from "@/types/models";
import { MCPServer } from "@/types/mcp-servers";
import { ConnectServersDialog } from "./connect-servers-dialog";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import { SearchBar } from "@/components/ui/search-bar";
import { getApiErrorMessage, toApiError } from "@/lib/api/errors";
import * as agentsApi from "@/lib/api/resources/agents";
import {
	canConfigureAgent,
	type ToolDiscoveryMode,
} from "@/types/agents";
import type { QueuedPrompt } from "@/types/runs";
import type { ThreadResourceSettings } from "@/types/threads";
import { PromptQueue } from "./prompt-queue";

// Petrol Mono composer pills: 34px tall, 999px radius, on the hover tint.
const composerPillClass = cn(
	"h-[34px] px-3 gap-2 rounded-full",
	"text-[13px] font-medium text-foreground",
	"bg-hover dark:bg-white/5",
	"hover:bg-petrol-tint dark:hover:bg-white/10",
	"data-[state=open]:bg-petrol-tint dark:data-[state=open]:bg-white/10",
	"disabled:opacity-60 disabled:cursor-not-allowed",
	"transition-colors",
);

const STATS_LOADER_MIN_MS = 400;
const TOOL_DISCOVERY_LABELS: Record<ToolDiscoveryMode, string> = {
	disabled: "Eager",
	automatic: "Automatic",
	local: "Auxilia Search",
};

interface ChatPromptInputProps {
	agentId: string;
	onSubmit: (message: PromptInputMessage) => void | Promise<void>;
	status: "submitted" | "streaming" | "ready" | "error";
	queueMode?: boolean;
	className?: string;
	stop?: () => void;
	onModelChange?: (modelId: string) => void | Promise<void>;
	selectedModel?: string;
	readOnlyModel?: boolean;
	modelChangeDisabled?: boolean;
	readOnlyEffort?: boolean;
	// Reasoning-effort choice for the selected model; null = the model's default.
	selectedEffort?: string | null;
	onEffortChange?: (effort: string | null) => void;
	agentReady?: boolean | null;
	disconnectedServers?: MCPServer[];
	onAllConnected?: () => void;
	resourceSettings: ThreadResourceSettings;
	onResourceSettingsChange: (settings: ThreadResourceSettings) => void;
	resourceSettingsSaving?: boolean;
	queuedPrompts?: QueuedPrompt[];
	onEnqueue?: (message: PromptInputMessage) => Promise<void>;
	onUpdateQueued?: (id: string, text: string) => Promise<void>;
	onBeginQueuedEdit?: (id: string) => Promise<void>;
	onEndQueuedEdit?: (id: string) => Promise<void>;
	onSendQueuedNow?: (id: string) => Promise<void>;
	sendQueuedNowDisabled?: boolean;
	onRemoveQueued?: (id: string) => Promise<void>;
	onReorderQueued?: (orderedIds: string[]) => Promise<void>;
	queueLoading?: boolean;
	onQueueAuthorizationRequired?: () => void;
	submissionDisabled?: boolean;
	conversationMessages?: BaseMessage[];
	loadLatestConversationMessages?: () => Promise<BaseMessage[]>;
}

// Human labels for the canonical effort ladder ("none" reads as Off — it
// turns the model's thinking off entirely).
const EFFORT_LABELS = new Map<string, string>([
	["none", "Off"],
	["minimal", "Minimal"],
	["low", "Low"],
	["medium", "Medium"],
	["high", "High"],
	["xhigh", "Extra high"],
	["max", "Max"],
]);

const effortLabel = (effort: string) => EFFORT_LABELS.get(effort) ?? effort;

const safeHttpUrl = (value: unknown): string | null => {
	if (typeof value !== "string") return null;
	try {
		const url = new URL(value);
		return url.protocol === "http:" || url.protocol === "https:"
			? url.toString()
			: null;
	} catch {
		return null;
	}
};

const ChatPromptInput = ({
	agentId,
	onSubmit,
	status,
	queueMode = false,
	className,
	stop,
	onModelChange,
	selectedModel: externalSelectedModel,
	readOnlyModel = false,
	modelChangeDisabled = false,
	readOnlyEffort = readOnlyModel,
	selectedEffort = null,
	onEffortChange,
	agentReady,
	disconnectedServers = [],
	onAllConnected,
	resourceSettings,
	onResourceSettingsChange,
	resourceSettingsSaving = false,
	queuedPrompts = [],
	onEnqueue,
	onUpdateQueued,
	onBeginQueuedEdit,
	onEndQueuedEdit,
	onSendQueuedNow,
	sendQueuedNowDisabled = false,
	onRemoveQueued,
	onReorderQueued,
	queueLoading = false,
	onQueueAuthorizationRequired,
	submissionDisabled = false,
	conversationMessages,
	loadLatestConversationMessages,
}: ChatPromptInputProps) => {
	const [connectDialogOpen, setConnectDialogOpen] = useState(false);
	const models = useModelsStore((state) => state.models);
	const fetchModels = useModelsStore((state) => state.fetchModels);
	const agentName = useChatHeaderStore((state) => state.agentName);
	const [model, setModel] = useState<string | undefined>(undefined);
	const [modelSelectorOpen, setModelSelectorOpen] = useState(false);
	const [modelSearch, setModelSearch] = useState("");
	const [modelUpdatePending, setModelUpdatePending] = useState(false);
	const textareaRef = useRef<HTMLTextAreaElement>(null);
	const initialFocusPendingRef = useRef(true);
	const controller = usePromptInputController();
	const [editingId, setEditingId] = useState<string | null>(null);
	const [busyId, setBusyId] = useState<string | null>(null);
	const [statsDialogOpen, setStatsDialogOpen] = useState(false);
	const [statsLoading, setStatsLoading] = useState(false);
	const [statsMessages, setStatsMessages] = useState<BaseMessage[] | null>(null);
	const statsRequestRef = useRef(0);
	const [toolDiscoveryConfig, setToolDiscoveryConfig] = useState<{
		agentId: string;
		mode: ToolDiscoveryMode;
		canChange: boolean;
	} | null>(null);
	const [toolDiscoveryPending, setToolDiscoveryPending] = useState(false);
	// A direct `onSubmit` (the protocol stream's `submit`) must only happen
	// while the server has no run on the thread: it shows the message
	// optimistically, and if a run is active the server parks it in the
	// queue instead — the prompt then appears in the conversation *and* in
	// the queue. The `queueMode` prop lags a render or two behind the first
	// send, so this lock is held for the whole run (the stream resolves only
	// once the run ends). The stream must still carry the first prompt of
	// an idle thread: that is what attaches it to the thread's events.
	const directRunLockRef = useRef(false);
	const draftRef = useRef<string | null>(null);
	const restoreFrameRef = useRef<number | null>(null);
	const effectiveEditingId =
		editingId && queuedPrompts.some((item) => item.id === editingId)
			? editingId
			: null;
	const toolDiscoveryMode =
		toolDiscoveryConfig?.agentId === agentId
			? toolDiscoveryConfig.mode
			: null;
	const canChangeToolDiscovery =
		toolDiscoveryConfig?.agentId === agentId &&
		toolDiscoveryConfig.canChange;

	const currentModel = externalSelectedModel ?? model;
	const selectedModelData = models.find((m) => m.id === currentModel);
	const effortLevels = selectedModelData?.reasoningEffortLevels ?? [];
	const effortDefault = selectedModelData?.reasoningEffortDefault ?? null;
	// A stored effort the catalog no longer declares is clamped to the model
	// default at run time — don't display it as if it were in effect. When the
	// model itself is unknown (e.g. disabled, absent from the picker list) the
	// levels can't be checked, so trust the stored value.
	const validatedEffort =
		selectedEffort &&
		(selectedModelData === undefined || effortLevels.includes(selectedEffort))
			? selectedEffort
			: null;
	// Pill label: the explicit choice, else the model's declared default
	// level, else Auto (provider-managed/dynamic).
	const effortPillLabel = validatedEffort
		? effortLabel(validatedEffort)
		: effortDefault
			? effortLabel(effortDefault)
			: "Auto";
	// Text-only models can't take image attachments. Per model, not per chef:
	// e.g. GLM 5.3 Flash accepts images while plain GLM 5.3 does not. Unknown
	// model (not in the picker list, e.g. the current model was disabled) → allow,
	// matching the old lookup-miss behavior.
	const noAttachments =
		selectedModelData !== undefined && !selectedModelData.multimodal;
	const enabledDisconnectedServers = useMemo(() => {
		const disabledIds = new Set(resourceSettings.disabledMcpServerIds);
		return disconnectedServers.filter((server) => !disabledIds.has(server.id));
	}, [disconnectedServers, resourceSettings.disabledMcpServerIds]);
	const conversationStats = useMemo(() => {
		const messages = statsMessages ?? conversationMessages;
		if (!messages) return null;
		let userMessages = 0;
		let assistantMessages = 0;
		let modelCalls = 0;
		let toolCalls = 0;
		let inputTokens = 0;
		let outputTokens = 0;
		let totalTokens = 0;
		let cachedInputTokens = 0;
		let reasoningTokens = 0;
		let hasUsage = false;
		let hasToolResultSinceLastModelCall = false;
		const calls: {
			number: number;
			phase: "initial" | "follow-up" | "after-tools";
			inputTokens: number;
			outputTokens: number;
			totalTokens: number;
		}[] = [];

		for (const message of messages) {
			if (isHumanMessage(message) && message.name !== "host") {
				userMessages += 1;
				continue;
			}
			if (isToolMessage(message)) {
				hasToolResultSinceLastModelCall = true;
				continue;
			}
			if (!isAIMessage(message)) continue;
			modelCalls += 1;
			toolCalls += message.tool_calls?.length ?? 0;
			if (message.text.trim()) assistantMessages += 1;

			const usage = message.usage_metadata;
			if (!usage) {
				hasToolResultSinceLastModelCall = false;
				continue;
			}
			hasUsage = true;
			const input = usage.input_tokens ?? 0;
			const output = usage.output_tokens ?? 0;
			const total = usage.total_tokens ?? input + output;
			inputTokens += input;
			outputTokens += output;
			totalTokens += total;
			cachedInputTokens += usage.input_token_details?.cache_read ?? 0;
			reasoningTokens += usage.output_token_details?.reasoning ?? 0;
			calls.push({
				number: modelCalls,
				phase:
					calls.length === 0
						? "initial"
						: hasToolResultSinceLastModelCall
							? "after-tools"
							: "follow-up",
				inputTokens: input,
				outputTokens: output,
				totalTokens: total,
			});
			hasToolResultSinceLastModelCall = false;
		}

		const initialInputTokens = calls[0]?.inputTokens ?? 0;
		return {
			userMessages,
			assistantMessages,
			messageCount: userMessages + assistantMessages,
			modelCalls,
			toolCalls,
			inputTokens,
			outputTokens,
			totalTokens,
			cachedInputTokens,
			reasoningTokens,
			hasUsage,
			initialInputTokens,
			laterInputTokens: Math.max(0, inputTokens - initialInputTokens),
			afterToolInputTokens: calls
				.filter((call) => call.phase === "after-tools")
				.reduce((sum, call) => sum + call.inputTokens, 0),
			calls,
		};
	}, [conversationMessages, statsMessages]);

	const handleStatsDialogOpenChange = (open: boolean) => {
		setStatsDialogOpen(open);
		const request = ++statsRequestRef.current;
		if (!open || !loadLatestConversationMessages) return;

		setStatsLoading(true);
		void Promise.all([
			loadLatestConversationMessages(),
			new Promise<void>((resolve) => {
				window.setTimeout(resolve, STATS_LOADER_MIN_MS);
			}),
		])
			.then(([messages]) => {
				if (statsRequestRef.current === request) {
					setStatsMessages(messages);
				}
			})
			.catch((error: unknown) => {
				if (statsRequestRef.current === request) {
					toast.error(
						getApiErrorMessage(error, "Conversation stats could not be loaded."),
					);
				}
			})
			.finally(() => {
				if (statsRequestRef.current === request) {
					setStatsLoading(false);
				}
			});
	};

	// Editable composer only: normalize a stale selection in the parent state
	// too (not just the display), so what's shown as Default/Auto is also what
	// gets submitted. Read-only threads keep their pinned value — the backend
	// clamps it at run time.
	useEffect(() => {
		if (
			!readOnlyEffort &&
			selectedEffort &&
			selectedModelData !== undefined &&
			!selectedModelData.reasoningEffortLevels.includes(selectedEffort)
		) {
			onEffortChange?.(null);
		}
	}, [readOnlyEffort, selectedEffort, selectedModelData, onEffortChange]);

	useEffect(() => {
		let cancelled = false;
		void agentsApi
			.getAgent(agentId)
			.then((agent) => {
				if (cancelled) return;
				setToolDiscoveryConfig({
					agentId,
					mode: agent.toolDiscoveryMode ?? "disabled",
					canChange: canConfigureAgent(agent.currentUserPermission),
				});
			})
			.catch(() => {
				// The composer remains usable if this optional control cannot load.
			});
		return () => {
			cancelled = true;
		};
	}, [agentId]);

	const handleToolDiscoveryChange = async (mode: ToolDiscoveryMode) => {
		if (mode === toolDiscoveryMode || !canChangeToolDiscovery) return;
		setToolDiscoveryPending(true);
		try {
			const agent = await agentsApi.patchAgent(agentId, {
				toolDiscoveryMode: mode,
			});
			const savedMode = agent.toolDiscoveryMode ?? mode;
			setToolDiscoveryConfig({
				agentId,
				mode: savedMode,
				canChange: canConfigureAgent(agent.currentUserPermission),
			});
			toast.success(
				`Tool discovery set to ${TOOL_DISCOVERY_LABELS[savedMode]} for the next message.`,
			);
		} catch (error) {
			toast.error(
				getApiErrorMessage(error, "Tool discovery could not be changed."),
			);
		} finally {
			setToolDiscoveryPending(false);
		}
	};

	const handleModelChange = async (modelId: string) => {
		if (modelChangeDisabled) return;
		if (modelId === currentModel) {
			handleModelSelectorOpenChange(false);
			return;
		}
		setModelUpdatePending(true);
		try {
			await onModelChange?.(modelId);
			setModel(modelId);
			handleModelSelectorOpenChange(false);
		} catch (error) {
			toast.error(
				getApiErrorMessage(error, "The conversation model could not be changed."),
			);
		} finally {
			setModelUpdatePending(false);
		}
	};

	const groupedModels = useMemo(() => {
		const q = modelSearch.trim().toLowerCase();
		const filtered = q
			? models.filter(
					(m) =>
						m.name.toLowerCase().includes(q) ||
						m.chef.toLowerCase().includes(q),
				)
			: models;
		return filtered.reduce(
			(acc, model) => {
				acc[model.chef] = acc[model.chef] || [];
				acc[model.chef].push(model);
				return acc;
			},
			{} as Record<string, Model[]>,
		);
	}, [models, modelSearch]);

	const hasModelResults = Object.keys(groupedModels).length > 0;

	const handleModelSelectorOpenChange = (open: boolean) => {
		setModelSelectorOpen(open);
		if (!open) setModelSearch("");
	};

	useEffect(
		() => () => {
			if (restoreFrameRef.current !== null) {
				cancelAnimationFrame(restoreFrameRef.current);
			}
		},
		[],
	);

	useEffect(() => {
		if (!initialFocusPendingRef.current || queueLoading) {
			return;
		}

		const frame = requestAnimationFrame(() => {
			textareaRef.current?.focus({ preventScroll: true });
			initialFocusPendingRef.current = false;
		});
		return () => {
			cancelAnimationFrame(frame);
		};
	}, [queueLoading]);

	const submitMessage = async (message: PromptInputMessage) => {
		const hasText = Boolean("text" in message && message.text);
		const hasAttachments = Boolean("files" in message && message.files?.length);

		if (effectiveEditingId) {
			if (!hasText || hasAttachments || !onUpdateQueued) return;
			setBusyId(effectiveEditingId);
			try {
				await onUpdateQueued(effectiveEditingId, message.text?.trim() ?? "");
				setEditingId(null);
				const draft = draftRef.current;
				draftRef.current = null;
				restoreFrameRef.current = requestAnimationFrame(() => {
					controller.textInput.setInput(draft ?? "");
					restoreFrameRef.current = null;
				});
			} catch (error) {
				toast.error(
					getApiErrorMessage(
						error,
						"The queued prompt could not be updated.",
					),
				);
				throw error;
			} finally {
				setBusyId(null);
			}
			return;
		}
		if (queueMode || directRunLockRef.current) {
			if (!(hasText || hasAttachments) || !onEnqueue) return;
			try {
				await onEnqueue(message);
			} catch (error) {
				const apiError = toApiError(error);
				if (apiError.status === 401) {
					onQueueAuthorizationRequired?.();
					const body =
						apiError.body && typeof apiError.body === "object"
							? (apiError.body as Record<string, unknown>)
							: null;
					const authUrl = safeHttpUrl(body?.auth_url);
					if (authUrl) {
						toast.error(
							"Reconnect the agent's MCP server before queueing this prompt.",
							{
								action: {
									label: "Connect",
									onClick: () => {
										window.open(
											authUrl,
											"_blank",
											"width=600,height=700",
										);
									},
								},
							},
						);
						throw error;
					}
					setConnectDialogOpen(true);
				}
				toast.error(
					getApiErrorMessage(
						error,
						"The prompt could not be added to the queue.",
					),
				);
				throw error;
			}
			return;
		}
		directRunLockRef.current = true;
		try {
			await onSubmit(message);
		} finally {
			directRunLockRef.current = false;
		}
	};

	const handleSubmit = (message: PromptInputMessage) => {
		if (!message || queueLoading || submissionDisabled || modelUpdatePending) return;
		const hasText = Boolean("text" in message && message.text);
		const hasAttachments = Boolean("files" in message && message.files?.length);
		if (!(hasText || hasAttachments)) return;

		const awaitSubmission =
			effectiveEditingId !== null ||
			queueMode ||
			directRunLockRef.current;
		const submission = submitMessage(message);
		requestAnimationFrame(() => {
			textareaRef.current?.focus({ preventScroll: true });
		});
		if (awaitSubmission) return submission;
		void submission.catch(() => {});
	};

	const finishEditingLocally = () => {
		setEditingId(null);
		if (draftRef.current !== null) {
			controller.textInput.setInput(draftRef.current);
			draftRef.current = null;
		}
	};

	const beginEdit = (item: QueuedPrompt) => {
		if (controller.attachments.files.length > 0) {
			toast.error("Send or remove the current attachments before editing.");
			return;
		}
		setBusyId(item.id);
		void (async () => {
			try {
				await onBeginQueuedEdit?.(item.id);
				if (editingId === null) {
					draftRef.current = controller.textInput.value;
				}
				controller.textInput.setInput(item.text);
				setEditingId(item.id);
				requestAnimationFrame(() => {
					textareaRef.current?.focus();
				});
			} catch (error) {
				toast.error(
					getApiErrorMessage(error, "This queued prompt can no longer be edited."),
				);
			} finally {
				setBusyId(null);
			}
		})();
	};

	const cancelEdit = () => {
		if (!effectiveEditingId) return;
		const id = effectiveEditingId;
		setBusyId(id);
		void (async () => {
			try {
				await onEndQueuedEdit?.(id);
				finishEditingLocally();
			} catch (error) {
				toast.error(
					getApiErrorMessage(error, "The queued prompt edit could not be closed."),
				);
			} finally {
				setBusyId(null);
			}
		})();
	};

	useEffect(() => {
		if (!effectiveEditingId || !onBeginQueuedEdit) return;
		const timer = window.setInterval(() => {
			void onBeginQueuedEdit(effectiveEditingId).catch(() => {});
		}, 10_000);
		return () => {
			window.clearInterval(timer);
		};
	}, [effectiveEditingId, onBeginQueuedEdit]);

	useEffect(() => {
		if (
			editingId === null ||
			queuedPrompts.some((item) => item.id === editingId)
		) {
			return;
		}
		// The queue is an external server subscription; losing its item ends
		// the local editing session.
		const timeoutId = window.setTimeout(() => {
			setEditingId(null);
			controller.textInput.setInput(draftRef.current ?? "");
			draftRef.current = null;
			toast.info("That prompt has started, so it can no longer be edited.");
		}, 0);
		return () => {
			window.clearTimeout(timeoutId);
		};
	}, [controller.textInput, editingId, queuedPrompts]);

	const removeQueued = async (id: string) => {
		setBusyId(id);
		try {
			await onRemoveQueued?.(id);
			if (editingId === id) finishEditingLocally();
		} catch (error) {
			toast.error(
				getApiErrorMessage(error, "The queued prompt could not be removed."),
			);
		} finally {
			setBusyId(null);
		}
	};

	const sendQueuedNow = async (id: string) => {
		setBusyId(id);
		try {
			await onSendQueuedNow?.(id);
			if (editingId === id) finishEditingLocally();
		} catch (error) {
			toast.error(
				getApiErrorMessage(error, "The queued prompt could not be sent now."),
			);
		} finally {
			setBusyId(null);
		}
	};

	const reorderQueued = async (orderedIds: string[]) => {
		try {
			await onReorderQueued?.(orderedIds);
		} catch (error) {
			toast.error(
				getApiErrorMessage(error, "The prompt queue could not be reordered."),
			);
		}
	};

	useEffect(() => {
		// Only fetch if we don't have models yet
		if (models.length === 0) {
			fetchModels();
		}
	}, [fetchModels, models.length]);

	return (
		<>
			<div className={className}>
				<PromptQueue
					items={queuedPrompts}
					editingId={effectiveEditingId}
					busyId={busyId}
					onEdit={beginEdit}
					onSendNow={sendQueuedNow}
					sendNowDisabled={sendQueuedNowDisabled}
					onRemove={removeQueued}
					onReorder={reorderQueued}
				/>
				{effectiveEditingId && (
					<div className="mb-2 flex items-center gap-2 rounded-lg border border-sky-400/35 bg-sky-500/[0.07] px-3 py-2 text-[12px] font-medium text-sky-700 dark:text-sky-300">
						<span className="size-1.5 rounded-full bg-sky-500" />
						Editing queued prompt
						<span className="flex-1 text-sky-700/65 dark:text-sky-300/65">
							Submit to save
						</span>
						<button
							type="button"
							onClick={cancelEdit}
							className="flex size-6 cursor-pointer items-center justify-center rounded-md transition-colors hover:bg-sky-500/10"
							aria-label="Cancel queued prompt editing"
						>
							<XIcon className="size-3.5" />
						</button>
					</div>
				)}
				<PromptInput
					globalDrop
					multiple
					disableAttachments={
						noAttachments || effectiveEditingId !== null
					}
					attachmentsDisabledMessage={
						effectiveEditingId
							? "Attachments cannot be changed while editing a queued prompt"
							: undefined
					}
					onSubmit={handleSubmit}
					className={cn(
					"min-h-[116px] transition-all duration-200",
					// Petrol Mono composer (design kit 09): 16px radius, 2px #DCE4E4
					// border → petrol on focus, depth from the composer shadow.
					"[&>[data-slot=input-group]]:rounded-2xl",
					"[&>[data-slot=input-group]]:border-2",
					"[&>[data-slot=input-group]]:border-input",
					"[&>[data-slot=input-group]]:bg-card",
					"[&>[data-slot=input-group]]:shadow-composer",
					"[&>[data-slot=input-group]]:transition-colors",
					effectiveEditingId
						? "[&>[data-slot=input-group]]:border-sky-400/65 [&>[data-slot=input-group]:focus-within]:border-sky-500"
						: "[&>[data-slot=input-group]:focus-within]:border-petrol",
					// Remove default focus ring
					"[&>[data-slot=input-group]]:has-[[data-slot=input-group-control]:focus-visible]:ring-0",
				)}
				>
				<PromptInputAttachments className="w-full justify-start px-[18px] pt-4">
					{(attachment) => <PromptInputAttachment data={attachment} />}
				</PromptInputAttachments>
				<PromptInputBody>
					<PromptInputTextarea
						ref={textareaRef}
						disabled={queueLoading}
						onKeyDown={(event) => {
							// Escape leaves edit mode without saving: the lease is
							// released and the pre-edit draft comes back.
							if (event.key !== "Escape" || !effectiveEditingId) return;
							event.preventDefault();
							cancelEdit();
						}}
						placeholder={agentName ? `Reply to ${agentName}…` : "Ask anything…"}
						className={cn(
							"text-[15px] font-medium leading-relaxed",
							"text-foreground",
							"placeholder:text-meta dark:placeholder:text-panel-dim",
							"px-[18px] pt-4 pb-2",
						)}
					/>
				</PromptInputBody>
				<PromptInputFooter className="px-3 pt-0 pb-3">
					<PromptInputTools className="gap-1.5">
						{noAttachments ? (
							<Tooltip>
								<TooltipTrigger asChild>
									<span>
										<PromptInputAddAttachmentButton
											disabled
											className={cn(composerPillClass, "w-[34px] px-0")}
										/>
									</span>
								</TooltipTrigger>
								<TooltipContent>
									This model does not support attachments.
								</TooltipContent>
							</Tooltip>
						) : (
							<PromptInputAddAttachmentButton
								disabled={
									effectiveEditingId !== null
								}
								className={cn(
									composerPillClass,
									"w-[34px] px-0 text-subtle dark:text-panel-body",
								)}
							/>
						)}
						{conversationStats && (
							<Dialog
								open={statsDialogOpen}
								onOpenChange={handleStatsDialogOpenChange}
							>
								<DialogTrigger asChild>
									<PromptInputButton
										aria-label="Conversation stats"
										title="Conversation stats"
										className={cn(
											composerPillClass,
											"w-[34px] cursor-pointer px-0 text-subtle dark:text-panel-body",
										)}
									>
										<ChartNoAxesColumnIncreasingIcon className="size-3.5" />
									</PromptInputButton>
								</DialogTrigger>
								<DialogContent className="max-h-[85vh] gap-0 overflow-y-auto sm:max-w-[600px]">
									<DialogTitle>Conversation stats</DialogTitle>
									<DialogDescription className="mt-1.5">
										Provider-reported usage from model responses stored in
										this thread. Internal routing calls are not included.
									</DialogDescription>

									{statsLoading ? (
										<div
											className="flex min-h-48 items-center justify-center gap-2 text-[13px] text-meta dark:text-panel-dim"
											aria-live="polite"
										>
											<Loader2 className="size-4 animate-spin" />
											Loading latest stats…
										</div>
									) : (
										<>
											<div className="mt-5 grid grid-cols-3 gap-2.5">
										<ConversationStat
											label="Total tokens"
											value={
												conversationStats.hasUsage
													? conversationStats.totalTokens
													: null
											}
											primary
										/>
										<ConversationStat
											label="Input tokens"
											value={
												conversationStats.hasUsage
													? conversationStats.inputTokens
													: null
											}
										/>
										<ConversationStat
											label="Output tokens"
											value={
												conversationStats.hasUsage
													? conversationStats.outputTokens
													: null
											}
										/>
									</div>

									{conversationStats.hasUsage && (
										<>
											<div className="mt-5">
												<h3 className="text-[12px] font-semibold text-foreground">
													Context loading
												</h3>
												<p className="mt-1 text-[11.5px] leading-[1.5] text-meta dark:text-panel-dim">
													Initial input is the first model request. Later input
													is the sum of every subsequent request, including
													context sent again.
												</p>
											</div>
											<div className="mt-3 grid grid-cols-3 gap-2.5">
												<ConversationStat
													label="Initial input"
													value={conversationStats.initialInputTokens}
												/>
												<ConversationStat
													label="Later input"
													value={conversationStats.laterInputTokens}
												/>
												<ConversationStat
													label="Input after tools"
													value={conversationStats.afterToolInputTokens}
												/>
											</div>

											<div className="mt-4 rounded-[8px] bg-hover px-3 py-2.5 text-[11.5px] leading-[1.55] text-meta dark:bg-white/5 dark:text-panel-dim">
												<span className="font-semibold text-body dark:text-panel-body">
													How tools are counted:
												</span>{" "}
												tool schemas are part of model input, tool-call arguments
												are model output, and tool results become model input on a
												later call. Tool execution itself does not use model
												tokens. Providers do not report an exact token breakdown
												by source.
											</div>

											<div className="mt-5">
												<h3 className="text-[12px] font-semibold text-foreground">
													Model input by call
												</h3>
												<p className="mt-1 text-[11.5px] leading-[1.5] text-meta dark:text-panel-dim">
													Each row is the full context sent for that call, not
													only the new tokens added since the previous call.
												</p>
											</div>
											<div className="mt-3 max-h-52 overflow-y-auto rounded-[10px] border border-border">
												{conversationStats.calls.map((call, index) => (
													<ConversationTokenCallRow
														key={call.number}
														call={call}
														last={index === conversationStats.calls.length - 1}
													/>
												))}
											</div>
										</>
									)}

									<div className="mt-5 overflow-hidden rounded-[10px] border border-border">
										<ConversationStatRow
											label="Messages"
											value={conversationStats.messageCount}
										/>
										<ConversationStatRow
											label="Your messages"
											value={conversationStats.userMessages}
										/>
										<ConversationStatRow
											label="Assistant messages"
											value={conversationStats.assistantMessages}
										/>
										<ConversationStatRow
											label="Model calls"
											value={conversationStats.modelCalls}
										/>
										<ConversationStatRow
											label="Tool calls"
											value={conversationStats.toolCalls}
											last={
												conversationStats.cachedInputTokens === 0 &&
												conversationStats.reasoningTokens === 0
											}
										/>
										{conversationStats.cachedInputTokens > 0 && (
											<ConversationStatRow
												label="Cached input tokens"
												value={conversationStats.cachedInputTokens}
												last={conversationStats.reasoningTokens === 0}
											/>
										)}
										{conversationStats.reasoningTokens > 0 && (
											<ConversationStatRow
												label="Reasoning tokens"
												value={conversationStats.reasoningTokens}
												last
											/>
										)}
									</div>

											{!conversationStats.hasUsage && (
												<p className="mt-4 rounded-[8px] bg-hover px-3 py-2.5 text-[12px] leading-[1.5] text-meta dark:bg-white/5 dark:text-panel-dim">
													Token usage is not available for the responses in this
													conversation.
												</p>
											)}
										</>
									)}
								</DialogContent>
							</Dialog>
						)}
						{toolDiscoveryMode && (
							<DropdownMenu
								align="start"
								side="top"
								className="w-[360px]"
								items={[
									{ sectionLabel: "Tool discovery" },
									{
										label: "Eager",
										description: "all schemas",
										active: toolDiscoveryMode === "disabled",
										onClick: () => {
											void handleToolDiscoveryChange("disabled");
										},
									},
									{
										label: "Automatic",
										description: "provider-native",
										active: toolDiscoveryMode === "automatic",
										onClick: () => {
											void handleToolDiscoveryChange("automatic");
										},
									},
									{
										label: "Auxilia Search",
										description: "adaptive",
										active: toolDiscoveryMode === "local",
										onClick: () => {
											void handleToolDiscoveryChange("local");
										},
									},
								]}
								trigger={
									<PromptInputButton
										disabled={
											toolDiscoveryPending || !canChangeToolDiscovery
										}
										aria-label={`Tool discovery: ${TOOL_DISCOVERY_LABELS[toolDiscoveryMode]}`}
										title={
											canChangeToolDiscovery
												? `Tool discovery: ${TOOL_DISCOVERY_LABELS[toolDiscoveryMode]}`
												: "Editor access is required to change tool discovery"
										}
										className={cn(
											composerPillClass,
											"w-[34px] cursor-pointer px-0 text-subtle dark:text-panel-body",
										)}
									>
										{toolDiscoveryPending ? (
											<Loader2 className="size-3.5 animate-spin" />
										) : (
											<WrenchIcon className="size-3.5" />
										)}
									</PromptInputButton>
								}
							/>
						)}
						{readOnlyModel ? (
							<PromptInputButton disabled className={composerPillClass}>
								{selectedModelData?.chefSlug && (
									<ModelSelectorLogo provider={selectedModelData.chefSlug} />
								)}
								{selectedModelData?.name && (
									<span className="truncate text-left">
										{selectedModelData.name}
									</span>
								)}
							</PromptInputButton>
						) : (
							<Dialog
								open={modelSelectorOpen}
								onOpenChange={handleModelSelectorOpenChange}
							>
								<DialogTrigger asChild>
									<PromptInputButton
										disabled={modelUpdatePending || modelChangeDisabled}
										className={cn(composerPillClass, "cursor-pointer")}
									>
										{selectedModelData ? (
											<>
												<ModelSelectorLogo
													provider={selectedModelData.chefSlug}
												/>
												<span className="truncate text-left">
													{selectedModelData.name}
												</span>
											</>
										) : (
											<span className="truncate text-left text-meta dark:text-panel-dim">
												Select model
											</span>
										)}
									</PromptInputButton>
								</DialogTrigger>
								<DialogContent
									className="gap-0 p-0"
									onKeyDown={handleKeyboardListNavigation}
								>
									<div className="px-6 pt-6 pb-4">
										<DialogTitle>Select a model</DialogTitle>
										<DialogDescription className="mt-1.5">
											Choose the model powering this chat
										</DialogDescription>
									</div>

									<div className="px-6 pb-3">
										<SearchBar
											placeholder="Search models..."
											value={modelSearch}
											onChange={setModelSearch}
										/>
									</div>

									<div
										role="listbox"
										className="px-4 pb-5 max-h-[55vh] overflow-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
									>
										{!hasModelResults ? (
											<div className="px-4 py-8 text-center text-[13px] text-meta dark:text-panel-dim">
												No models found.
											</div>
										) : (
											Object.entries(groupedModels).map(
												([chefName, chefModels]) => (
													<div key={chefName} className="px-2 pt-2">
														<div className="px-3 pb-1.5 text-[10px] font-semibold text-meta dark:text-panel-dim">
															{chefName}
														</div>
														<div className="flex flex-col gap-0.5">
															{chefModels.map((m) => {
																const isActive = currentModel === m.id;
																return (
																	<button
																		key={m.id}
																		type="button"
																		role="option"
																		data-keyboard-option="true"
																		aria-selected={isActive}
																		disabled={
																			modelUpdatePending || modelChangeDisabled
																		}
																		onClick={() => {
																			void handleModelChange(m.id);
																		}}
																		className={cn(
																			"flex w-full items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-colors text-left outline-none focus-visible:bg-hover focus-visible:ring-2 focus-visible:ring-petrol/35 dark:focus-visible:bg-white/5",
																			"text-[13.5px] font-medium text-foreground",
																			isActive
																				? "bg-petrol-tint dark:bg-white/10"
																				: "hover:bg-hover dark:hover:bg-white/5",
																		)}
																	>
																		<ModelSelectorLogo provider={m.chefSlug} />
																		<span className="flex-1 truncate">
																			{m.name}
																		</span>
																		{isActive && (
																			<CheckIcon
																				className="ml-auto size-4 shrink-0 text-petrol"
																				strokeWidth={3}
																			/>
																		)}
																	</button>
																);
															})}
														</div>
													</div>
												),
											)
										)}
									</div>
								</DialogContent>
							</Dialog>
						)}
						{readOnlyEffort
							? // Show a stored explicit effort while keeping it immutable.
								validatedEffort && (
									<PromptInputButton disabled className={composerPillClass}>
										<BrainIcon className="size-3.5" />
										<span className="truncate text-left">
											{effortLabel(validatedEffort)}
										</span>
									</PromptInputButton>
								)
							: effortLevels.length > 0 && (
									<DropdownMenu
										align="start"
										side="top"
										items={[
											{
												label: effortDefault
													? `Default (${effortLabel(effortDefault)})`
													: "Auto",
												active: !validatedEffort,
												onClick: () => {
													onEffortChange?.(null);
												},
											},
											...effortLevels.map((level) => ({
												label: effortLabel(level),
												active: validatedEffort === level,
												onClick: () => {
													onEffortChange?.(level);
												},
											})),
										]}
										trigger={
											<PromptInputButton
												className={cn(composerPillClass, "cursor-pointer")}
											>
												<BrainIcon className="size-3.5" />
												<span className="truncate text-left">
													{effortPillLabel}
												</span>
											</PromptInputButton>
										}
									/>
								)}
					</PromptInputTools>
					<div className="flex items-center gap-1.5">
						<ConnectButton
							allConnected={
								agentReady === true &&
								enabledDisconnectedServers.length === 0
							}
							onClick={() => {
								setConnectDialogOpen(true);
							}}
						/>
						{status === "streaming" && stop && <StopButton stop={stop} />}
						<SubmitButton
							disabled={
								queueLoading || submissionDisabled || modelUpdatePending
							}
						/>
					</div>
				</PromptInputFooter>
				</PromptInput>
			</div>
			<ConnectServersDialog
				open={connectDialogOpen}
				onOpenChange={setConnectDialogOpen}
				agentId={agentId}
				disconnectedServers={disconnectedServers}
				onConnectionChange={() => onAllConnected?.()}
				resourceSettings={resourceSettings}
				onResourceSettingsChange={onResourceSettingsChange}
				resourceSettingsSaving={resourceSettingsSaving}
			/>
		</>
	);
};

const formatStat = (value: number | null) =>
	value === null ? "N/A" : new Intl.NumberFormat("en-US").format(value);

const ConversationStat = ({
	label,
	value,
	primary = false,
}: {
	label: string;
	value: number | null;
	primary?: boolean;
}) => (
	<div
		className={cn(
			"rounded-[10px] border px-3 py-3",
			primary
				? "border-petrol/20 bg-petrol-tint dark:border-white/10 dark:bg-white/10"
				: "border-border bg-card",
		)}
	>
		<div
			className={cn(
				"font-mono text-[18px] font-semibold tracking-[-0.03em]",
				primary ? "text-petrol dark:text-panel-terminal" : "text-foreground",
			)}
		>
			{formatStat(value)}
		</div>
		<div className="mt-1 text-[10.5px] font-medium leading-tight text-meta dark:text-panel-dim">
			{label}
		</div>
	</div>
);

const ConversationStatRow = ({
	label,
	value,
	last = false,
}: {
	label: string;
	value: number;
	last?: boolean;
}) => (
	<div
		className={cn(
			"flex items-center justify-between px-3.5 py-2.5",
			!last && "border-b border-hairline dark:border-white/5",
		)}
	>
		<span className="text-[12.5px] font-medium text-body dark:text-panel-body">
			{label}
		</span>
		<span className="font-mono text-[12px] font-semibold text-foreground">
			{formatStat(value)}
		</span>
	</div>
);

const ConversationTokenCallRow = ({
	call,
	last = false,
}: {
	call: {
		number: number;
		phase: "initial" | "follow-up" | "after-tools";
		inputTokens: number;
		outputTokens: number;
		totalTokens: number;
	};
	last?: boolean;
}) => {
	const phaseLabel = {
		initial: "Initial load",
		"follow-up": "Follow-up",
		"after-tools": "After tool results",
	}[call.phase];

	return (
		<div
			className={cn(
				"flex items-center justify-between gap-4 px-3.5 py-2.5",
				!last && "border-b border-hairline dark:border-white/5",
			)}
		>
			<div className="min-w-0">
				<div className="text-[12.5px] font-medium text-body dark:text-panel-body">
					Call {call.number}
				</div>
				<div className="mt-0.5 text-[10.5px] text-meta dark:text-panel-dim">
					{phaseLabel}
				</div>
			</div>
			<div className="shrink-0 text-right">
				<div className="font-mono text-[12px] font-semibold text-foreground">
					{formatStat(call.inputTokens)} in
				</div>
				<div className="mt-0.5 font-mono text-[10.5px] text-meta dark:text-panel-dim">
					{formatStat(call.outputTokens)} out · {formatStat(call.totalTokens)} total
				</div>
			</div>
		</div>
	);
};

const SubmitButton = ({ disabled = false }: { disabled?: boolean }) => {
	const controller = usePromptInputController();
	const input = controller.textInput.value;
	const isDisabled = disabled || !input.trim();

	return (
		<button
			type="submit"
			disabled={isDisabled}
			className={cn(
				"flex size-[38px] items-center justify-center rounded-full transition-all",
				isDisabled
					? "cursor-not-allowed bg-hover text-ghost dark:bg-white/5 dark:text-panel-dim"
					: "cursor-pointer bg-petrol text-white shadow-submit hover:opacity-90",
			)}
		>
			<svg
				width="20"
				height="20"
				viewBox="0 0 20 20"
				fill="currentColor"
				xmlns="http://www.w3.org/2000/svg"
			>
				<path d="M8.99992 16V6.41407L5.70696 9.70704C5.31643 10.0976 4.68342 10.0976 4.29289 9.70704C3.90237 9.31652 3.90237 8.6835 4.29289 8.29298L9.29289 3.29298L9.36907 3.22462C9.76184 2.90427 10.3408 2.92686 10.707 3.29298L15.707 8.29298L15.7753 8.36915C16.0957 8.76192 16.0731 9.34092 15.707 9.70704C15.3408 10.0732 14.7618 10.0958 14.3691 9.7754L14.2929 9.70704L10.9999 6.41407V16C10.9999 16.5523 10.5522 17 9.99992 17C9.44764 17 8.99992 16.5523 8.99992 16Z" />
			</svg>
		</button>
	);
};

const StopButton = ({ stop }: { stop: () => void }) => (
	<button
		type="button"
		onClick={stop}
		aria-label="Stop current response"
		className="flex size-[38px] cursor-pointer items-center justify-center rounded-full border border-input bg-card text-subtle transition-colors hover:border-destructive/35 hover:bg-destructive/8 hover:text-destructive"
	>
		<svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
			<rect x="5" y="5" width="10" height="10" rx="2" />
		</svg>
	</button>
);

const ConnectButton = ({
	allConnected,
	onClick,
}: {
	allConnected: boolean;
	onClick: () => void;
}) => {
	return (
		<button
			type="button"
			onClick={onClick}
			aria-label={
				allConnected ? "View connected resources" : "Connect agent resources"
			}
			title={allConnected ? "View agent resources" : undefined}
			className={cn(
				"flex h-[38px] cursor-pointer items-center justify-center gap-2 rounded-full transition-all",
				"text-[14px] font-semibold",
				allConnected
					? "w-[38px] border border-input bg-card px-0 text-foreground hover:border-border-hover hover:bg-hover dark:hover:bg-white/5"
					: "bg-petrol px-4 text-white shadow-submit hover:opacity-90",
			)}
		>
			<PlugIcon size={16} />
			{!allConnected && <span>Connect</span>}
		</button>
	);
};

export default ChatPromptInput;
