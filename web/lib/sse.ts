import { API_URL } from "./config";
import type { HistoryTurn, QueryResult, Step } from "./types";

export type StreamEvent =
  | { kind: "step"; data: Step }
  | { kind: "token"; data: { text: string } }
  | { kind: "result"; data: QueryResult }
  | { kind: "error"; data: { message: string } };

/**
 * Incremental Server-Sent Events parser. Feed it chunks of text as they arrive; it calls `onEvent` for every
 * complete event (blocks end with a blank line). Handles \r\n, multi-line data and chunks split anywhere.
 */
export function createSSEParser(onEvent: (event: string, data: string) => void) {
  let buffer = "";
  return {
    push(chunk: string) {
      // Normalise the whole buffer so a \r\n split across two chunks is still joined
      buffer = (buffer + chunk).replace(/\r\n/g, "\n");
      let end: number;
      while ((end = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        let event = "message";
        const data: string[] = [];
        for (const line of block.split("\n")) {
          if (line.startsWith(":")) continue;
          const colon = line.indexOf(":");
          const field = colon === -1 ? line : line.slice(0, colon);
          const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
          if (field === "event") event = value;
          else if (field === "data") data.push(value);
        }
        if (data.length) onEvent(event, data.join("\n"));
      }
    },
  };
}

export class RateLimitedError extends Error {}

/** Ask a question over /query/stream, calling `onEvent` for each step, token and the final result. */
export async function streamQuery(
  question: string,
  history: HistoryTurn[],
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_URL}/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ query_text: question, history }),
    signal,
  });
  if (response.status === 429) {
    const body = await response.json().catch(() => ({}));
    throw new RateLimitedError(body.message || "Too many questions for now. Please wait a minute.");
  }
  if (!response.ok || !response.body) throw new Error(`The API answered with HTTP ${response.status}`);

  const parser = createSSEParser((event, data) => {
    if (event === "step" || event === "token" || event === "result" || event === "error") {
      onEvent({ kind: event, data: JSON.parse(data) } as StreamEvent);
    }
  });
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    parser.push(value);
  }
}
