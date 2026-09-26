"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, createAnalysis } from "@/lib/api";
import type { Analysis, Finding } from "@/lib/types";
import { AnalysisStatusBadge } from "./Badges";
import { CoverageCard } from "./CoverageCard";
import { DiffViewer } from "./DiffViewer";
import { FindingCard } from "./FindingCard";
import { FACET_LABELS } from "./FacetProgress";
import { GitHubMark } from "./TopNav";

const REPORT_SECTIONS = [
  { id: "findings", label: "Findings" },
  { id: "evidence", label: "Evidence" },
  { id: "coverage", label: "Coverage" },
  { id: "diff", label: "Diff" },
] as const;
type ReportSectionId = (typeof REPORT_SECTIONS)[number]["id"];

export interface DiffFocus {
  path: string;
  line: number | null;
}

export function severityDesc(a: Finding, b: Finding): number {
  return b.severity - a.severity;
}

function shortSha(sha: string | null): string {
  return sha ? sha.slice(0, 10) : "";
}

function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function formatDescription(description: string): string {
  return description
    .replace(/\r\n?/g, "\n")
    .replace(/```[^\n]*\n?([\s\S]*?)```/g, "$1")
    .replace(/\[\[([^\]]+)\]\]\(diffhunk:\/\/[^)]*\)/g, "$1")
    .replace(/!?\[([^\]]*)\]\((?:diffhunk:\/\/|https?:\/\/)[^)]*\)/g, "$1")
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "• ")
    .replace(/^\s*>\s?/gm, "")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/__(.+?)__/g, "$1")
    .replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, "$1")
    .replace(/(?<![\w])_([^_\n]+)_(?![\w])/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/<\/?[a-z][^>]*>/gi, "")
    .trim();
}

