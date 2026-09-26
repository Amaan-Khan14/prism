import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AnalysisPage from "@/app/analyses/[id]/page";
import { ALL_FACET_KINDS, analysis, facetRow, SAMPLE_DIFF_TEXT } from "../fixtures";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "a-1" }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/analyses/a-1",
}));

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AnalysisPage live progress", () => {
  it("streams facet progress over SSE and renders the report when done", async () => {
    const runningState = {
      analysis_id: "a-1",
      status: "running",
      error: null,
      facets: [
        { kind: "intent_vs_spec", status: "completed" },
        { kind: "cross_file_impact", status: "running" },
        { kind: "test_coverage_gaps", status: "pending" },
        { kind: "risk_hazards", status: "pending" },
      ],
    };
    const doneState = {
      ...runningState,
      status: "completed",
      facets: runningState.facets.map((facet) => ({ ...facet, status: "completed" })),
    };

    let detailCalls = 0;
    const encoder = new TextEncoder();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => {
        const url = String(input instanceof Request ? input.url : input);
        if (url.endsWith("/stream")) {
          const stream = new ReadableStream<Uint8Array>({
            start(controller) {
              controller.enqueue(
                encoder.encode(`event: progress\ndata: ${JSON.stringify(runningState)}\n\n`),
              );
              controller.enqueue(
                encoder.encode(`event: done\ndata: ${JSON.stringify(doneState)}\n\n`),
              );
              controller.close();
            },
          });
          return new Response(stream, { status: 200 });
        }
        if (/\/analyses\/a-1$/.test(url)) {
          detailCalls += 1;
          if (detailCalls === 1) {
            return new Response(
              JSON.stringify(
                analysis({
                  status: "running",
                  facets: ALL_FACET_KINDS.map((kind) => facetRow(kind, "pending")),
                }),
              ),
              { status: 200, headers: { "Content-Type": "application/json" } },
            );
          }
          return new Response(JSON.stringify(analysis()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (url.endsWith("/diff")) {
          return new Response(SAMPLE_DIFF_TEXT, { status: 200 });
        }
        throw new Error(`Unhandled fetch in test: ${url}`);
      }),
    );

    render(<AnalysisPage />);

    // The mocked stream resolves almost instantly, so the page may already
    // have transitioned; the meaningful contract is the final report state.
    await waitFor(
      () => {
        expect(screen.getByTestId("analysis-report")).toBeInTheDocument();
      },
      { timeout: 3000 },
    );
    expect(detailCalls).toBeGreaterThanOrEqual(2);
    expect(screen.getByTestId("verified-findings")).toBeInTheDocument();
  });
});

describe("AnalysisPage terminal states", () => {
  it("renders the completed report directly for finished analyses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => {
        const url = String(input instanceof Request ? input.url : input);
        if (/\/analyses\/a-1$/.test(url)) {
          return new Response(JSON.stringify(analysis()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (url.endsWith("/diff")) {
          return new Response(SAMPLE_DIFF_TEXT, { status: 200 });
        }
        throw new Error(`Unhandled fetch in test: ${url}`);
      }),
    );

    render(<AnalysisPage />);

    expect(await screen.findByTestId("analysis-report")).toBeInTheDocument();
    expect(screen.queryByTestId("analysis-progress")).toBeNull();
  });

  it("shows a not-found state for missing analyses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ detail: "Analysis not found" }), { status: 404 }),
      ),
    );

    render(<AnalysisPage />);

    expect(await screen.findByText("Analysis not found")).toBeInTheDocument();
  });

  it("renders partial findings with an error banner for failed analyses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => {
        const url = String(input instanceof Request ? input.url : input);
        if (/\/analyses\/a-1$/.test(url)) {
          return new Response(
            JSON.stringify(
              analysis({ status: "failed", error: "Review failed for one or more facets." }),
            ),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (url.endsWith("/diff")) {
          return new Response(SAMPLE_DIFF_TEXT, { status: 200 });
        }
        throw new Error(`Unhandled fetch in test: ${url}`);
      }),
    );

    render(<AnalysisPage />);

    expect(await screen.findByTestId("analysis-error")).toBeInTheDocument();
    expect(screen.getByTestId("analysis-error")).toHaveTextContent(
      "Review failed for one or more facets.",
    );
  });
});
