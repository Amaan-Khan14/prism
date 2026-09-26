"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ApiError, listAnalyses } from "@/lib/api";
import { AnalysisStatusBadge } from "@/components/Badges";
import { useAuth } from "@/components/AuthProvider";
import type { AnalysisListItem } from "@/lib/types";

const ALL_REPOSITORIES = "all";
const UNLINKED_REPOSITORY = "__unlinked__";

function reviewName(item: AnalysisListItem) {
  if (item.pr.repo_full_name && item.pr.pr_number !== null) return `${item.pr.repo_full_name}#${item.pr.pr_number}`;
  return item.pr.github_pr_url || item.pr.title || "Pull request review";
}

export default function ReviewsPage() {
  const { status } = useAuth();
  const [reviews, setReviews] = useState<AnalysisListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [repositoryFilter, setRepositoryFilter] = useState(ALL_REPOSITORIES);

  const loadReviews = useCallback(async () => {
    setError(null);
    try {
      setReviews(await listAnalyses());
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.detail : "Could not load your reviews.");
    }
  }, []);

  useEffect(() => {
    if (status === "signedIn") void loadReviews();
  }, [loadReviews, status]);

  if (status === "loading") return <div className="h-40 animate-pulse rounded-xl bg-slate-100" aria-label="Loading account" />;
  if (status !== "signedIn") {
    return <section className="border-y border-slate-200 py-10"><h1 className="text-3xl font-semibold tracking-[-0.03em] text-slate-950">Reviews</h1><p className="mt-3 text-sm text-slate-600">Sign in with GitHub to see your submitted reviews.</p><a href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/auth/github/login`} className="mt-5 inline-flex rounded-lg bg-brand-700 px-5 py-3 text-sm font-semibold text-white hover:bg-brand-800">Sign in with GitHub</a></section>;
  }

  const repositories = Array.from(new Set((reviews ?? []).map((item) => item.pr.repo_full_name).filter((name): name is string => Boolean(name)))).sort((a, b) => a.localeCompare(b));
  const hasUnlinkedReviews = (reviews ?? []).some((item) => !item.pr.repo_full_name);
  const filteredReviews = (reviews ?? []).filter((item) => {
    if (repositoryFilter === ALL_REPOSITORIES) return true;
    if (repositoryFilter === UNLINKED_REPOSITORY) return !item.pr.repo_full_name;
    return item.pr.repo_full_name === repositoryFilter;
  });

  return (
    <div className="space-y-6" data-testid="reviews-page">
      <header className="flex flex-col gap-5 border-b border-slate-200 pb-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-[-0.03em] text-slate-950">Reviews</h1>
          <p className="mt-2 text-sm text-slate-600">Open an in-progress analysis or return to a completed evidence brief.</p>
        </div>
        <label className="flex shrink-0 flex-col gap-1.5 text-xs font-medium text-slate-600 sm:min-w-56">
          Repository
          <select
            aria-label="Filter reviews by repository"
            value={repositoryFilter}
            onChange={(event) => setRepositoryFilter(event.target.value)}
            disabled={reviews === null || (repositories.length === 0 && !hasUnlinkedReviews)}
            className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:bg-slate-100 disabled:text-slate-500"
          >
            <option value={ALL_REPOSITORIES}>All repositories</option>
            {repositories.map((repository) => <option key={repository} value={repository}>{repository}</option>)}
            {hasUnlinkedReviews && <option value={UNLINKED_REPOSITORY}>No repository</option>}
          </select>
        </label>
      </header>

      {error && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error} <button type="button" onClick={() => void loadReviews()} className="font-semibold underline underline-offset-2">Retry</button></div>}
      {reviews === null && !error && <div className="space-y-3" aria-label="Loading reviews">{[0, 1, 2].map((row) => <div key={row} className="h-24 animate-pulse rounded-xl bg-slate-100" />)}</div>}
      {reviews?.length === 0 && <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center"><p className="text-sm font-semibold text-slate-900">No reviews yet</p><p className="mt-1 text-sm text-slate-600">Submitted pull request analyses will appear here.</p><Link href="/dashboard" className="mt-4 inline-block text-sm font-semibold text-brand-800 underline underline-offset-4">Go to workspace</Link></div>}
      {!!reviews?.length && <>
        <p className="text-xs text-slate-500">Showing {filteredReviews.length} of {reviews.length} {reviews.length === 1 ? "review" : "reviews"}</p>
        {filteredReviews.length > 0 ? (
          <ul className="space-y-3">
            {filteredReviews.map((item) => (
              <li key={item.id}>
                <Link href={`/analyses/${item.id}`} className="flex min-h-[96px] flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-5 transition-colors hover:border-slate-300 hover:bg-slate-50/70 sm:px-6">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-mono text-sm font-semibold text-slate-950">{reviewName(item)}</p>
                    {item.pr.title && item.pr.title !== reviewName(item) && <p className="mt-1 truncate text-sm text-slate-600">{item.pr.title}</p>}
                    <p className="mt-2 text-xs text-slate-500">Submitted {new Date(item.created_at).toLocaleString()}</p>
                  </div>
                  <AnalysisStatusBadge status={item.status} />
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center"><p className="text-sm font-semibold text-slate-900">No reviews for this repository</p><p className="mt-1 text-sm text-slate-600">Choose another repository to see its reviews.</p></div>
        )}
      </>}
    </div>
  );
}
