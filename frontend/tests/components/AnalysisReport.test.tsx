import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AnalysisReport } from "@/components/AnalysisReport";
import { diffRowId } from "@/lib/diff";
import { analysis, SAMPLE_DIFF_TEXT } from "../fixtures";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubDiffFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/diff")) {
        return new Response(SAMPLE_DIFF_TEXT, { status: 200 });
      }
      throw new Error(`Unhandled fetch in test: ${url}`);
    }),
  );
}

describe("AnalysisReport", () => {
  it("renders the brief, verified findings, and unverified appendix", async () => {
    stubDiffFetch();
    render(<AnalysisReport analysis={analysis()} />);

    expect(screen.getByTestId("analysis-brief")).toHaveTextContent(
      "Evidence gate confirmed 1 of 2 claims.",
    );
    expect(screen.getByTestId("verified-findings")).toHaveTextContent(
      "Retry loop can mask downstream failures.",
    );
    expect(screen.getByTestId("unverified-appendix")).toHaveTextContent(
      "Claims a coverage gap without a coverage artifact.",
    );
  });

  it("opens the cited row in the in-place Diff tab", async () => {
    stubDiffFetch();
    const scrollIntoView = vi.fn();
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
    render(<AnalysisReport analysis={analysis()} />);

    await userEvent.click(screen.getByRole("tab", { name: "Evidence" }));
    await userEvent.click(screen.getByRole("button", { name: "View in diff" }));

    expect(screen.getByRole("tab", { name: "Diff" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("review-diff-panel")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("diff-viewer")).toBeInTheDocument();
    });
    await waitFor(
      () => {
        expect(scrollIntoView).toHaveBeenCalled();
      },
      { timeout: 3000 },
    );
    expect(document.getElementById(diffRowId("app/pipeline.py", 11))).not.toBeNull();
  });

  it("shows accepted coverage provenance details", async () => {
    stubDiffFetch();
    render(<AnalysisReport analysis={analysis()} />);

    await userEvent.click(screen.getByRole("tab", { name: "Coverage" }));
    const card = screen.getByTestId("coverage-card");
    expect(card).toHaveAttribute("data-coverage-status", "accepted");
    expect(card).toHaveTextContent("Coverage artifact accepted");
    expect(card).toHaveTextContent("github_actions");
    expect(card).toHaveTextContent("#12345678");
    expect(card).toHaveTextContent("coverage-report");
    expect(card).toHaveTextContent("lcov");
  });

  it("communicates unknown coverage for rejected artifacts", async () => {
    stubDiffFetch();
    render(
      <AnalysisReport
        analysis={analysis({
          coverage_status: "rejected",
          coverage_rejection_reason: "Head SHA did not match the analyzed commit.",
        })}
      />,
    );

    await userEvent.click(screen.getByRole("tab", { name: "Coverage" }));
    const card = screen.getByTestId("coverage-card");
    expect(card).toHaveAttribute("data-coverage-status", "rejected");
    expect(card).toHaveTextContent("treated as unknown");
    expect(card).toHaveTextContent("Head SHA did not match the analyzed commit.");
  });

  it("shows a friendly empty state when nothing was verified", () => {
    stubDiffFetch();
    render(<AnalysisReport analysis={analysis({ facets: [] })} />);

    expect(screen.getByTestId("no-findings")).toHaveTextContent(
      "Nothing verified to report",
    );
    expect(screen.queryByTestId("unverified-appendix")).toBeNull();
  });

  it("explains partial results when an analysis failed with completed facets", () => {
    stubDiffFetch();
    render(
      <AnalysisReport
        analysis={analysis({
          status: "failed",
          error: "Review failed for one or more facets.",
        })}
      />,
    );

    expect(screen.getByTestId("analysis-error")).toHaveTextContent("failed partway through");
    expect(screen.getByTestId("analysis-error")).toHaveTextContent(
      "Review failed for one or more facets.",
    );
    expect(screen.getByTestId("verified-findings")).toHaveTextContent(
      "Retry loop can mask downstream failures.",
    );
  });
});
