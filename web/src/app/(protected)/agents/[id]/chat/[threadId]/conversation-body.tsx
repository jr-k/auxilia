"use client";

import { Fragment, memo, useCallback, useMemo } from "react";
import Image from "next/image";
import type { BaseMessage } from "@langchain/core/messages";
import {
  isAIMessage,
  isHumanMessage,
  isToolMessage,
} from "@langchain/core/messages";
import type { AnyStream, SubagentDiscoverySnapshot } from "@langchain/react";
import type { Interrupt } from "@langchain/langgraph-sdk";
import {
  ChevronDownIcon,
  CopyIcon,
  ExternalLinkIcon,
  MessagesSquareIcon,
  RefreshCcwIcon,
} from "lucide-react";
import { SlackLogo } from "@/components/slack-logo";
import {
  Message,
  MessageAction,
  MessageActions,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message";
import {
  ChainOfThought,
  ChainReasoningStep,
  ChainThinking,
} from "@/components/ai-elements/chain-of-thought";
import {
  Error,
  ErrorContent,
  ErrorDetails,
} from "@/components/ai-elements/error";
import {
  Attachment,
  AttachmentHoverCard,
  AttachmentHoverCardContent,
  AttachmentHoverCardTrigger,
  AttachmentInfo,
  AttachmentPreview,
  Attachments,
  getAttachmentLabel,
  getMediaCategory,
} from "@/components/ai-elements/attachments";
import { TodoList } from "@/components/ai-elements/todo-list";
import type { Todo } from "@/components/ai-elements/todo-list";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useMcpServersStore } from "@/stores/mcp-servers-store";
import { useAgentsStore } from "@/stores/agents-store";
import type { HitlDecision, HitlResponse } from "@/hooks/use-hitl-approvals";
import { McpAppWidget } from "../components/mcp-app-widget";
import {
  type ChainStepData,
  type ToolCallView,
  type ToolStepState,
  getFileAttachments,
  getMcpAppInfo,
  getReasoning,
  getStructuredContent,
  getToolStepState,
  groupChains,
  sanitizeToolIdentifier,
  claimsInterrupt,
} from "@/lib/transcript";
import {
  presentSideChannelMessage,
  type SideChannelContextMessage,
} from "@/lib/transcript/side-channel-context";
import {
  SubAgentCard,
  SubAgentProgress,
  SynthesisIndicator,
} from "./subagent-card";
import { threadMapAnchor } from "./thread-map";
import { type DescribeTool, ToolStep, useDescribeTool } from "./tool-step";

export type ConversationBodyProps = {
  /** Throttled `stream.messages` (or the hydrated history when idle). */
  messages: BaseMessage[];
  /** `pairToolCalls(messages, stream.toolCalls)`, memoized by the page. */
  toolCalls: ToolCallView[];
  /** `stream.subagents` — discovery snapshots keyed by `task` tool-call id. */
  subagents: ReadonlyMap<string, SubagentDiscoverySnapshot>;
  /** Identity-stable stream handle for the cards' scoped subscriptions. */
  stream: AnyStream;
  supervisorTodos: Todo[];
  isLoading: boolean;
  isInterrupted: boolean;
  hitlToolNames: Set<string> | null;
  decisions: Partial<Record<string, HitlDecision>>;
  recordDecision: (toolCallId: string, decision: HitlDecision) => void;
  /** Interrupts raised inside subagents (`stream.interrupts` minus the root
   *  one); each card claims its own and approves it itself. */
  nestedInterrupts: Interrupt[];
  /** Resume an interrupt — `stream.respond(response, { interruptId })`. */
  respond: (response: HitlResponse, interruptId: string | null) => void;
  modelUnavailable: boolean;
  onRegenerate: () => void;
  error: unknown;
  rehydratedError: string | null;
};

/**
 * The conversation render tree, memoized so the page that owns `useStream`
 * (notified on every store tick) renders almost nothing itself. Every prop is
 * either throttled or identity-stable between ticks.
 */
