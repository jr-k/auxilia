export const WORKSPACE_EVENT_KINDS = [
  "agents",
  "triggers",
  "mcp_servers",
  "skills",
  "threads",
  "runs",
  "prompt_queue",
  "trigger_history",
  "notifications",
] as const;

export type WorkspaceEventKind = (typeof WORKSPACE_EVENT_KINDS)[number];

export type WorkspaceInvalidation = {
  kind: WorkspaceEventKind;
  eventKey?: string;
  threadId?: string;
  payload?: {
    title: string;
    body: string;
    url?: string;
  };
};

export function isWorkspaceInvalidation(
  value: unknown,
): value is WorkspaceInvalidation {
  if (value === null || typeof value !== "object") return false;
  const event = value as Record<string, unknown>;
  const payload = event.payload;
  const validPayload =
    payload === undefined ||
    (payload !== null &&
      typeof payload === "object" &&
      typeof (payload as Record<string, unknown>).title === "string" &&
      typeof (payload as Record<string, unknown>).body === "string" &&
      ((payload as Record<string, unknown>).url === undefined ||
        typeof (payload as Record<string, unknown>).url === "string"));
  return (
    typeof event.kind === "string" &&
    WORKSPACE_EVENT_KINDS.includes(event.kind as WorkspaceEventKind) &&
    (event.eventKey === undefined || typeof event.eventKey === "string") &&
    (event.threadId === undefined || typeof event.threadId === "string") &&
    validPayload
  );
}
