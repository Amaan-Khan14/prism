import type { FacetKind, FacetStatus } from "@/lib/types";
import { FacetStatusBadge } from "./Badges";

export const FACET_ORDER: FacetKind[] = [
  "intent_vs_spec",
  "cross_file_impact",
  "test_coverage_gaps",
  "risk_hazards",
];

export const FACET_LABELS: Record<FacetKind, { name: string; action: string; description: string }> = {
  intent_vs_spec: {
    name: "Intent vs spec",
    action: "Analyzing intent against the PR description",
    description: "Checks what the change claims to do against what the diff does.",
  },
  cross_file_impact: {
    name: "Cross-file impact",
    action: "Tracing cross-file dependencies",
    description: "Follows import and call edges touched by the change.",
  },
  test_coverage_gaps: {
    name: "Test coverage gaps",
    action: "Checking test coverage on changed lines",
    description: "Flags changed behavior that CI coverage does not exercise.",
  },
  risk_hazards: {
    name: "Risk hazards",
    action: "Scanning for transaction, auth, and concurrency hazards",
    description: "Looks for higher-stakes failure modes in the changed code.",
  },
};

export interface FacetProgressInput {
  kind: FacetKind;
  status: FacetStatus;
}

/**
 * Live progress for the four review facets. `computeFacts` is shown while
 * every facet is still queued, mirroring the backend pipeline order.
 */
export function FacetProgress({ facets }: { facets: FacetProgressInput[] }) {
  const byKind = new Map(facets.map((facet) => [facet.kind, facet.status]));
  const allQueued = facets.every((facet) => facet.status === "pending");

  return (
    <ol className="space-y-2" data-testid="facet-progress">
      {allQueued && (
        <li className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3">
          <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-slate-950" />
          <div className="min-w-0">
            <p className="text-sm text-slate-900">Computing deterministic facts</p>
            <p className="text-xs text-slate-500">
              Extracting changed lines, dependency edges, and coverage for this diff.
            </p>
          </div>
        </li>
      )}
      {FACET_ORDER.map((kind) => {
        const status = byKind.get(kind) ?? "pending";
        const label = FACET_LABELS[kind];
        return (
          <li
            key={kind}
            data-testid={`facet-${kind}`}
            className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3"
          >
            <span
              className={`h-2 w-2 shrink-0 rounded-full ${
                status === "running"
                  ? "animate-pulse bg-slate-950"
                  : status === "completed"
                    ? "bg-emerald-500"
                    : status === "failed"
                      ? "bg-rose-500"
                      : "bg-slate-300"
              }`}
            />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-0.5">
                <p className="text-sm text-slate-900">{label.name}</p>
                <FacetStatusBadge status={status} />
              </div>
              <p className="text-xs text-slate-500">{label.description}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
