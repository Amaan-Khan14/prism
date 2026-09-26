import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FindingCard } from "@/components/FindingCard";
import { citation, finding } from "../fixtures";

describe("FindingCard", () => {
  it("shows verdict, severity, summary, and citation location", () => {
    render(<FindingCard finding={finding()} />);

    const card = screen.getByTestId("finding-card");
    expect(card).toHaveAttribute("data-verdict", "verified");
    expect(screen.getByTestId("finding-verdict")).toHaveTextContent("Verified");
    expect(screen.getByText("S3")).toBeInTheDocument();
    expect(screen.getByText(/Retry loop can mask downstream failures/)).toBeInTheDocument();
    expect(screen.getByText(/app\/pipeline\.py:11/)).toBeInTheDocument();
    expect(screen.getByText(/confirmed against facts/)).toBeInTheDocument();
  });

  it("does not render a diff link when no diff is available", () => {
    render(<FindingCard finding={finding()} />);
    expect(screen.queryByRole("button", { name: /app\/pipeline\.py:11/ })).toBeNull();
  });

  it("links citations into the diff when a handler is provided", async () => {
    const onViewInDiff = vi.fn();
    render(<FindingCard finding={finding()} onViewInDiff={onViewInDiff} />);

    await userEvent.click(screen.getByRole("button", { name: /app\/pipeline\.py:11/ }));
    expect(onViewInDiff).toHaveBeenCalledWith("app/pipeline.py", 11);
  });

  it("explains why an unverified finding was demoted", () => {
    render(
      <FindingCard
        finding={finding({
          verdict: "unverified",
          citations: [
            citation({
              supported: false,
              reason: "coverage status is unknown for this analysis",
            }),
          ],
          gate_reasons: ["all citations failed verification"],
        })}
      />,
    );

    expect(screen.getByText(/Why this is unverified/)).toBeInTheDocument();
    expect(screen.getByText("all citations failed verification")).toBeInTheDocument();
    expect(screen.getByText(/coverage status is unknown/)).toBeInTheDocument();
  });

  it("renders dependency citations with the imported module", () => {
    render(
      <FindingCard
        finding={finding({
          citations: [
            citation({
              kind: "dependency_edge",
              imported_module: "app.billing",
              line_number: 3,
            }),
          ],
        })}
      />,
    );

    expect(screen.getByText("Dependency edge")).toBeInTheDocument();
    expect(screen.getByText("imports")).toBeInTheDocument();
    expect(screen.getByText("app.billing")).toBeInTheDocument();
  });
});