export function AnalysisReport({ analysis }: { analysis: Analysis }) {
  const router = useRouter();
  const [focus, setFocus] = useState<DiffFocus | null>(null);
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<ReportSectionId>("findings");
  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [fileFilter, setFileFilter] = useState("all");
  const [restarting, setRestarting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [copyLabel, setCopyLabel] = useState("Copy PR link");

  const { verified, unverified } = useMemo(() => {
    const all = analysis.facets.flatMap((facet) => facet.findings);
    return {
      verified: all.filter((finding) => finding.verdict === "verified").sort(severityDesc),
      unverified: all.filter((finding) => finding.verdict === "unverified").sort(severityDesc),
    };
  }, [analysis]);

  const categories = Array.from(new Set(verified.map((finding) => finding.claim_type).filter((value): value is string => Boolean(value))));
  const files = Array.from(new Set(verified.flatMap((finding) => finding.citations.map((citation) => citation.file_path))));
  const visibleFindings = verified.filter((finding) => {
    const matchesSearch = !search || `${finding.summary} ${finding.citations.map((citation) => citation.file_path).join(" ")}`.toLowerCase().includes(search.toLowerCase());
    const matchesSeverity = severityFilter === "all" || (severityFilter === "high" ? finding.severity >= 4 : severityFilter === "medium" ? finding.severity >= 2 && finding.severity <= 3 : finding.severity <= 1);
    const matchesCategory = categoryFilter === "all" || finding.claim_type === categoryFilter;
    const matchesFile = fileFilter === "all" || finding.citations.some((citation) => citation.file_path === fileFilter);
    return matchesSearch && matchesSeverity && matchesCategory && matchesFile;
  });
  const selectedFinding = visibleFindings.find((finding) => finding.id === selectedFindingId) ?? visibleFindings[0] ?? null;

  const onViewInDiff = (path: string, line: number | null) => {
    setFocus({ path, line });
    setActiveSection("diff");
  };
  const reviewAgain = async () => {
    if (!analysis.pr.github_pr_url || restarting) return;
    setActionError(null);
    setRestarting(true);
    try {
      const created = await createAnalysis(analysis.pr.github_pr_url);
      router.push(`/analyses/${created.id}`);
    } catch (error) {
      setActionError(error instanceof ApiError ? error.detail : "Could not start another review.");
      setRestarting(false);
    }
  };
  const copyPrLink = async () => {
    if (!analysis.pr.github_pr_url) return;
    try {
      await navigator.clipboard.writeText(analysis.pr.github_pr_url);
      setCopyLabel("Copied");
      window.setTimeout(() => setCopyLabel("Copy PR link"), 1600);
    } catch {
      setCopyLabel("Copy unavailable");
      window.setTimeout(() => setCopyLabel("Copy PR link"), 1600);
    }
  };

  const repoLabel = analysis.pr.repo_full_name && analysis.pr.pr_number !== null
    ? `${analysis.pr.repo_full_name}#${analysis.pr.pr_number}`
    : null;
  const headLabel = analysis.pr.head_sha ? `head ${shortSha(analysis.pr.head_sha)}` : null;
  const selectedTab = REPORT_SECTIONS.find((section) => section.id === activeSection) ?? REPORT_SECTIONS[0];

  return (
    <div className="space-y-6" data-testid="analysis-report">
      <header className="space-y-4 border-b border-slate-200 pb-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="max-w-4xl text-xl font-bold leading-tight tracking-[-0.02em] text-slate-950">{analysis.pr.title || "Pull request analysis"}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
              {analysis.pr.github_pr_url && repoLabel ? <a href={analysis.pr.github_pr_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 font-mono font-medium text-slate-800 underline-offset-2 hover:text-brand-800 hover:underline"><GitHubMark className="h-3.5 w-3.5" />{repoLabel}</a> : repoLabel && <span className="font-mono">{repoLabel}</span>}
              {headLabel && <span className="font-mono">{headLabel}</span>}
              <span>Reviewed {formatDateTime(analysis.created_at)}</span>
              <AnalysisStatusBadge status={analysis.status} />
            </div>
          </div>
          {analysis.pr.github_pr_url && (
            <div className="flex flex-wrap items-center gap-2">
              <button type="button" onClick={() => void reviewAgain()} disabled={restarting} className="rounded-md bg-brand-700 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-800 disabled:cursor-wait disabled:opacity-70">{restarting ? "Starting…" : "Review again"}</button>
              <details className="relative">
                <summary aria-label="More review actions" className="flex h-10 w-10 cursor-pointer list-none items-center justify-center rounded-md border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"><svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor" aria-hidden="true"><circle cx="4" cy="10" r="1.5"/><circle cx="10" cy="10" r="1.5"/><circle cx="16" cy="10" r="1.5"/></svg></summary>
                <div className="absolute right-0 z-20 mt-2 w-44 rounded-lg border border-slate-200 bg-white p-1 shadow-lg shadow-slate-900/10">
                  <a href={analysis.pr.github_pr_url} target="_blank" rel="noreferrer" className="block rounded-md px-3 py-2 text-left text-xs text-slate-700 hover:bg-slate-50">View on GitHub</a>
                  <button type="button" onClick={() => void copyPrLink()} className="block w-full rounded-md px-3 py-2 text-left text-xs text-slate-700 hover:bg-slate-50">{copyLabel}</button>
                </div>
              </details>
            </div>
          )}
        </div>
        {analysis.pr.description && (
          <details data-testid="pr-description" className="group max-w-4xl rounded-lg border border-slate-200 bg-white">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-3 text-sm font-medium text-slate-800 outline-none marker:hidden transition-colors hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-700">
              <span>Pull request description</span>
              <svg viewBox="0 0 20 20" className="h-4 w-4 shrink-0 text-slate-500 transition-transform group-open:rotate-90" fill="currentColor" aria-hidden="true"><path d="M7 5l6 5-6 5V5z" /></svg>
            </summary>
            <div className="max-h-96 overflow-y-auto border-t border-slate-200 px-4 py-4"><p className="whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">{formatDescription(analysis.pr.description)}</p></div>
          </details>
        )}
        {actionError && <p role="alert" className="max-w-4xl rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{actionError}</p>}
      </header>

      {analysis.status === "failed" && <div role="alert" data-testid="analysis-error" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900"><p className="font-semibold">This analysis failed{verified.length > 0 ? " partway through" : ""}.</p><p className="mt-1">{analysis.error ?? "The backend reported an error."} {verified.length > 0 ? "Findings from the facets that completed are shown below." : "No findings were produced. Start another review from Workspace."}</p></div>}

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white" data-testid="review-sections">
        <div role="tablist" aria-label="Review sections" className="flex overflow-x-auto border-b border-slate-200 px-2 sm:px-4">
          {REPORT_SECTIONS.map((section, index) => {
            const isActive = activeSection === section.id;
            return (
              <button
                key={section.id}
                id={`report-tab-${section.id}`}
                type="button"
                role="tab"
                aria-selected={isActive}
                aria-controls="report-tabpanel"
                tabIndex={isActive ? 0 : -1}
                onClick={() => setActiveSection(section.id)}
                onKeyDown={(event) => {
                  if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
                  event.preventDefault();
                  const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? REPORT_SECTIONS.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + REPORT_SECTIONS.length) % REPORT_SECTIONS.length;
                  setActiveSection(REPORT_SECTIONS[nextIndex].id);
                  document.getElementById(`report-tab-${REPORT_SECTIONS[nextIndex].id}`)?.focus();
                }}
                className={`shrink-0 border-b-2 px-4 py-3 text-sm transition-colors ${isActive ? "border-brand-700 font-semibold text-brand-800" : "border-transparent text-slate-600 hover:text-slate-950"}`}
              >{section.label}</button>
            );
          })}
        </div>

        <div id="report-tabpanel" role="tabpanel" aria-labelledby={`report-tab-${selectedTab.id}`} tabIndex={0} className="min-w-0 outline-none">
          {activeSection === "findings" && (
            <div data-testid="analysis-brief">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
                <div><h2 className="text-base font-semibold text-slate-950">Findings register</h2><p className="mt-1 text-xs text-slate-600" data-testid="brief-summary">Evidence gate confirmed {verified.length} of {verified.length + unverified.length} claims.</p></div>
                <div className="flex gap-2 text-xs"><span className="rounded-md bg-emerald-50 px-2.5 py-1 font-medium text-emerald-800">{verified.length} verified</span><span className="rounded-md bg-amber-50 px-2.5 py-1 font-medium text-amber-800">{unverified.length} unverified</span></div>
              </div>
              <div className="grid gap-2 border-b border-slate-200 bg-white p-3 sm:grid-cols-2 xl:grid-cols-[minmax(150px,1fr)_120px_145px_145px_auto]">
                <label className="relative"><span className="sr-only">Search findings</span><svg viewBox="0 0 20 20" className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5"/><path d="m13 13 4 4" strokeLinecap="round"/></svg><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search findings…" className="h-10 w-full rounded-md border border-slate-300 bg-white pl-9 pr-3 text-xs text-slate-900 placeholder:text-slate-600 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-700/20" /></label>
                <label><span className="sr-only">Filter by severity</span><select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)} className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-xs font-medium text-slate-800"><option value="all">Any severity</option><option value="high">High · S4–S5</option><option value="medium">Medium · S2–S3</option><option value="low">Low · S0–S1</option></select></label>
                <label><span className="sr-only">Filter by category</span><select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)} className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-xs font-medium text-slate-800"><option value="all">All categories</option>{categories.map((category) => <option key={category} value={category}>{category}</option>)}</select></label>
                <label><span className="sr-only">Filter by file</span><select value={fileFilter} onChange={(event) => setFileFilter(event.target.value)} className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-xs font-medium text-slate-800"><option value="all">All files</option>{files.map((file) => <option key={file} value={file}>{file}</option>)}</select></label>
                <button type="button" onClick={() => { setSearch(""); setSeverityFilter("all"); setCategoryFilter("all"); setFileFilter("all"); }} disabled={!search && severityFilter === "all" && categoryFilter === "all" && fileFilter === "all"} className="h-10 px-2 text-xs font-semibold text-brand-800 underline decoration-brand-200 underline-offset-2 hover:decoration-brand-800 disabled:cursor-default disabled:text-slate-400 disabled:no-underline">Clear filters</button>
              </div>
              <div className="grid grid-cols-[54px_minmax(0,1fr)_96px] gap-3 border-b border-slate-200 bg-slate-50 px-5 py-2.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-600 xl:grid-cols-[54px_minmax(180px,1fr)_100px_135px_96px]"><span>Severity</span><span>Finding</span><span className="hidden xl:block">Category</span><span className="hidden xl:block">File</span><span className="text-right">Evidence</span></div>
              <div className="divide-y divide-slate-100" data-testid="verified-findings">
                {visibleFindings.length === 0 ? <p className="px-5 py-10 text-center text-sm text-slate-600" data-testid="no-findings">{verified.length === 0 ? (analysis.status === "failed" ? "No facets completed successfully." : "Nothing verified to report — the facets raised no supported issues.") : "No findings match these filters. Clear a filter or try another search."}</p> : visibleFindings.map((finding) => <button type="button" key={finding.id} data-testid="finding-card" data-verdict={finding.verdict} aria-pressed={selectedFinding?.id === finding.id} onClick={() => { setSelectedFindingId(finding.id); setActiveSection("evidence"); }} className={`grid w-full grid-cols-[54px_minmax(0,1fr)_90px] items-start gap-3 px-5 py-4 text-left transition-colors hover:bg-brand-50/50 xl:grid-cols-[54px_minmax(180px,1fr)_100px_135px_96px] ${selectedFinding?.id === finding.id ? "bg-brand-50/70" : "bg-white"}`}><span className={`w-fit rounded-md px-2 py-1 font-mono text-xs font-semibold ${finding.severity >= 4 ? "bg-rose-50 text-rose-800" : finding.severity >= 2 ? "bg-amber-50 text-amber-800" : "bg-slate-100 text-slate-700"}`}>S{finding.severity}</span><span className="min-w-0"><span className="block text-sm font-medium leading-5 text-slate-900">{finding.summary}</span><span className="mt-1 block truncate font-mono text-[11px] text-slate-600 xl:hidden">{finding.citations[0] ? `${finding.citations[0].file_path}${finding.citations[0].line_number === null ? "" : `:${finding.citations[0].line_number}`}` : "No citation attached"}</span></span><span className="hidden truncate text-xs text-slate-700 xl:block">{finding.claim_type || "—"}</span><span className="hidden truncate font-mono text-[11px] text-slate-700 xl:block">{finding.citations[0]?.file_path ?? "—"}</span><span className="text-right text-[11px] font-semibold text-emerald-800">{finding.citations.length} citation{finding.citations.length === 1 ? "" : "s"} · verified</span></button>)}
              </div>
              {unverified.length > 0 && <section className="border-t border-amber-200 bg-amber-50/40 px-5 py-4" data-testid="unverified-appendix"><h3 className="text-sm font-semibold text-amber-950">Unverified appendix <span className="font-normal text-amber-800">· {unverified.length} claim{unverified.length === 1 ? "" : "s"} held by the evidence gate</span></h3><div className="mt-3 space-y-3">{unverified.map((finding) => <FindingCard key={finding.id} finding={finding} onViewInDiff={onViewInDiff} />)}</div></section>}
            </div>
          )}

          {activeSection === "evidence" && (
            <section className="p-5 sm:p-6" data-testid="evidence-panel" aria-label="Selected finding evidence">
              {selectedFinding ? <>
                <div className="flex flex-wrap items-center gap-2"><span className={`rounded-md px-2 py-1 text-xs font-semibold ${selectedFinding.severity >= 4 ? "bg-rose-50 text-rose-800" : selectedFinding.severity >= 2 ? "bg-amber-50 text-amber-800" : "bg-slate-100 text-slate-700"}`}>Severity {selectedFinding.severity}</span><span className="rounded-md bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-800">Verified</span>{selectedFinding.claim_type && <span className="rounded-md bg-slate-100 px-2 py-1 font-mono text-xs text-slate-700">{selectedFinding.claim_type}</span>}</div>
                <h2 className="mt-3 text-lg font-semibold leading-6 text-slate-950">{selectedFinding.summary}</h2>
                <p className="mt-2 text-sm leading-6 text-slate-600">Evidence gate matched {selectedFinding.citations.length} citation{selectedFinding.citations.length === 1 ? "" : "s"} against facts from this pull request.</p>
                <h3 className="mt-6 border-b border-slate-200 pb-2 text-xs font-semibold uppercase tracking-wide text-slate-600">Evidence citations</h3>
                {selectedFinding.citations.length ? <ul className="divide-y divide-slate-100">{selectedFinding.citations.map((citation, index) => <li key={`${citation.file_path}-${citation.line_number}-${index}`} className="flex flex-wrap items-center justify-between gap-3 py-3"><div className="min-w-0 flex-1 text-sm text-slate-700"><span className="mr-2 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600">{citation.kind.replaceAll("_", " ")}</span><span className="font-mono text-xs">{citation.file_path}{citation.line_number === null ? "" : `:${citation.line_number}`}</span>{citation.imported_module && <span className="ml-2 text-xs">imports <code className="font-mono">{citation.imported_module}</code></span>}{citation.excerpt && <pre className="mt-2 overflow-x-auto rounded-md bg-slate-950 px-3 py-2 font-mono text-xs leading-5 text-slate-100"><code>{citation.excerpt}</code></pre>}<p className={`mt-1 text-xs ${citation.supported ? "text-emerald-800" : "text-amber-800"}`}>{citation.supported ? "This exact changed line was verified in the diff." : citation.reason}</p></div><button type="button" onClick={() => onViewInDiff(citation.file_path, citation.line_number)} className="shrink-0 rounded-md border border-slate-300 px-3 py-2 text-xs font-medium text-slate-800 transition-colors hover:border-brand-700 hover:text-brand-800">View in diff</button></li>)}</ul> : <p className="py-4 text-sm text-slate-600">No citations are attached to this finding.</p>}
                <details className="mt-4 rounded-lg border border-slate-200 px-4 py-3"><summary className="cursor-pointer text-sm font-medium text-slate-800">Review facet status</summary><p className="mt-2 text-xs leading-5 text-slate-600">{describeFacets(analysis)}</p></details>
              </> : <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-6 text-sm leading-6 text-slate-600">No verified finding is selected. Choose a row in Findings to inspect its evidence. Unsupported claims remain in the unverified appendix.</div>}
            </section>
          )}

          {activeSection === "coverage" && (
            <div className="grid gap-4 p-5 sm:p-6 lg:grid-cols-[minmax(0,1fr)_minmax(280px,0.7fr)]" data-testid="coverage-panel">
              <CoverageCard analysis={analysis} />
              <aside className="rounded-xl border border-slate-200 bg-slate-50 p-5"><h2 className="text-sm font-semibold text-slate-950">How verification works</h2><p className="mt-2 text-sm leading-6 text-slate-700">Verified means each citation matched a changed line, dependency edge, or parsed coverage fact. Claims the evidence gate could not support stay in the appendix with their reason.</p><p className="mt-3 text-xs text-slate-600">Coverage is tied to the PR head commit. Missing or mismatched evidence stays unknown.</p></aside>
            </div>
          )}

          {activeSection === "diff" && (
            <section className="p-5 sm:p-6" data-testid="review-diff-panel"><div className="mb-4"><h2 className="text-base font-semibold text-slate-950">Pull request diff</h2><p className="mt-1 text-xs text-slate-600">Select a file to inspect its changed lines. Evidence citations open and focus the matching location.</p></div><DiffViewer analysisId={analysis.id} focus={focus ?? (selectedFinding?.citations[0] ? { path: selectedFinding.citations[0].file_path, line: selectedFinding.citations[0].line_number } : null)} revealFocus={focus !== null} /></section>
          )}
        </div>
      </section>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-1 py-3" data-testid="coverage-provenance-rail">
        <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1 text-xs"><span className="inline-flex items-center gap-2 font-semibold text-slate-900"><span className={`h-2 w-2 rounded-full ${analysis.coverage_status === "accepted" ? "bg-emerald-600" : analysis.coverage_status === "rejected" ? "bg-amber-600" : "bg-slate-400"}`} />{analysis.coverage_status === "accepted" ? "Coverage accepted" : analysis.coverage_status === "rejected" ? "Coverage rejected" : "Coverage unavailable"}</span><span className="font-mono text-slate-700">head {shortSha(analysis.pr.head_sha)}</span><span className="text-slate-700">{verified.length} verified · {unverified.length} unverified</span></div>
        <button type="button" onClick={() => setActiveSection("coverage")} className="shrink-0 text-xs font-semibold text-brand-800 underline decoration-brand-200 underline-offset-2 hover:decoration-brand-800">View provenance</button>
      </div>
    </div>
  );
}

function describeFacets(analysis: Analysis): string {
  return analysis.facets
    .slice()
    .sort((a, b) => a.kind.localeCompare(b.kind))
    .map((facet) => `${FACET_LABELS[facet.kind]?.name ?? facet.kind}: ${facet.status}`)
    .join(" · ");
}
