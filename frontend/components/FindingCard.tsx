"use client";

import { SeverityChip, VerdictBadge } from "./Badges";
import type { Citation, Finding } from "@/lib/types";

const kindLabels: Record<Citation["kind"], string> = {
  added_line: "Changed line",
  dependency_edge: "Dependency edge",
  coverage: "Coverage",
};

interface FindingCardProps {
  finding: Finding;
  /** Present when the analysis has a diff the citation can link into. */
  onViewInDiff?: (path: string, line: number | null) => void;
}

export function FindingCard({ finding, onViewInDiff }: FindingCardProps) {
  return (
    <article
      data-testid="finding-card"
      data-verdict={finding.verdict}
      className="rounded-xl border border-slate-200 bg-white p-4 sm:p-5"
    >
      <div className="flex flex-wrap items-center gap-2">
        <VerdictBadge verdict={finding.verdict} />
        <SeverityChip severity={finding.severity} />
        {finding.claim_type && (
          <span className="rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-600">
            {finding.claim_type}
          </span>
        )}
      </div>
      <p className="mt-2.5 text-sm leading-6 text-slate-800">{finding.summary}</p>

      {finding.citations.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {finding.citations.map((citation, index) => (
            <CitationRow
              key={index}
              citation={citation}
              onViewInDiff={onViewInDiff}
            />
          ))}
        </ul>
      )}

      {!finding.citations.some((citation) => citation.supported) &&
        finding.gate_reasons.length > 0 && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-800">
              Why this is unverified
            </p>
            <ul className="mt-1 list-inside list-disc text-xs text-amber-800/80">
              {finding.gate_reasons.map((reason, index) => (
                <li key={index}>{reason}</li>
              ))}
            </ul>
          </div>
        )}
    </article>
  );
}

function CitationRow({
  citation,
  onViewInDiff,
}: {
  citation: Citation;
  onViewInDiff?: (path: string, line: number | null) => void;
}) {
  const hasDiffLink = Boolean(onViewInDiff);
  const lineLabel =
    citation.line_number !== null ? `:${citation.line_number}` : "";
  const location = `${citation.file_path}${lineLabel}`;

  return (
    <li className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs" data-testid="citation-row">
      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-500">
        {kindLabels[citation.kind] ?? citation.kind}
      </span>
      {hasDiffLink ? (
        <button
          type="button"
          onClick={() => onViewInDiff?.(citation.file_path, citation.line_number)}
          className="font-mono text-slate-950 underline decoration-slate-300 underline-offset-2 transition-colors hover:decoration-slate-950"
          title="Show this line in the diff"
        >
          {location}
        </button>
      ) : (
        <span className="font-mono text-slate-700">{location}</span>
      )}
      {citation.imported_module && (
        <span className="font-mono text-slate-500">
          imports <span className="text-slate-800">{citation.imported_module}</span>
        </span>
      )}
      <span
        className={
          citation.supported
            ? "text-emerald-600"
            : "text-amber-600"
        }
        title={citation.reason}
      >
        {citation.supported ? "✓ confirmed against facts" : `⚠ ${citation.reason}`}
      </span>
    </li>
  );
}
