import { afterEach, describe, expect, it, vi } from "vitest";
import { SseParser, streamAnalysisProgress } from "@/lib/sse";
import type { StreamState } from "@/lib/types";

afterEach(() => {
  vi.unstubAllGlobals();
});

function sseState(overrides: Partial<StreamState> = {}): StreamState {
  return {
    analysis_id: "a1",
    status: "running",
    error: null,
    facets: [
      { kind: "intent_vs_spec", status: "completed" },
      { kind: "cross_file_impact", status: "running" },
      { kind: "test_coverage_gaps", status: "pending" },
      { kind: "risk_hazards", status: "pending" },
    ],
    ...overrides,
  };
}

function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

describe("SseParser", () => {
  it("parses events split across chunk boundaries", () => {
    const parser = new SseParser();
    expect(parser.push("event: progress\ndata: {\"stat")).toEqual([]);
    expect(parser.push("us\": \"running\"}\n\nevent: done\ndata: {}\n\n")).toEqual([
      { event: "progress", data: '{"status": "running"}' },
      { event: "done", data: "{}" },
    ]);
  });

  it("joins multi-line data fields and ignores unrelated events", () => {
    const parser = new SseParser();
    const events = parser.push("event: message\ndata: line1\ndata: line2\n\n: keepalive\n\n");
    expect(events).toEqual([{ event: "message", data: "line1\nline2" }]);
  });
});

describe("streamAnalysisProgress", () => {
  it("emits progress events and resolves on done", async () => {
    const progressState = sseState();
    const doneState = sseState({ status: "completed" });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        sseResponse([
          `event: progress\ndata: ${JSON.stringify(progressState)}\n\n`,
          `event: done\ndata: ${JSON.stringify(doneState)}\n\n`,
        ]),
      ),
    );
    const onProgress = vi.fn();
    const onError = vi.fn();

    streamAnalysisProgress("a1", { onProgress, onError });

    await vi.waitFor(() => {
      expect(onProgress).toHaveBeenCalledWith(doneState, true);
    });
    expect(onProgress).toHaveBeenNthCalledWith(1, progressState, false);
    expect(onError).not.toHaveBeenCalled();
  });

  it("reports an error when the endpoint fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("nope", { status: 404 })));
    const onProgress = vi.fn();
    const onError = vi.fn();

    streamAnalysisProgress("a1", { onProgress, onError, stallTimeoutMs: 5_000 });

    await vi.waitFor(() => {
      expect(onError).toHaveBeenCalled();
    });
    expect(onProgress).not.toHaveBeenCalled();
  });
});