export const ConversationBody = memo(function ConversationBody({
  messages,
  toolCalls,
  subagents,
  stream,
  supervisorTodos,
  isLoading,
  isInterrupted,
  hitlToolNames,
  decisions,
  recordDecision,
  nestedInterrupts,
  respond,
  modelUnavailable,
  onRegenerate,
  error,
  rehydratedError,
}: ConversationBodyProps) {
  const { mcpServers } = useMcpServersStore();
  const workspaceAgents = useAgentsStore((s) => s.agents);
  const describe = useDescribeTool(mcpServers);

  const findAgent = useCallback(
    (subagentType: string) =>
      workspaceAgents.find(
        (a) => sanitizeToolIdentifier(a.name) === subagentType,
      ) ??
      workspaceAgents.find(
        (a) =>
          a.name.toLowerCase() ===
          subagentType.replaceAll("_", " ").toLowerCase(),
      ),
    [workspaceAgents],
  );

  const chains = useMemo(
    () => groupChains(messages, toolCalls),
    [messages, toolCalls],
  );

  const last = messages.at(-1);
  const assistantStreaming = isLoading && last != null && isAIMessage(last);
  // The assistant has started a message but produced no text or tool call
  // yet: its reasoning is what's streaming.
  const preamble =
    assistantStreaming &&
    last.text.length === 0 &&
    !toolCalls.some((tc) => tc.messageId === last.id);
  const reasoningStreamingId =
    preamble && getReasoning(last) ? (last.id ?? null) : null;
  // "Thinking…" until anything at all arrives.
  const showThinking =
    isLoading &&
    last != null &&
    (isHumanMessage(last) || (preamble && reasoningStreamingId == null));
  const lastVisibleIndex = messages.findLastIndex((m) => !isToolMessage(m));

  return (
    <>
      {supervisorTodos.length > 0 && (
        <TodoList
          todos={supervisorTodos}
          className="mb-4 rounded-lg border border-border/50 bg-muted/30 p-4"
        />
      )}
      {messages.map((message, index) => {
        const key = message.id ?? index;
        if (isHumanMessage(message)) {
          return isHostNotice(message) ? (
            <HostNotice key={key} message={message} />
          ) : (
            <UserTurn
              key={key}
              message={message}
              anchorId={threadMapAnchor(index)}
            />
          );
        }
        if (!isAIMessage(message)) return null;

        const text = message.text;
        const sources = getWebSearchSources(message);
        const chain = message.id ? chains.get(message.id) : undefined;
        const isLast = index === lastVisibleIndex;

        return (
          <Fragment key={key}>
            {chain && (
              <Chain
                steps={chain}
                reasoningStreamingId={reasoningStreamingId}
                subagents={subagents}
                stream={stream}
                describe={describe}
                findAgent={findAgent}
                isInterrupted={isInterrupted}
                hitlToolNames={hitlToolNames}
                decisions={decisions}
                recordDecision={recordDecision}
                nestedInterrupts={nestedInterrupts}
                respond={respond}
                resumeInFlight={isLoading}
                modelUnavailable={modelUnavailable}
                coordinatorStreaming={assistantStreaming && isLast}
              />
            )}
            {text && (
              <>
                <Message from="assistant">
                  <MessageContent>
                    <MessageResponse>{text}</MessageResponse>
                    {sources.length > 0 && (
                      <WebSearchSources sources={sources} />
                    )}
                  </MessageContent>
                </Message>
                {!isLoading && isLast && (
                  <MessageActions>
                    {!modelUnavailable && (
                      <MessageAction onClick={onRegenerate} label="Retry">
                        <RefreshCcwIcon className="size-3" />
                      </MessageAction>
                    )}
                    <MessageAction
                      onClick={() => {
                        void navigator.clipboard.writeText(text);
                      }}
                      label="Copy"
                    >
                      <CopyIcon className="size-3" />
                    </MessageAction>
                  </MessageActions>
                )}
              </>
            )}
          </Fragment>
        );
      })}

      {showThinking && <ChainThinking />}

      {(error != null || rehydratedError != null) && (
        <Error>
          <ErrorContent>An error occurred.</ErrorContent>
          <ErrorDetails>
            <div>
              {error != null
                ? error instanceof globalThis.Error
                  ? error.message
                  : String(error)
                : rehydratedError}
            </div>
          </ErrorDetails>
        </Error>
      )}
    </>
  );
});

