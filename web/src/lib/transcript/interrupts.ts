import type { Interrupt } from "@langchain/langgraph-sdk";
import { sanitizeToolIdentifier } from "./message";

/** `stream.interrupts` mirrors every namespace's pending interrupt; the root
 *  one drives the root chain's approval UI, the nested ones belong to the
 *  subagent cards (`findSubagentInterrupt`). */
export function splitInterrupts(interrupts: readonly Interrupt[]): {
  root: Interrupt | null;
  nested: Interrupt[];
} {
  let root: Interrupt | null = null;
  const nested: Interrupt[] = [];
  for (const interrupt of interrupts) {
    if (isRootNamespace(interrupt.namespace)) root ??= interrupt;
    else nested.push(interrupt);
  }
  return { root, nested };
}

const isRootNamespace = (namespace: readonly string[] | undefined) =>
  namespace == null || namespace.length === 0;

export const sameNamespace = (
  a: readonly string[] | undefined,
  b: readonly string[],
) => a != null && a.length === b.length && a.join("|") === b.join("|");

/**
 * Whether an interrupt was raised inside this subagent.
 *
 * Live, the backend stamps the subagent's execution namespace
 * (`tools:<pregel task id>`) on `input.requested`, and the SDK binds the same
 * namespace onto the discovery snapshot as the subagent streams. A page that
 * hydrates instead rebuilds the snapshot under the SDK's discovery key,
 * `tools:<tool_call_id>`, and the backend addresses a hydrated interrupt with
 * that key — so both are accepted, and nothing is matched by content (two
 * siblings calling the same tool with the same arguments would otherwise
 * claim one interrupt).
 */
export function claimsInterrupt(
  interrupt: Interrupt,
  subagent: { id: string; namespace: readonly string[] },
): boolean {
  return (
    sameNamespace(interrupt.namespace, subagent.namespace) ||
    sameNamespace(interrupt.namespace, [`tools:${subagent.id}`])
  );
}

/** The pending interrupt raised inside one subagent, if any. */
export function findSubagentInterrupt(
  nested: readonly Interrupt[],
  subagent: { id: string; namespace: readonly string[] },
): Interrupt | null {
  return nested.find((interrupt) => claimsInterrupt(interrupt, subagent)) ?? null;
}

export type ElicitationRequest =
  | {
      key: string;
      message: string;
      mode: "form";
      requested_schema: ElicitationSchema;
    }
  | { key: string; message: string; mode: "url"; url: string };

export type ElicitationSchema = {
  properties?: Record<string, ElicitationField>;
  required?: string[];
};

type TitledOption = { const: string; title?: string };

export type ElicitationField = {
  type?: "string" | "number" | "integer" | "boolean" | "array";
  title?: string;
  description?: string;
  format?: string;
  enum?: string[];
  enumNames?: string[];
  oneOf?: TitledOption[];
  items?: { enum?: string[]; anyOf?: TitledOption[] };
  minItems?: number;
  maxItems?: number;
  default?: unknown;
};

export type ElicitationChoices = {
  options: { value: string; label: string }[];
  multi: boolean;
};

export function elicitationChoices(
  field: ElicitationField,
): ElicitationChoices | null {
  const multi = field.type === "array";
  const titled = multi ? field.items?.anyOf : field.oneOf;
  const values = multi ? field.items?.enum : field.enum;
  const options = titled
    ? titled.map((option) => ({
        value: option.const,
        label: option.title ?? option.const,
      }))
    : values?.map((value, index) => ({
        value,
        label: (!multi && field.enumNames?.[index]) || value,
      }));
  return options ? { options, multi } : null;
}

export type ElicitationInterrupt = {
  type: "mcp_elicitation";
  tool_name: string;
  /** Exact runtime call association supplied by the protocol emitter. */
  tool_call_id?: string;
  requests: ElicitationRequest[];
};

export type ElicitationAnswer =
  | { action: "accept"; content?: Record<string, unknown> }
  | { action: "decline" }
  | { action: "cancel" };

export type ElicitationResponse = {
  responses: Record<string, ElicitationAnswer>;
};

export function isElicitation(value: unknown): value is ElicitationInterrupt {
  return (
    value != null &&
    typeof value === "object" &&
    (value as { type?: unknown }).type === "mcp_elicitation"
  );
}

function elicitationToolName(value: unknown): string | null {
  return isElicitation(value) ? sanitizeToolIdentifier(value.tool_name) : null;
}

/** Locate the exact paused call, falling back to its runtime tool name only
 * for checkpoints created before exact association was emitted. */
export function findElicitedCallId(
  toolCalls: readonly { id: string; name: string; status: string }[],
  value: unknown,
): string | null {
  if (!isElicitation(value)) return null;
  if (
    value.tool_call_id &&
    toolCalls.some(
      (call) =>
        call.id === value.tool_call_id &&
        call.status !== "finished" &&
        call.status !== "error",
    )
  ) {
    return value.tool_call_id;
  }
  const name = elicitationToolName(value);
  if (name == null) return null;
  return (
    toolCalls.findLast(
      (call) =>
        (call.name === name || call.name.endsWith(`_${name}`)) &&
        call.status !== "finished" &&
        call.status !== "error",
    )?.id ?? null
  );
}

/** The HITL middleware only hangs the tool calls named in the interrupt's
 *  `action_requests`; sibling calls in the same turn run on resume. */
export function extractHitlToolNames(value: unknown): Set<string> | null {
  if (isElicitation(value)) return new Set();
  if (!value || typeof value !== "object") return null;
  const requests = (value as { action_requests?: unknown }).action_requests;
  if (!Array.isArray(requests)) return null;
  return new Set(
    requests
      .map((r: { name?: unknown } | null) => r?.name)
      .filter((n): n is string => typeof n === "string"),
  );
}
