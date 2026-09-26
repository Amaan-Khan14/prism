"use client";

import { useEffect, useMemo, useState } from "react";
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
  { id: "findings-list", label: "Findings" },
  { id: "evidence-inspector", label: "Evidence" },
  { id: "coverage-rail", label: "Coverage" },
  { id: "diff-section", label: "Diff" },
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

/**
 * The full read-out for a finished (or partially finished) analysis:
 * risk-ordered brief, verified findings, unverified appendix, coverage
 * provenance, verification state, and the linked diff.
 */
export function AnalysisReport({ analysis }: { analysis: Analysis }) {
  const router = useRouter();
  const [focus, setFocus] = useState<DiffFocus | null>(null);
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);
  const [inspectorTab, setInspectorTab] = useState<"evidence" | "details" | "guidance">("evidence");
  const [activeSection, setActiveSection] = useState<ReportSectionId>("findings-list");
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
      verified: all.filter((f) => f.verdict === "verified").sort(severityDesc),
      unverified: all.filter((f) => f.verdict === "unverified").sort(severityDesc),
    };
  }, [analysis]);

  const onViewInDiff = (path: string, line: number | null) => {
    setFocus({ path, line });
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

  useEffect(() => {
    const syncSection = () => {
      const hash = window.location.hash.slice(1);
      if (REPORT_SECTIONS.some((section) => section.id === hash)) {
        setActiveSection(hash as ReportSectionId);
      }
    };
    syncSection();
    window.addEventListener("hashchange", syncSection);
    return () => window.removeEventListener("hashchange", syncSection);
  }, []);

  const repoLabel =
    analysis.pr.repo_full_name && analysis.pr.pr_number !== null
      ? `${analysis.pr.repo_full_name}#${analysis.pr.pr_number}`
      : null;
  const headLabel = analysis.pr.head_sha ? `head ${shortSha(analysis.pr.head_sha)}` : null;

  return (
    <div className="space-y-6" data-testid="analysis-report">
      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(310px,0.65fr)]">
        <div className="min-w-0 space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-5">
        <div className="min-w-0">
          <h1 className="max-w-4xl text-xl font-bold leading-tight tracking-[-0.02em] text-slate-950">{analysis.pr.title || "Pull request analysis"}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
            {analysis.pr.github_pr_url && repoLabel ? <a href={analysis.pr.github_pr_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 font-mono font-medium text-slate-800 underline-offset-2 hover:text-brand-800 hover:underline"><GitHubMark className="h-3.5 w-3.5" />{repoLabel}</a> : repoLabel && <span className="font-mono">{repoLabel}</span>}
            {headLabel && <span className="font-mono">{headLabel}</span>}
            <span>Reviewed {formatDateTime(analysis.created_at)}</span>
            <AnalysisStatusBadge status={analysis.status} />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {analysis.pr.github_pr_url && <><button type="button" onClick={() => void reviewAgain()} disabled={restarting} className="rounded-md bg-brand-700 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-800 disabled:cursor-wait disabled:opacity-70">{restarting ? "Starting…" : "Review again"}</button><details className="relative"><summary aria-label="More review actions" className="flex h-10 w-10 cursor-pointer list-none items-center justify-center rounded-md border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"><svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor" aria-hidden="true"><circle cx="4" cy="10" r="1.5"/><circle cx="10" cy="10" r="1.5"/><circle cx="16" cy="10" r="1.5"/></svg></summary><div className="absolute right-0 z-20 mt-2 w-44 rounded-lg border border-slate-200 bg-white p-1 shadow-lg shadow-slate-900/10"><a href={analysis.pr.github_pr_url} target="_blank" rel="noreferrer" className="block rounded-md px-3 py-2 text-left text-xs text-slate-700 hover:bg-slate-50">View on GitHub</a><button type="button" onClick={() => void copyPrLink()} className="block w-full rounded-md px-3 py-2 text-left text-xs text-slate-700 hover:bg-slate-50">{copyLabel}</button></div></details></>}
        </div>
        {analysis.pr.description && <p className="basis-full max-w-4xl text-sm leading-6 text-slate-700">{analysis.pr.description}</p>}
        {actionError && <p role="alert" className="basis-full rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{actionError}</p>}
      </header>

      {analysis.status === "failed" && <div role="alert" data-testid="analysis-error" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900"><p className="font-semibold">This analysis failed{verified.length > 0 ? " partway through" : ""}.</p><p className="mt-1">{analysis.error ?? "The backend reported an error."} {verified.length > 0 ? "Findings from the facets that completed are shown below." : "No findings were produced. You can submit the PR again from Overview."}</p></div>}

      <section id="findings-list" className="scroll-mt-20" data-testid="analysis-brief">
          <nav aria-label="Review sections" className="flex gap-1 overflow-x-auto border-b border-slate-200 text-sm">
            {REPORT_SECTIONS.map((section) => {
              const isActive = activeSection === section.id;
              return <a key={section.id} href={`#${section.id}`} aria-current={isActive ? "location" : undefined} onClick={() => setActiveSection(section.id)} className={`shrink-0 border-b-2 px-3 py-3 ${isActive ? "border-brand-700 font-semibold text-brand-800" : "border-transparent text-slate-600 hover:text-slate-950"}`}>{section.label}</a>;
            })}
          </nav>
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm shadow-slate-900/[0.025]">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4"><div><h2 className="text-base font-semibold text-slate-950">Findings register</h2><p className="mt-1 text-xs text-slate-600" data-testid="brief-summary">Evidence gate confirmed {verified.length} of {verified.length + unverified.length} claims.</p></div><div className="flex gap-2 text-xs"><span className="rounded-md bg-emerald-50 px-2.5 py-1 font-medium text-emerald-800">{verified.length} verified</span><span className="rounded-md bg-amber-50 px-2.5 py-1 font-medium text-amber-800">{unverified.length} unverified</span></div></div>
          <div className="grid gap-2 border-b border-slate-200 bg-white p-3 sm:grid-cols-2 xl:grid-cols-[minmax(150px,1fr)_120px_145px_145px_auto]">
            <label className="relative"><span className="sr-only">Search findings</span><svg viewBox="0 0 20 20" className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5"/><path d="m13 13 4 4" strokeLinecap="round"/></svg><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search findings…" className="h-10 w-full rounded-md border border-slate-300 bg-white pl-9 pr-3 text-xs text-slate-900 placeholder:text-slate-600 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-700/20" /></label>
            <label><span className="sr-only">Filter by severity</span><select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)} className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-xs font-medium text-slate-800"><option value="all">Any severity</option><option value="high">High · S4–S5</option><option value="medium">Medium · S2–S3</option><option value="low">Low · S0–S1</option></select></label>
            <label><span className="sr-only">Filter by category</span><select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)} className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-xs font-medium text-slate-800"><option value="all">All categories</option>{categories.map((category) => <option key={category} value={category}>{category}</option>)}</select></label>
            <label><span className="sr-only">Filter by file</span><select value={fileFilter} onChange={(event) => setFileFilter(event.target.value)} className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-xs font-medium text-slate-800"><option value="all">All files</option>{files.map((file) => <option key={file} value={file}>{file}</option>)}</select></label>
            <button type="button" onClick={() => { setSearch(""); setSeverityFilter("all"); setCategoryFilter("all"); setFileFilter("all"); }} disabled={!search && severityFilter === "all" && categoryFilter === "all" && fileFilter === "all"} className="h-10 px-2 text-xs font-semibold text-brand-800 underline decoration-brand-200 underline-offset-2 hover:decoration-brand-800 disabled:cursor-default disabled:text-slate-400 disabled:no-underline">Clear filters</button>
          </div>
          <div className="grid grid-cols-[54px_minmax(0,1fr)_96px] gap-3 border-b border-slate-200 bg-slate-50 px-5 py-2.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-600 xl:grid-cols-[54px_minmax(180px,1fr)_100px_135px_96px]"><span>Severity</span><span>Finding</span><span className="hidden xl:block">Category</span><span className="hidden xl:block">File</span><span className="text-right">Evidence</span></div>
          <div className="divide-y divide-slate-100" data-testid="verified-findings">
            {visibleFindings.length === 0 ? <p className="px-5 py-10 text-center text-sm text-slate-600" data-testid="no-findings">{verified.length === 0 ? (analysis.status === "failed" ? "No facets completed successfully." : "Nothing verified to report — the facets raised no supported issues.") : "No findings match these filters. Clear a filter or try another search."}</p> : visibleFindings.map((finding) => <button type="button" key={finding.id} data-testid="finding-card" data-verdict={finding.verdict} aria-pressed={selectedFinding?.id === finding.id} onClick={() => setSelectedFindingId(finding.id)} className={`grid w-full grid-cols-[54px_minmax(0,1fr)_90px] items-start gap-3 px-5 py-4 text-left transition-colors hover:bg-brand-50/50 xl:grid-cols-[54px_minmax(180px,1fr)_100px_135px_96px] ${selectedFinding?.id === finding.id ? "bg-brand-50/70" : "bg-white"}`}><span className={`w-fit rounded-md px-2 py-1 font-mono text-xs font-semibold ${finding.severity >= 4 ? "bg-rose-50 text-rose-800" : finding.severity >= 2 ? "bg-amber-50 text-amber-800" : "bg-slate-100 text-slate-700"}`}>S{finding.severity}</span><span className="min-w-0"><span className="block text-sm font-medium leading-5 text-slate-900">{finding.summary}</span><span className="mt-1 block truncate font-mono text-[11px] text-slate-600 xl:hidden">{finding.citations[0] ? `${finding.citations[0].file_path}${finding.citations[0].line_number === null ? "" : `:${finding.citations[0].line_number}`}` : "No citation attached"}</span></span><span className="hidden truncate text-xs text-slate-700 xl:block">{finding.claim_type || "—"}</span><span className="hidden truncate font-mono text-[11px] text-slate-700 xl:block">{finding.citations[0]?.file_path ?? "—"}</span><span className="text-right text-[11px] font-semibold text-emerald-800">{finding.citations.length} citation{finding.citations.length === 1 ? "" : "s"} · verified</span></button>)}
          </div>
          {unverified.length > 0 && <div className="border-t border-amber-200 bg-amber-50/60 px-5 py-3 text-xs text-amber-900">{unverified.length} additional claim{unverified.length === 1 ? "" : "s"} held in the unverified appendix below.</div>}
        </div>
      </section>
        </div>

        <aside id="evidence-inspector" className="scroll-mt-20 rounded-xl border border-slate-200 bg-white shadow-sm shadow-slate-900/[0.025] xl:sticky xl:top-4" aria-label="Evidence inspector">
          {selectedFinding ? <>
            <div className="border-b border-slate-200 px-5 py-4" id="selected-finding-header">
              <div className="flex flex-wrap items-center gap-2"><span className={`rounded-md px-2 py-1 text-xs font-semibold ${selectedFinding.severity >= 4 ? "bg-rose-50 text-rose-800" : selectedFinding.severity >= 2 ? "bg-amber-50 text-amber-800" : "bg-slate-100 text-slate-700"}`}>{selectedFinding.severity >= 4 ? "High" : selectedFinding.severity >= 2 ? "Medium" : "Low"}</span><span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-800"><svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="currentColor" aria-hidden="true"><path d="M8 0a8 8 0 1 0 0 16A8 8 0 0 0 8 0Zm3.5 5.8-4 4.3a.8.8 0 0 1-1.2 0L4.5 8.2l1.1-1.1 1.3 1.3 3.4-3.7 1.2 1.1Z"/></svg>Verified</span></div>
              <h2 className="mt-3 text-base font-semibold leading-5 text-slate-950">{selectedFinding.summary}</h2>
            </div>
            <div role="tablist" aria-label="Finding details" className="flex gap-4 border-b border-slate-200 px-5 text-xs font-medium">
              {(["evidence", "details", "guidance"] as const).map((tab) => {
                const labels = { evidence: "Evidence", details: "Details", guidance: "Guidance" };
                const isActive = inspectorTab === tab;
                return <button key={tab} id={`finding-tab-${tab}`} type="button" role="tab" aria-selected={isActive} aria-controls={`finding-panel-${tab}`} onClick={() => setInspectorTab(tab)} className={`border-b-2 py-3 ${isActive ? "border-brand-700 text-brand-800" : "border-transparent text-slate-600 hover:text-slate-950"}`}>{labels[tab]}</button>;
              })}
            </div>
            {inspectorTab === "evidence" && <section id="finding-panel-evidence" role="tabpanel" aria-labelledby="finding-tab-evidence" className="px-5 py-4"><p className="text-[10px] font-semibold uppercase tracking-wide text-slate-600">Summary</p>{selectedFinding.claim_type && <p className="mt-2 text-xs font-semibold text-slate-800">{selectedFinding.claim_type}</p>}<p className="mt-1 text-xs leading-5 text-slate-700">{selectedFinding.summary}</p></section>}
            {inspectorTab === "details" && <section id="finding-panel-details" role="tabpanel" aria-labelledby="finding-tab-details" className="border-b border-slate-200 px-5 py-4"><p className="text-xs font-semibold text-slate-950">Why this is flagged</p><p className="mt-1 text-xs leading-5 text-slate-700">The evidence gate matched {selectedFinding.citations.length} citation{selectedFinding.citations.length === 1 ? "" : "s"} to facts from this pull request.</p><ul className="mt-2 space-y-1">{selectedFinding.citations.map((citation, index) => <li key={`${citation.file_path}-${citation.line_number}-${index}`} className="flex items-start gap-2 text-[11px] leading-4 text-slate-700"><span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-600"/><span><button type="button" onClick={() => onViewInDiff(citation.file_path, citation.line_number)} className="font-mono text-brand-800 underline decoration-brand-200 underline-offset-2 hover:decoration-brand-800">{citation.file_path}{citation.line_number === null ? "" : `:${citation.line_number}`}</button>{citation.imported_module && <> imports <span className="font-mono">{citation.imported_module}</span></>}{!citation.supported && <span className="text-amber-900"> · {citation.reason}</span>}</span></li>)}</ul></section>}
            {inspectorTab === "guidance" && <section id="finding-panel-guidance" role="tabpanel" aria-labelledby="finding-tab-guidance" className="border-b border-slate-200 px-5 py-4"><p className="text-xs font-semibold text-slate-950">Review guidance</p><p className="mt-1 text-xs leading-5 text-slate-700">Use the cited diff and dependency context to assess the change before choosing a corrective action.</p></section>}
            <div id="diff-section" className="max-h-[290px] scroll-mt-20 overflow-y-auto border-y border-slate-200 p-4"><p className="mb-3 text-[10px] font-semibold uppercase tracking-wide text-slate-600">Cited diff</p><DiffViewer analysisId={analysis.id} focus={focus ?? (selectedFinding.citations[0] ? { path: selectedFinding.citations[0].file_path, line: selectedFinding.citations[0].line_number } : null)} revealFocus={focus !== null} /></div>
            <div className="m-4 flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-3"><svg viewBox="0 0 16 16" className="mt-0.5 h-4 w-4 shrink-0 text-emerald-800" fill="currentColor" aria-hidden="true"><path d="M8 0a8 8 0 1 0 0 16A8 8 0 0 0 8 0Zm3.5 5.8-4 4.3a.8.8 0 0 1-1.2 0L4.5 8.2l1.1-1.1 1.3 1.3 3.4-3.7 1.2 1.1Z"/></svg><div><p className="text-xs font-semibold text-emerald-900">Verified against PR facts</p><p className="mt-1 text-[11px] leading-4 text-emerald-900">{selectedFinding.citations.length} citation{selectedFinding.citations.length === 1 ? "" : "s"} confirmed. Unsupported claims remain in the appendix.</p><p className="mt-2 text-[10px] leading-4 text-emerald-900/90">{describeFacets(analysis)}</p></div></div>
          </> : <div className="p-5"><h2 className="text-base font-semibold text-slate-950">Evidence inspector</h2><p className="mt-3 text-sm leading-6 text-slate-600">The report has no verified findings to inspect. Unsupported claims remain visible in the appendix.</p><div id="diff-section" className="mt-4"><DiffViewer analysisId={analysis.id} focus={focus} /></div></div>}
        </aside>
      </div>

      <section id="coverage-rail" className="grid scroll-mt-20 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,0.7fr)]"><CoverageCard analysis={analysis} /><aside className="rounded-xl border border-slate-200 bg-white p-5"><h2 className="text-sm font-semibold text-slate-950">How verification works</h2><p className="mt-2 text-sm leading-6 text-slate-700">Verified means each citation matched a changed line, dependency edge, or parsed coverage fact. Claims the evidence gate could not support stay in the appendix with their reason.</p><p className="mt-3 text-xs text-slate-600">Coverage is tied to the PR head commit. Missing or mismatched evidence stays unknown.</p></aside></section>

      {unverified.length > 0 && (
        <section data-testid="unverified-appendix">
          <h2 className="mb-3 text-sm font-semibold text-zinc-950">
            Unverified appendix
            <span className="ml-2 text-xs font-normal text-amber-700">
              held out by the evidence gate
            </span>
          </h2>
          <div className="space-y-3">
            {unverified.map((finding) => (
              <FindingCard key={finding.id} finding={finding} onViewInDiff={onViewInDiff} />
            ))}
          </div>
        </section>
      )}

      <div className="-mx-5 mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-white/95 px-5 py-3 sm:-mx-6 sm:px-6 xl:sticky xl:bottom-0 xl:z-20 xl:shadow-[0_-8px_28px_-24px_rgba(15,23,42,0.35)] xl:backdrop-blur" data-testid="coverage-provenance-rail">
        <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1 text-xs">
          <span className="inline-flex items-center gap-2 font-semibold text-slate-900"><span className={`h-2 w-2 rounded-full ${analysis.coverage_status === "accepted" ? "bg-emerald-600" : analysis.coverage_status === "rejected" ? "bg-amber-600" : "bg-slate-400"}`} />{analysis.coverage_status === "accepted" ? "Coverage accepted" : analysis.coverage_status === "rejected" ? "Coverage rejected" : "Coverage unavailable"}</span>
          <span className="font-mono text-slate-700">head {shortSha(analysis.pr.head_sha)}</span>
          <span className="text-slate-700">{verified.length} verified · {unverified.length} unverified</span>
        </div>
        <a href="#coverage-rail" className="shrink-0 text-xs font-semibold text-brand-800 underline decoration-brand-200 underline-offset-2 hover:decoration-brand-800">View provenance</a>
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