/**
 * A user-role message the runtime authored, not the user: it carries
 * `name: "host"` and `additional_kwargs.host_notice` (e.g. the sandbox of
 * the thread was replaced). Rendered as a muted event line, never as a
 * user bubble, so the transcript keeps who said what.
 */
export function isHostNotice(message: BaseMessage): boolean {
  return (
    message.name === "host" &&
    typeof message.additional_kwargs?.host_notice === "string"
  );
}

const HostNotice = ({ message }: { message: BaseMessage }) => (
  <div className="my-2 flex justify-center">
    <p className="max-w-[80%] rounded-md border border-dashed border-border px-3 py-1.5 text-center text-[11.5px] leading-[1.5] text-muted-foreground">
      {message.text.replace(/^\[Host notice\]\s*/, "")}
    </p>
  </div>
);

type WebSearchSource = {
  url: string;
  title: string;
};

const SOURCE_HINT = /(annotation|citation|grounding|search|source)/i;

function getWebSearchSources(message: BaseMessage): WebSearchSource[] {
  const sources = new Map<string, WebSearchSource>();
  const seen = new WeakSet<object>();

  const visit = (value: unknown, hinted = false) => {
    if (Array.isArray(value)) {
      value.forEach((item) => {
        visit(item, hinted);
      });
      return;
    }
    if (value === null || typeof value !== "object") return;
    if (seen.has(value)) return;
    seen.add(value);

    const record = value as Record<string, unknown>;
    const typeHint =
      typeof record.type === "string" && SOURCE_HINT.test(record.type);
    const nextHint = hinted || typeHint;
    const candidate =
      typeof record.url === "string"
        ? record.url
        : typeof record.uri === "string"
          ? record.uri
          : null;

    if (candidate && nextHint) {
      try {
        const url = new URL(candidate);
        if (url.protocol === "https:" || url.protocol === "http:") {
          const title =
            typeof record.title === "string" && record.title.trim()
              ? record.title.trim()
              : url.hostname.replace(/^www\./, "");
          sources.set(url.href, { url: url.href, title });
        }
      } catch {
        // Ignore malformed provider metadata rather than rendering unsafe links.
      }
    }

    for (const [key, child] of Object.entries(record)) {
      visit(child, nextHint || SOURCE_HINT.test(key));
    }
  };

  visit(message.content);
  visit(message.additional_kwargs);
  visit(message.response_metadata);
  return [...sources.values()];
}

const WebSearchSources = ({ sources }: { sources: WebSearchSource[] }) => (
  <div className="mt-1 flex flex-wrap items-center gap-1.5">
    <span className="mr-0.5 text-[10.5px] font-medium text-meta dark:text-panel-dim">
      Sources
    </span>
    {sources.map((source) => (
      <a
        key={source.url}
        href={source.url}
        target="_blank"
        rel="noreferrer"
        className="inline-flex max-w-52 items-center gap-1 truncate rounded-md border border-border/70 bg-card px-2 py-1 text-[10.5px] font-medium text-body transition-colors hover:border-border-hover hover:text-petrol dark:bg-panel dark:text-panel-body dark:hover:text-panel-terminal"
        title={source.title}
      >
        <span className="truncate">{source.title}</span>
        <ExternalLinkIcon className="size-2.5 shrink-0" />
      </a>
    ))}
  </div>
);

const UserTurn = ({
  message,
  anchorId,
}: {
  message: BaseMessage;
  anchorId: string;
}) => {
  const { text, context, source } = presentSideChannelMessage(message.text);
  const attachments = getFileAttachments(message);
  return (
    <div id={anchorId} className="flex flex-col gap-2">
      {attachments.length > 0 && (
        <div className="flex justify-end">
          <Attachments variant="inline">
            {attachments.map((attachment) => {
              const label = getAttachmentLabel(attachment);
              return (
                <AttachmentHoverCard key={attachment.id}>
                  <AttachmentHoverCardTrigger asChild>
                    <Attachment data={attachment}>
                      <div className="relative size-5 shrink-0">
                        <div className="absolute inset-0 transition-opacity group-hover:opacity-0">
                          <AttachmentPreview />
                        </div>
                      </div>
                      <AttachmentInfo />
                    </Attachment>
                  </AttachmentHoverCardTrigger>
                  <AttachmentHoverCardContent>
                    <div className="space-y-3">
                      {getMediaCategory(attachment) === "image" &&
                        "url" in attachment &&
                        attachment.url && (
                          <div className="flex items-center justify-center overflow-hidden rounded-md border">
                            <Image
                              alt={label}
                              className="object-contain"
                              height={200}
                              src={attachment.url}
                              width={200}
                            />
                          </div>
                        )}
                      <div className="space-y-1 px-0.5">
                        <h4 className="font-semibold text-sm leading-none">
                          {label}
                        </h4>
                      </div>
                    </div>
                  </AttachmentHoverCardContent>
                </AttachmentHoverCard>
              );
            })}
          </Attachments>
        </div>
      )}
      {context.length > 0 && (
        <SideChannelContextDetails messages={context} source={source} />
      )}
      {text && (
        <Message from="user">
          <MessageContent>
            <MessageResponse>{text}</MessageResponse>
          </MessageContent>
        </Message>
      )}
    </div>
  );
};

