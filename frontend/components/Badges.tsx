import type { AnalysisStatus, FacetStatus, FindingVerdict } from "@/lib/types";

const analysisStyles: Record<AnalysisStatus, { label: string; className: string; dot: string }> = {
  pending: {
    label: "Pending",
    className: "bg-zinc-100 text-zinc-600 ring-zinc-500/20",
    dot: "bg-zinc-400",
  },
  running: {
    label: "Running",
    className: "bg-zinc-950 text-white ring-zinc-950",
    dot: "bg-white animate-pulse",
  },
  completed: {
    label: "Completed",
    className: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    dot: "bg-emerald-500",
  },
  failed: {
    label: "Failed",
    className: "bg-rose-50 text-rose-700 ring-rose-600/20",
    dot: "bg-rose-500",
  },
};

export function AnalysisStatusBadge({ status }: { status: AnalysisStatus }) {
  const style = analysisStyles[status];
  return (
    <span
      data-testid="analysis-status"
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${style.className}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
      {style.label}
    </span>
  );
}

const facetStatusLabels: Record<FacetStatus, string> = {
  pending: "Queued",
  running: "Running",
  completed: "Done",
  failed: "Failed",
};

export function FacetStatusBadge({ status }: { status: FacetStatus }) {
  const styles: Record<FacetStatus, string> = {
    pending: "text-zinc-400",
    running: "text-zinc-950 animate-pulse",
    completed: "text-emerald-600",
    failed: "text-rose-600",
  };
  return (
    <span
      data-testid="facet-status"
      className={`inline-flex items-center gap-1.5 text-xs font-medium ${styles[status]}`}
    >
      <StatusDot status={status} />
      {facetStatusLabels[status]}
    </span>
  );
}

function StatusDot({ status }: { status: FacetStatus }) {
  const colors: Record<FacetStatus, string> = {
    pending: "bg-zinc-300",
    running: "bg-zinc-950",
    completed: "bg-emerald-500",
    failed: "bg-rose-500",
  };
  return <span className={`h-2 w-2 rounded-full ${colors[status]}`} />;
}

export function VerdictBadge({ verdict }: { verdict: FindingVerdict }) {
  const verified = verdict === "verified";
  return (
    <span
      data-testid="finding-verdict"
      title={
        verified
          ? "Every citation was checked against deterministic PR facts."
          : "At least one citation could not be confirmed against PR facts."
      }
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ring-1 ring-inset ${
        verified
          ? "bg-emerald-50 text-emerald-700 ring-emerald-600/20"
          : "bg-amber-50 text-amber-700 ring-amber-600/20"
      }`}
    >
      {verified ? "Verified" : "Unverified"}
    </span>
  );
}

export function SeverityChip({ severity }: { severity: number }) {
  const level = Math.max(0, Math.min(5, severity));
  const styles =
    level >= 4
      ? "bg-rose-50 text-rose-700 ring-rose-600/20"
      : level >= 2
        ? "bg-amber-50 text-amber-700 ring-amber-600/20"
        : "bg-zinc-100 text-zinc-600 ring-zinc-500/20";
  return (
    <span
      title={`Severity ${level} out of 5`}
      className={`inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[11px] ring-1 ring-inset ${styles}`}
    >
      S{level}
    </span>
  );
}
