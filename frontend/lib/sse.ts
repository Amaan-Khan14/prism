/** Fetch-based SSE reader for the backend analysis progress stream. */
import { API_URL } from "./api";
import type { StreamState } from "./types";

/**
 * Incremental parser for the server-sent events wire format
 * (`event: <name>\ndata: <payload>\n\n`).
 */
export class SseParser {
  private buffer = "";

  /** Feed one decoded chunk; returns the complete events it completes. */
  push(chunk: string): { event: string; data: string }[] {
    this.buffer += chunk;
    const events: { event: string; data: string }[] = [];
    let boundary = this.buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawEvent = this.buffer.slice(0, boundary);
      this.buffer = this.buffer.slice(boundary + 2);
      const parsed = parseEventBlock(rawEvent);
      if (parsed) events.push(parsed);
      boundary = this.buffer.indexOf("\n\n");
    }
    return events;
  }

  /** Whether a partial event is waiting for more bytes. */
  get hasPartial(): boolean {
    return this.buffer.length > 0;
  }
}

function parseEventBlock(block: string): { event: string; data: string } | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (dataLines.length === 0) return null;
  return { event, data: dataLines.join("\n") };
}

export interface StreamCallbacks {
  /** Called for every `progress` event and once with the final `done` state. */
  onProgress: (state: StreamState, done: boolean) => void;
  /** Called when the stream errors, stalls, or ends without a `done` event. */
  onError: (error: Error) => void;
  /** Abort after this many milliseconds without any bytes (default 30s). */
  stallTimeoutMs?: number;
}

export interface StreamHandle {
  abort: () => void;
}

/**
 * Stream live analysis progress over SSE using fetch (cookies included).
 *
 * The backend only emits when state changes, so a watchdog aborts the
 * request if no bytes arrive within `stallTimeoutMs`; callers can then fall
 * back to polling `GET /analyses/{id}`.
 */
export function streamAnalysisProgress(
  analysisId: string,
  callbacks: StreamCallbacks,
): StreamHandle {
  const controller = new AbortController();
  const stallTimeoutMs = callbacks.stallTimeoutMs ?? 30_000;
  let stallTimer: ReturnType<typeof setTimeout> | undefined;
  let settled = false;

  const resetStallTimer = () => {
    if (stallTimer) clearTimeout(stallTimer);
    stallTimer = setTimeout(() => {
      if (settled) return;
      settled = true;
      controller.abort();
      callbacks.onError(new Error("Analysis progress stream stalled."));
    }, stallTimeoutMs);
  };

  const abort = (userInitiated: boolean) => {
    if (settled && !userInitiated) return;
    settled = true;
    if (stallTimer) clearTimeout(stallTimer);
    controller.abort();
  };

  void (async () => {
    resetStallTimer();
    try {
      const response = await fetch(
        `${API_URL}/analyses/${encodeURIComponent(analysisId)}/stream`,
        { credentials: "include", signal: controller.signal },
      );
      if (!response.ok || !response.body) {
        throw new Error(`Progress stream failed with status ${response.status}.`);
      }
      const reader = response.body.getReader();
      const parser = new SseParser();
      const decoder = new TextDecoder();
      for (;;) {
        const { value, done } = await reader.read();
        if (value) {
          resetStallTimer();
          for (const event of parser.push(decoder.decode(value, { stream: true }))) {
            if (event.event !== "progress" && event.event !== "done") continue;
            let state: StreamState;
            try {
              state = JSON.parse(event.data) as StreamState;
            } catch {
              continue;
            }
            callbacks.onProgress(state, event.event === "done");
            if (event.event === "done") {
              abort(false);
              return;
            }
          }
        }
        if (done) break;
      }
      if (!settled) {
        settled = true;
        if (stallTimer) clearTimeout(stallTimer);
        callbacks.onError(new Error("Analysis progress stream closed unexpectedly."));
      }
    } catch (error) {
      if (settled) return;
      settled = true;
      if (stallTimer) clearTimeout(stallTimer);
      callbacks.onError(
        error instanceof Error ? error : new Error("Analysis progress stream failed."),
      );
    }
  })();

  return {
    abort: () => abort(true),
  };
}
