import { describe, expect, it } from "vitest";
import { createSSEParser } from "./sse";

function collect(chunks: string[]) {
  const events: [string, string][] = [];
  const parser = createSSEParser((event, data) => events.push([event, data]));
  chunks.forEach((c) => parser.push(c));
  return events;
}

describe("createSSEParser", () => {
  it("parses complete events", () => {
    expect(collect(['event: step\ndata: {"step":"understood"}\n\nevent: token\ndata: {"text":"Hi"}\n\n'])).toEqual([
      ["step", '{"step":"understood"}'],
      ["token", '{"text":"Hi"}'],
    ]);
  });

  it("handles events split across chunks and CRLF line endings", () => {
    expect(collect(["event: tok", 'en\r\ndata: {"text":', '"a"}\r', "\n\r\n", "event: result\ndata: {}\n", "\n"])).toEqual([
      ["token", '{"text":"a"}'],
      ["result", "{}"],
    ]);
  });

  it("joins multi-line data, ignores comments and waits for the blank line", () => {
    const events = collect([": keep-alive\n\ndata: line1\ndata: line2\n\nevent: step\ndata: {}"]);
    expect(events).toEqual([["message", "line1\nline2"]]);
  });
});
