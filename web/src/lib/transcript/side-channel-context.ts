export type SideChannelContextMessage = {
  participantId: string;
  text: string;
};

export type SideChannelMessagePresentation = {
  text: string;
  context: SideChannelContextMessage[];
  source: string | null;
};

type ResolvedContextEnvelope = {
  open: string;
  requestSeparator: string;
  source: string;
};

const SIDE_CHANNEL_OPEN =
  /<side_channel_context source="([a-z0-9_-]+)">\n/i;
const SIDE_CHANNEL_REQUEST_SEPARATOR =
  "\n</side_channel_context>\n\n<current_request>\n";
const REQUEST_CLOSE = "\n</current_request>";
const MESSAGE_HEADER = /(?:^|\n\n)\[Side-channel user ([^\]\n]+)\]\n/g;
const LEADING_MENTION = /^<@[A-Z0-9]+>\s*/;

function resolveEnvelope(raw: string): ResolvedContextEnvelope | null {
  const current = SIDE_CHANNEL_OPEN.exec(raw);
  if (current?.[1]) {
    return {
      open: current[0],
      requestSeparator: SIDE_CHANNEL_REQUEST_SEPARATOR,
      source: current[1].toLowerCase(),
    };
  }
  return null;
}

function parseContext(transcript: string): SideChannelContextMessage[] {
  const matches = [...transcript.matchAll(MESSAGE_HEADER)];
  return matches.flatMap((match, index) => {
    const participantId = match[1];
    const start = (match.index ?? 0) + match[0].length;
    const end = matches[index + 1]?.index ?? transcript.length;
    const text = transcript.slice(start, end).trim();
    return participantId && text ? [{ participantId, text }] : [];
  });
}

/**
 * Split model-facing side-channel context from the user-facing request.
 * Plain messages pass through untouched.
 */
export function presentSideChannelMessage(
  raw: string,
): SideChannelMessagePresentation {
  const envelope = resolveEnvelope(raw);
  if (!envelope) return { text: raw, context: [], source: null };

  const contextStart = raw.indexOf(envelope.open);
  const contextEnd = raw.indexOf(
    envelope.requestSeparator,
    contextStart,
  );
  const requestEnd = raw.lastIndexOf(REQUEST_CLOSE);
  if (contextEnd < 0 || requestEnd < contextEnd) {
    return { text: raw, context: [], source: null };
  }

  const requestStart = contextEnd + envelope.requestSeparator.length;
  const text = raw.slice(requestStart, requestEnd);
  const context = parseContext(
    raw.slice(contextStart + envelope.open.length, contextEnd),
  );

  // A side channel may return the triggering request despite an exclusive
  // boundary. It is already the current request, so hide that duplicate.
  const last = context.at(-1);
  if (
    last &&
    last.text.replace(LEADING_MENTION, "").trim() === text.trim()
  ) {
    context.pop();
  }

  return { text, context, source: envelope.source };
}