const SideChannelContextDetails = ({
  messages,
  source,
}: {
  messages: SideChannelContextMessage[];
  source: string | null;
}) => (
  <div className="flex justify-end">
    <Collapsible className="group/side-channel-context flex w-fit max-w-[78%] flex-col items-end">
      <CollapsibleTrigger className="ml-auto flex cursor-pointer items-center gap-2 rounded-lg border border-border/70 bg-card px-2.5 py-1.5 text-left text-[11.5px] text-meta shadow-[0_1px_2px_rgba(0,0,0,0.03)] transition-colors hover:border-border-hover hover:text-foreground dark:bg-panel">
        {source === "slack" ? (
          <SlackLogo className="size-4 rounded-[4px] border-0 shadow-none" />
        ) : (
          <MessagesSquareIcon className="size-3.5 text-petrol dark:text-panel-terminal" />
        )}
        <span className="font-semibold text-body dark:text-panel-body">
          {source === "slack" ? "Slack" : (source ?? "Side channel")}
        </span>
        <span className="font-mono text-[10px]">
          context
        </span>
        <span className="font-mono text-[10.5px]">
          {messages.length} message{messages.length === 1 ? "" : "s"}
        </span>
        <ChevronDownIcon className="size-3 shrink-0 -rotate-90 transition-transform duration-200 group-data-[state=open]/side-channel-context:rotate-0" />
      </CollapsibleTrigger>
      <CollapsibleContent className="data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down w-fit max-w-full overflow-hidden">
        <div className="mt-2 flex max-h-80 max-w-[min(34rem,72vw)] flex-col items-end gap-2.5 overflow-y-auto">
          {messages.map((message, index) => (
            <div
                  key={`${message.participantId}-${index}`}
              className="w-fit max-w-full rounded-[12px_12px_3px_12px] border border-border/60 bg-white px-3 py-1.5 shadow-[0_1px_2px_rgba(0,0,0,0.035)] dark:bg-panel"
            >
              <div className="mb-0.5 font-mono text-[9.5px] leading-none text-meta dark:text-panel-dim">
                    {message.participantId}
              </div>
              <div className="whitespace-pre-wrap text-[12.5px] leading-[1.4] text-body dark:text-panel-body">
                {message.text}
              </div>
            </div>
          ))}
        </div>
      </CollapsibleContent>
    </Collapsible>
  </div>
);

type ChainProps = {
  steps: ChainStepData[];
  /** The AI message whose reasoning is still streaming, if any. */
  reasoningStreamingId: string | null;
  subagents: ReadonlyMap<string, SubagentDiscoverySnapshot>;
  stream: AnyStream;
  describe: DescribeTool;
  findAgent: (subagentType: string) => SubAgentCardAgent | undefined;
  isInterrupted: boolean;
  hitlToolNames: Set<string> | null;
  decisions: Partial<Record<string, HitlDecision>>;
  recordDecision: (toolCallId: string, decision: HitlDecision) => void;
  nestedInterrupts: Interrupt[];
  respond: (response: HitlResponse, interruptId: string | null) => void;
  /** A run is executing: a card's approval waits for it to settle. */
  resumeInFlight: boolean;
  modelUnavailable: boolean;
  coordinatorStreaming: boolean;
};

