import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FacetProgress } from "@/components/FacetProgress";
import { ALL_FACET_KINDS, facetRow } from "../fixtures";

describe("FacetProgress", () => {
  it("shows the facts-computation stage while every facet is queued", () => {
    render(
      <FacetProgress facets={ALL_FACET_KINDS.map((kind) => ({ kind, status: "pending" }))} />,
    );

    expect(screen.getByText("Computing deterministic facts")).toBeInTheDocument();
    const facets = screen.getAllByTestId("facet-status");
    expect(facets).toHaveLength(4);
    facets.forEach((facet) => expect(facet).toHaveTextContent("Queued"));
  });

  it("renders the four review facets in pipeline order", () => {
    render(<FacetProgress facets={ALL_FACET_KINDS.map((kind) => ({ kind, status: "running" }))} />);

    expect(screen.getByText("Intent vs spec")).toBeInTheDocument();
    expect(screen.getByText("Cross-file impact")).toBeInTheDocument();
    expect(screen.getByText("Test coverage gaps")).toBeInTheDocument();
    expect(screen.getByText("Risk hazards")).toBeInTheDocument();
    screen.getAllByTestId("facet-status").forEach((facet) => {
      expect(facet).toHaveTextContent("Running");
    });
  });

  it("marks completed and failed facets distinctly", () => {
    render(
      <FacetProgress
        facets={[
          { kind: "intent_vs_spec", status: "completed" },
          { kind: "cross_file_impact", status: "failed" },
          { kind: "test_coverage_gaps", status: "pending" },
          { kind: "risk_hazards", status: "pending" },
        ]}
      />,
    );

    expect(screen.getByTestId("facet-intent_vs_spec")).toHaveTextContent("Done");
    expect(screen.getByTestId("facet-cross_file_impact")).toHaveTextContent("Failed");
  });

  it("handles the backend facet rows directly", () => {
    render(
      <FacetProgress
        facets={[
          facetRow("intent_vs_spec", "completed"),
          facetRow("risk_hazards", "running"),
        ].map(({ kind, status }) => ({ kind, status }))}
      />,
    );

    expect(screen.queryByText("Computing deterministic facts")).toBeNull();
    expect(screen.getByTestId("facet-risk_hazards")).toHaveTextContent("Running");
  });
});
