"use client";

import {
	coerceMessageLikeToMessage,
	isAIMessage,
	isHumanMessage,
	isToolMessage,
	type BaseMessage,
	type BaseMessageLike,
} from "@langchain/core/messages";
import {
	Download,
	FileText,
	Globe2,
	ImageIcon,
	LockKeyhole,
	Wrench,
} from "lucide-react";
import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import {
	Conversation,
	ConversationContent,
} from "@/components/ai-elements/conversation";
import {
	Message,
	MessageContent,
	MessageResponse,
} from "@/components/ai-elements/message";
import {
	getAttachmentIds,
	getFileAttachments,
	getReasoning,
	pairToolCalls,
	type ToolCallView,
} from "@/lib/transcript";
import {
	getPublicArtifact,
	getPublicConversation,
	type PublicConversation,
	type PublicConversationArtifact,
} from "@/lib/api/resources/threads";

function formatBytes(size: number): string {
	if (size < 1024) return `${size} B`;
	if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
	return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function toolLabel(name: string): string {
	return name
		.replaceAll(/[-_]+/g, " ")
		.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function printable(value: unknown): string {
	if (typeof value === "string") return value;
	try {
		return JSON.stringify(value, null, 2);
	} catch {
		return String(value);
	}
}

function SharedFile({
	artifact,
	shareId,
	token,
}: {
	artifact: PublicConversationArtifact;
	shareId: string;
	token: string;
}) {
	const [imageUrl, setImageUrl] = useState<string | null>(null);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState(false);

	useEffect(() => {
		if (!artifact.mime_type.startsWith("image/")) return;
		let active = true;
		let objectUrl: string | null = null;
		void getPublicArtifact(shareId, artifact.id, token).then(
			async (blob) => {
				const typed = new Blob([await blob.arrayBuffer()], {
					type: artifact.mime_type,
				});
				objectUrl = URL.createObjectURL(typed);
				if (active) setImageUrl(objectUrl);
			},
			() => {
				if (active) setError(true);
			},
		);
		return () => {
			active = false;
			if (objectUrl) URL.revokeObjectURL(objectUrl);
		};
	}, [artifact.id, artifact.mime_type, shareId, token]);

	const download = async () => {
		setBusy(true);
		setError(false);
		try {
			const blob = await getPublicArtifact(shareId, artifact.id, token);
			const url = URL.createObjectURL(blob);
			const anchor = document.createElement("a");
			anchor.href = url;
			anchor.download = artifact.filename;
			anchor.click();
			setTimeout(() => {
				URL.revokeObjectURL(url);
			}, 0);
		} catch {
			setError(true);
		} finally {
			setBusy(false);
		}
	};

	return (
		<div className="w-full max-w-sm overflow-hidden rounded-[10px] border border-border bg-card">
			{imageUrl && (
				<Image
					unoptimized
					src={imageUrl}
					alt={artifact.title}
					className="max-h-72 w-full bg-hover object-contain"
					height={288}
					width={640}
				/>
			)}
			<div className="flex items-center gap-3 p-3">
				<span className="flex size-9 shrink-0 items-center justify-center rounded-[8px] bg-hover text-petrol">
					{artifact.mime_type.startsWith("image/") ? (
						<ImageIcon className="size-4" />
					) : (
						<FileText className="size-4" />
					)}
				</span>
				<div className="min-w-0 flex-1">
					<p className="truncate text-[12.5px] font-semibold text-foreground">
						{artifact.title}
					</p>
					<p className="text-[11px] text-meta">
						{formatBytes(artifact.size)}
						{error ? " · Unavailable" : ""}
					</p>
				</div>
				<button
					type="button"
					disabled={busy}
					onClick={() => {
						void download();
					}}
					className="flex size-8 cursor-pointer items-center justify-center rounded-[7px] border border-input text-subtle transition-colors hover:bg-hover hover:text-foreground disabled:opacity-50"
					aria-label={`Download ${artifact.filename}`}
				>
					<Download className="size-3.5" />
				</button>
			</div>
		</div>
	);
}

function ToolCall({ call }: { call: ToolCallView }) {
	const result = call.error ?? call.output;
	return (
		<details className="my-2 rounded-[9px] border border-border bg-hover/30">
			<summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-[12px] font-semibold text-subtle">
				<Wrench className="size-3.5" />
				{toolLabel(call.name)}
				<span className="ml-auto font-normal text-meta">
					{call.status === "error"
						? "Failed"
						: call.status === "running"
							? "Incomplete"
							: "Completed"}
				</span>
			</summary>
			<div className="space-y-2 border-t border-border p-3">
				{call.args && Object.keys(call.args).length > 0 && (
					<pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-[7px] bg-background p-2 font-mono text-[11px] text-subtle">
						{printable(call.args)}
					</pre>
				)}
				{result != null && (
					<pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-[7px] bg-background p-2 font-mono text-[11px] text-subtle">
						{printable(result)}
					</pre>
				)}
				{call.truncatedChars !== undefined && (
					<p className="text-[11px] text-meta">
						Showing a preview. The original result contains{" "}
						{call.truncatedChars.toLocaleString()} characters.
					</p>
				)}
			</div>
		</details>
	);
}

function PublicTranscript({
	conversation,
	shareId,
	token,
}: {
	conversation: PublicConversation;
	shareId: string;
	token: string;
}) {
	const messages = useMemo(
		() =>
			conversation.messages.map((message) =>
				coerceMessageLikeToMessage(message as BaseMessageLike),
			),
		[conversation.messages],
	);
	const toolCalls = useMemo(() => pairToolCalls(messages), [messages]);
	const toolsByMessage = useMemo(() => {
		const grouped = new Map<string, ToolCallView[]>();
		for (const call of toolCalls) {
			if (!call.messageId) continue;
			grouped.set(call.messageId, [
				...(grouped.get(call.messageId) ?? []),
				call,
			]);
		}
		return grouped;
	}, [toolCalls]);
	const artifactsById = useMemo(
		() => new Map(conversation.artifacts.map((item) => [item.id, item])),
		[conversation.artifacts],
	);
	const artifactsByToolCall = useMemo(() => {
		const grouped = new Map<string, PublicConversationArtifact[]>();
		for (const artifact of conversation.artifacts) {
			if (!artifact.tool_call_id) continue;
			grouped.set(artifact.tool_call_id, [
				...(grouped.get(artifact.tool_call_id) ?? []),
				artifact,
			]);
		}
		return grouped;
	}, [conversation.artifacts]);

	return messages.map((message: BaseMessage, index) => {
		if (isToolMessage(message)) return null;
		if (isHumanMessage(message)) {
			const inline = getFileAttachments(message);
			const displayText = message.additional_kwargs?.display_text;
			const text =
				typeof displayText === "string" ? displayText : message.text;
			const persistent = getAttachmentIds(message)
				.map((id) => artifactsById.get(id))
				.filter(
					(item): item is PublicConversationArtifact => item !== undefined,
				);
			const persistentFiles = new Set(
				persistent.map(
					(artifact) => `${artifact.filename}\0${artifact.mime_type}`,
				),
			);
			const visibleInline = inline.filter(
				(file) =>
					!persistentFiles.has(
						`${file.filename ?? ""}\0${file.mediaType}`,
					),
			);
			return (
				<Message key={message.id ?? index} from="user" className="py-3">
					<MessageContent>
						{text && <MessageResponse>{text}</MessageResponse>}
						{visibleInline.map((file) =>
							"url" in file && file.url ? (
								<a
									key={file.id}
									href={file.url}
									download={file.filename}
									className="mt-2 block text-[12px] font-medium text-primary underline"
								>
									{file.filename}
								</a>
							) : null,
						)}
						{persistent.map((artifact) => (
							<SharedFile
								key={artifact.id}
								artifact={artifact}
								shareId={shareId}
								token={token}
							/>
						))}
					</MessageContent>
				</Message>
			);
		}
		if (!isAIMessage(message)) return null;
		const reasoning = getReasoning(message);
		const calls = message.id ? (toolsByMessage.get(message.id) ?? []) : [];
		return (
			<div key={message.id ?? index} className="py-3">
				{reasoning && (
					<details className="mb-3 text-[12px] text-subtle">
						<summary className="cursor-pointer font-medium">Reasoning</summary>
						<div className="mt-2 whitespace-pre-wrap border-l border-border pl-3">
							{reasoning}
						</div>
					</details>
				)}
				{calls.map((call) => (
					<div key={call.id}>
						<ToolCall call={call} />
						{(artifactsByToolCall.get(call.callId ?? call.id) ?? []).map(
							(artifact) => (
								<SharedFile
									key={artifact.id}
									artifact={artifact}
									shareId={shareId}
									token={token}
								/>
							),
						)}
					</div>
				))}
				{message.text && (
					<Message from="assistant">
						<MessageContent>
							<MessageResponse>{message.text}</MessageResponse>
						</MessageContent>
					</Message>
				)}
			</div>
		);
	});
}

export function PublicConversationView({ shareId }: { shareId: string }) {
	const [state, setState] = useState<
		| { status: "loading" }
		| { status: "error" }
		| { status: "ready"; conversation: PublicConversation; token: string }
	>({ status: "loading" });

	useEffect(() => {
		const token = new URLSearchParams(window.location.hash.slice(1)).get(
			"token",
		);
		let active = true;
		const request = token
			? getPublicConversation(shareId, token)
			: Promise.reject(new Error("Missing share token"));
		void request.then(
			(conversation) => {
				if (active && token) {
					setState({ status: "ready", conversation, token });
				}
			},
			() => {
				if (active) setState({ status: "error" });
			},
		);
		return () => {
			active = false;
		};
	}, [shareId]);

	if (state.status === "loading") {
		return (
			<main className="flex min-h-dvh items-center justify-center bg-background">
				<div className="h-8 w-40 animate-pulse rounded-full bg-hover" />
			</main>
		);
	}
	if (state.status === "error") {
		return (
			<main className="flex min-h-dvh items-center justify-center bg-background p-6">
				<div className="max-w-sm text-center">
					<LockKeyhole className="mx-auto size-8 text-meta" />
					<h1 className="mt-4 text-[18px] font-semibold text-foreground">
						Conversation unavailable
					</h1>
					<p className="mt-2 text-[13px] leading-5 text-subtle">
						This link is invalid or the publication has been removed.
					</p>
				</div>
			</main>
		);
	}

	const { conversation, token } = state;
	return (
		<main className="flex h-dvh flex-col bg-background">
			<header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-4 md:px-6">
				<div className="flex min-w-0 items-center gap-2.5">
					<span
						className="flex size-8 shrink-0 items-center justify-center rounded-full text-sm"
						style={{ backgroundColor: conversation.agent.color ?? undefined }}
					>
						{conversation.agent.emoji ?? "A"}
					</span>
					<div className="min-w-0">
						<p className="truncate text-[13px] font-semibold text-foreground">
							{conversation.agent.name}
						</p>
						<p className="truncate text-[11px] text-meta">
							{conversation.title ?? "Shared conversation"}
						</p>
					</div>
				</div>
				<span className="flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-[11.5px] font-medium text-subtle">
					<Globe2 className="size-3.5" />
					Read-only snapshot
				</span>
			</header>
			<Conversation className="min-h-0 flex-1">
				<ConversationContent className="mx-auto w-full max-w-4xl px-3 pb-16 sm:px-6 lg:px-10">
					<PublicTranscript
						conversation={conversation}
						shareId={shareId}
						token={token}
					/>
				</ConversationContent>
			</Conversation>
		</main>
	);
}