type SubAgentCardAgent = NonNullable<
  React.ComponentProps<typeof SubAgentCard>["agent"]
>;

type ToolRow = {
  kind: "tool";
  tc: ToolCallView;
  /** The discovered subagent, for a `task` call the SDK has bound. */
  sub: SubagentDiscoverySnapshot | undefined;
  state: ToolStepState;
};
type ChainRow = Extract<ChainStepData, { kind: "reasoning" }> | ToolRow;

/** One turn's chain of thought: reasoning, tool steps and subagent cards on
 *  the rail, then the MCP app widgets of any tool that returned one. */
const Chain = ({
  steps,
  reasoningStreamingId,
  subagents,
  stream,
  describe,
  findAgent,
  isInterrupted,
  hitlToolNames,
  decisions,
  recordDecision,
  nestedInterrupts,
  respond,
  resumeInFlight,
  modelUnavailable,
  coordinatorStreaming,
}: ChainProps) => {
  const rows: ChainRow[] = steps.map((step) =>
    step.kind === "reasoning"
      ? step
      : {
          kind: "tool",
          tc: step.tc,
          sub: step.tc.name === "task" ? subagents.get(step.tc.id) : undefined,
          state: getToolStepState(step.tc, isInterrupted, hitlToolNames),
        },
  );
  const tools = rows.filter((r): r is ToolRow => r.kind === "tool");
  const chainSubagents = tools
    .map((r) => r.sub)
    .filter((s): s is SubagentDiscoverySnapshot => s != null);
  const reasoningStreaming = rows.some(
    (r) => r.kind === "reasoning" && r.messageId === reasoningStreamingId,
  );
  // A subagent of this chain paused on an approval: its card shows the
  // approval, the chain stays open and stops reading as active.
  const pausedSubagents = chainSubagents.filter(
    (s) =>
      s.status === "running" &&
      nestedInterrupts.some((i) => claimsInterrupt(i, s)),
  );

  return (
    <div className="w-full space-y-2">
      <ChainOfThought
        active={
          reasoningStreaming ||
          tools.some((r) =>
            r.sub
              ? r.sub.status === "running" && !pausedSubagents.includes(r.sub)
              : r.state === "running",
          )
        }
        lockOpen={
          pausedSubagents.length > 0 ||
          tools.some(
            (r) => !r.sub && r.state === "awaiting-approval" && !decisions[r.tc.id],
          )
        }
        toolCount={tools.length - chainSubagents.length}
        subagentCount={chainSubagents.length}
      >
        {rows.map((row) => {
          if (row.kind === "reasoning") {
            return (
              <ChainReasoningStep
                key={row.id}
                text={row.text}
                streaming={row.messageId === reasoningStreamingId}
              />
            );
          }
          const { tc, sub, state } = row;
          return sub ? (
            <SubAgentCard
              key={sub.id}
              subagent={sub}
              stream={stream}
              describe={describe}
              agent={findAgent(sub.name)}
              interrupts={nestedInterrupts}
              respond={respond}
              resumeInFlight={resumeInFlight}
              modelUnavailable={modelUnavailable}
            />
          ) : (
            <ToolStep
              key={tc.id}
              tc={tc}
              state={state}
              describe={describe}
              approval={
                state === "awaiting-approval"
                  ? {
                      decided: decisions[tc.id],
                      disabled: modelUnavailable,
                      onDecide: (decision) => {
                        recordDecision(tc.id, decision);
                      },
                    }
                  : undefined
              }
            />
          );
        })}
      </ChainOfThought>
      {chainSubagents.length > 0 && (
        <>
          <SubAgentProgress subagents={chainSubagents} />
          <SynthesisIndicator
            subagents={chainSubagents}
            isCoordinatorStreaming={coordinatorStreaming}
          />
        </>
      )}
      {tools.map(({ tc, sub }) => {
        const app = sub ? null : getMcpAppInfo(tc);
        if (!app) return null;
        return (
          <McpAppWidget
            key={`app-${tc.id}`}
            input={tc.args}
            output={tc.output}
            structuredContent={getStructuredContent(tc)}
            errorText={tc.error}
            toolName={describe(tc.name).toolName}
            appToolInfo={app}
          />
        );
      })}
    </div>
  );
};
