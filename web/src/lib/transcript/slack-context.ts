export type SlackContextMessage = {
  userId: string;
  text: string;
};

export type SlackMessagePresentation = {
  text: string;
  context: SlackContextMessage[];
};

const CONTEXT_OPEN = "<slack_thread_context>\n";
const REQUEST_SEPARATOR =
  "\n</slack_thread_context>\n\n<current_request>\n";
const REQUEST_CLOSE = "\n</current_request>";
const MESSAGE_HEADER = /(?:^|\n\n)\[Slack user ([^\]\n]+)\]\n/g;
const LEADING_MENTION = /^<@[A-Z0-9]+>\s*/;

function parseContext(transcript: string): SlackContextMessage[] {
  const matches = [...transcript.matchAll(MESSAGE_HEADER)];
  return matches.flatMap((match, index) => {
    const userId = match[1];
    const start = (match.index ?? 0) + match[0].length;
    const end = matches[index + 1]?.index ?? transcript.length;
    const text = transcript.slice(start, end).trim();
    return userId && text ? [{ userId, text }] : [];
  });
}

/**
 * Split the model-facing Slack envelope from the user-facing message.
 * Older and non-Slack messages pass through untouched.
 */
export function presentSlackMessage(raw: string): SlackMessagePresentation {
  const contextStart = raw.indexOf(CONTEXT_OPEN);
  if (contextStart < 0) return { text: raw, context: [] };

  const contextEnd = raw.indexOf(REQUEST_SEPARATOR, contextStart);
  const requestEnd = raw.lastIndexOf(REQUEST_CLOSE);
  if (contextEnd < 0 || requestEnd < contextEnd) {
    return { text: raw, context: [] };
  }

  const requestStart = contextEnd + REQUEST_SEPARATOR.length;
  const text = raw.slice(requestStart, requestEnd);
  const context = parseContext(
    raw.slice(contextStart + CONTEXT_OPEN.length, contextEnd),
  );

  // Slack may include the current app_mention in conversations.replies even
  // with an exclusive `latest` boundary. It is already rendered as the current
  // request, so hide that duplicate from the expandable context.
  const last = context.at(-1);
  if (
    last &&
    last.text.replace(LEADING_MENTION, "").trim() === text.trim()
  ) {
    context.pop();
  }

  return { text, context };
}
