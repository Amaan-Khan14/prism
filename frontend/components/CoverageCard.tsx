import type { Analysis } from "@/lib/types";

function shortSha(sha: string | null): string {
  return sha ? `${sha.slice(0, 10)}…` : "—";
}

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function ProvenanceRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap justify-between gap-x-4 gap-y-0.5 py-1">
      <span className="text-xs text-slate-500">{label}</span>
      <span className="text-right font-mono text-xs text-slate-800">{children}</span>
    </div>
  );
}

const statusMeta = {
  accepted: {
    title: "Coverage artifact accepted",
    note: "The CI coverage report matched this PR's exact head commit and was parsed successfully.",
    className: "border-emerald-200 bg-emerald-50",
    heading: "text-emerald-800",
  },
  rejected: {
    title: "Coverage artifact rejected",
    note: "A coverage report was uploaded for this commit, but it failed validation. Coverage is treated as unknown.",
    className: "border-amber-200 bg-amber-50",
    heading: "text-amber-800",
  },
  none: {
    title: "No coverage artifact",
    note: "No CI coverage report was supplied for this commit, so test-coverage claims are limited to what the diff itself shows.",
    className: "border-slate-200 bg-white",
    heading: "text-slate-900",
  },
  unknown: {
    title: "Coverage status unknown",
    note: "This analysis predates coverage provenance tracking, so no coverage information is available.",
    className: "border-slate-200 bg-white",
    heading: "text-slate-900",
  },
} as const;

export function CoverageCard({ analysis }: { analysis: Analysis }) {
  const status = analysis.coverage_status ?? "unknown";
  const meta = statusMeta[status];

  return (
    <section
      data-testid="coverage-card"
      data-coverage-status={status}
      className={`rounded-xl border p-4 sm:p-5 ${meta.className}`}
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className={`text-sm font-semibold ${meta.heading}`}>{meta.title}</h3>
        {analysis.coverage_format && (
          <span className="rounded bg-white/60 px-1.5 py-0.5 font-mono text-[11px] uppercase text-slate-600 ring-1 ring-inset ring-slate-200">
            {analysis.coverage_format}
          </span>
        )}
      </div>
      <p className="mt-1.5 text-xs leading-5 text-slate-600">{meta.note}</p>

      <div className="mt-3 divide-y divide-slate-200/80">
        <ProvenanceRow label="CI provider">
          {analysis.coverage_ci_provider ?? "—"}
        </ProvenanceRow>
        <ProvenanceRow label="Commit SHA">{shortSha(analysis.coverage_commit_sha)}</ProvenanceRow>
        <ProvenanceRow label="Actions run">
          {analysis.coverage_run_id
            ? `#${analysis.coverage_run_id}${analysis.coverage_run_attempt ? ` (attempt ${analysis.coverage_run_attempt})` : ""}`
            : "—"}
        </ProvenanceRow>
        <ProvenanceRow label="Artifact">
          {analysis.coverage_artifact_name ?? "—"}
        </ProvenanceRow>
        <ProvenanceRow label="Files in report">
          {analysis.coverage_file_count ?? "—"}
        </ProvenanceRow>
        {status === "accepted" && (
          <ProvenanceRow label="Parsed at">
            {formatDateTime(analysis.coverage_parsed_at)}
          </ProvenanceRow>
        )}
        {status === "rejected" && analysis.coverage_rejection_reason && (
          <ProvenanceRow label="Rejection reason">
            {analysis.coverage_rejection_reason}
          </ProvenanceRow>
        )}
      </div>

      {analysis.coverage_parser_warnings && analysis.coverage_parser_warnings.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-slate-500 hover:text-slate-800">
            {analysis.coverage_parser_warnings.length} parser warning
            {analysis.coverage_parser_warnings.length === 1 ? "" : "s"}
          </summary>
          <ul className="mt-1 list-inside list-disc text-xs text-slate-500">
            {analysis.coverage_parser_warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
