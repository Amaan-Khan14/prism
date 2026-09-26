"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, createAnalysis, getInstallationPullRequests, getInstallationRepositories, listAnalyses, startInstallationFlow } from "@/lib/api";
import type { AnalysisListItem, ConnectedRepository, Installation, PullRequestOption } from "@/lib/types";
import { useAuth } from "@/components/AuthProvider";
import { AnalysisStatusBadge } from "@/components/Badges";
import { GitHubMark } from "@/components/TopNav";

const PR_URL_PATTERN = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/pull\/\d+\/?$/;

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });
}

function prLabel(item: AnalysisListItem): string {
  if (item.pr.repo_full_name && item.pr.pr_number !== null) {
    return `${item.pr.repo_full_name}#${item.pr.pr_number}`;
  }
  if (item.pr.github_pr_url) return item.pr.github_pr_url;
  return item.pr.title || "Raw diff analysis";
}

export default function DashboardPage() {
  const { status } = useAuth();

  return (
    <div className="space-y-6 pb-4">
      <header className="flex flex-col justify-between gap-3 border-b border-slate-200 pb-5 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.035em] text-slate-950">Review workspace</h1>
          <p className="mt-1.5 text-sm text-slate-600">Start a pull-request review, manage repository access, and revisit your evidence briefs.</p>
        </div>
        {status === "signedIn" && <span className="font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-brand-700">Evidence-backed review</span>}
      </header>
      {status === "loading" && <DashboardSkeleton />}
      {status === "signedOut" && <SignInPanel />}
      {status === "signedIn" && <SignedInDashboard />}
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-4" data-testid="dashboard-skeleton">
      <div className="h-32 animate-pulse rounded-2xl bg-slate-100" />
      <div className="h-64 animate-pulse rounded-2xl bg-slate-100" />
    </div>
  );
}

function SignInPanel() {
  return (
    <section
      data-testid="dashboard-sign-in"
      className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white px-6 py-16 text-center"
    >
      <div className="hero-grid pointer-events-none absolute inset-0" aria-hidden="true" />
      <div className="relative">
        <GitHubMark className="mx-auto h-10 w-10 text-slate-950" />
        <h2 className="mt-4 text-xl font-semibold tracking-tight text-slate-950">
          Sign in to analyze pull requests
        </h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">
          PRism uses the GitHub App user authorization flow. You will connect your
          repositories once, right after signing in.
        </p>
        <a
          href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/auth/github/login`}
          data-testid="dashboard-sign-in-button"
          className="mt-6 inline-flex items-center gap-2 rounded-lg bg-brand-700 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-800"
        >
          <GitHubMark className="h-4 w-4" />
          Sign in with GitHub
        </a>
      </div>
    </section>
  );
}

function SignedInDashboard() {
  const router = useRouter();
  const { user } = useAuth();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [connectedNotice, setConnectedNotice] = useState(false);

  useEffect(() => {
    if (sessionStorage.getItem("prism:github_connected")) {
      sessionStorage.removeItem("prism:github_connected");
      setConnectedNotice(true);
    }
  }, []);

  const analyzePr = useCallback(
    async (prUrl: string) => {
      setSubmitError(null);
      setSubmitting(true);
      try {
        const created = await createAnalysis(prUrl);
        router.push(`/analyses/${created.id}`);
      } catch (error) {
        setSubmitError(
          error instanceof ApiError
            ? error.detail
            : "Something went wrong while submitting the analysis.",
        );
        setSubmitting(false);
      }
    },
    [router],
  );

  const handleManualSubmit = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const url = new FormData(event.currentTarget).get("pr_url");
      const prUrl = typeof url === "string" ? url.trim() : "";
      if (!PR_URL_PATTERN.test(prUrl)) {
        setSubmitError("Enter a GitHub pull request URL like https://github.com/owner/repo/pull/123.");
        return;
      }
      await analyzePr(prUrl);
    },
    [analyzePr],
  );

  return (
    <div className="space-y-6">
      {connectedNotice && (
        <div
          role="status"
          data-testid="connected-notice"
          className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
        >
          GitHub App connected — your repositories are ready for analysis.
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px] xl:items-start">
        <div className="space-y-5">
          <PullRequestPicker
            installations={user?.installations ?? []}
            submitting={submitting}
            submitError={submitError}
            onAnalyze={analyzePr}
          />
          <details className="group rounded-xl border border-slate-200 bg-white px-5 py-4 sm:px-6">
            <summary className="cursor-pointer list-none text-sm font-semibold text-slate-700 transition-colors hover:text-slate-950">
              <span className="flex items-center justify-between gap-4">Paste a pull request URL <span className="text-lg font-normal text-slate-400 transition-transform group-open:rotate-45">+</span></span>
            </summary>
            <form onSubmit={handleManualSubmit} data-testid="new-analysis-form" className="mt-5 border-t border-slate-100 pt-5">
              <label htmlFor="pr_url" className="text-sm font-medium text-slate-950">Pull request URL</label>
              <p className="mt-1 text-xs leading-5 text-slate-500">Analysis uses the exact diff, facts, and coverage for the PR head commit. Nothing is posted back to GitHub.</p>
              <div className="mt-3 flex flex-col gap-3 sm:flex-row">
                <input id="pr_url" name="pr_url" type="url" required placeholder="https://github.com/owner/repo/pull/123" className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-100" />
                <button type="submit" disabled={submitting} data-testid="submit-analysis" className="inline-flex items-center justify-center gap-2 rounded-lg bg-brand-700 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-800 disabled:cursor-not-allowed disabled:opacity-60">{submitting ? <><Spinner /> Submitting…</> : "Analyze PR"}</button>
              </div>
              {submitError && <p role="alert" data-testid="submit-error" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{submitError}</p>}
            </form>
          </details>
        </div>
        <InstallationsCard />
      </div>
      <AnalysisHistory />
    </div>
  );
}

function PullRequestPicker({
  installations,
  submitting,
  submitError,
  onAnalyze,
}: {
  installations: Installation[];
  submitting: boolean;
  submitError: string | null;
  onAnalyze: (url: string) => Promise<void>;
}) {
  const [repositories, setRepositories] = useState<Array<{ installationId: number; repository: ConnectedRepository }>>([]);
  const [repositoriesLoading, setRepositoriesLoading] = useState(true);
  const [repositoriesError, setRepositoriesError] = useState(false);
  const [selectedRepository, setSelectedRepository] = useState("");
  const [pullRequests, setPullRequests] = useState<PullRequestOption[] | null>(null);
  const [pullRequestsLoading, setPullRequestsLoading] = useState(false);
  const [pullRequestsError, setPullRequestsError] = useState<string | null>(null);
  const [selectedPullRequest, setSelectedPullRequest] = useState("");
  const [hasMore, setHasMore] = useState(false);

  useEffect(() => {
    let active = true;
    setRepositories([]);
    setRepositoriesLoading(installations.length > 0);
    setRepositoriesError(false);
    if (installations.length === 0) {
      setRepositoriesLoading(false);
      return () => { active = false; };
    }
    void Promise.all(installations.map(async (installation) => {
      const result = await getInstallationRepositories(installation.id);
      return result.repositories.map((repository) => ({ installationId: installation.id, repository }));
    })).then((results) => {
      if (!active) return;
      const available = results.flat();
      setRepositories(available);
      setSelectedRepository((current) => {
        const stillAvailable = available.some(({ installationId, repository }) => `${installationId}:${repository.full_name}` === current);
        return stillAvailable ? current : (available[0] ? `${available[0].installationId}:${available[0].repository.full_name}` : "");
      });
    }).catch(() => {
      if (active) setRepositoriesError(true);
    }).finally(() => {
      if (active) setRepositoriesLoading(false);
    });
    return () => { active = false; };
  }, [installations]);

  const selected = repositories.find(({ installationId, repository }) =>
    `${installationId}:${repository.full_name}` === selectedRepository,
  );

  useEffect(() => {
    let active = true;
    setPullRequests(null);
    setSelectedPullRequest("");
    setPullRequestsError(null);
    setHasMore(false);
    if (!selected) {
      setPullRequestsLoading(false);
      return () => { active = false; };
    }
    setPullRequestsLoading(true);
    void getInstallationPullRequests(selected.installationId, selected.repository.full_name).then((result) => {
      if (!active) return;
      setPullRequests(result.pull_requests);
      setHasMore(result.has_more);
      setSelectedPullRequest(result.pull_requests[0] ? String(result.pull_requests[0].number) : "");
    }).catch((error) => {
      if (active) setPullRequestsError(error instanceof ApiError ? error.detail : "Could not load pull requests from GitHub.");
    }).finally(() => {
      if (active) setPullRequestsLoading(false);
    });
    return () => { active = false; };
  }, [selectedRepository, selected?.installationId, selected?.repository.full_name]);

  const chosenPr = pullRequests?.find((pr) => String(pr.number) === selectedPullRequest);

  return (
    <section id="new-review" className="scroll-mt-24 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-[0_14px_30px_-26px_rgba(15,23,42,0.55)]" data-testid="pr-picker">
      <div className="border-b border-slate-100 bg-slate-50/70 px-5 py-4 sm:px-6">
        <h2 className="text-base font-semibold tracking-[-0.02em] text-slate-950">Start a review</h2>
        <p className="mt-1 text-xs text-slate-600">Choose a connected repository, then select an open pull request.</p>
      </div>
      <div className="p-5 sm:p-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-xs font-medium text-slate-600">
          Repository
          <select value={selectedRepository} onChange={(event) => setSelectedRepository(event.target.value)} disabled={repositoriesLoading || repositories.length === 0} className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 focus:border-slate-950 focus:outline-none">
            <option value="">{repositoriesLoading ? "Loading repositories…" : "Select a repository"}</option>
            {repositories.map(({ installationId, repository }) => <option key={`${installationId}:${repository.id}`} value={`${installationId}:${repository.full_name}`}>{repository.full_name}</option>)}
          </select>
        </label>
        <label className="block text-xs font-medium text-slate-600">
          Pull request
          <select value={selectedPullRequest} onChange={(event) => setSelectedPullRequest(event.target.value)} disabled={!selected || pullRequestsLoading || !pullRequests?.length} className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 focus:border-slate-950 focus:outline-none">
            <option value="">{pullRequestsLoading ? "Loading pull requests…" : "Select a pull request"}</option>
            {pullRequests?.map((pr) => <option key={pr.number} value={String(pr.number)}>#{pr.number} {pr.title}{pr.draft ? " (Draft)" : ""}</option>)}
          </select>
        </label>
      </div>
      {repositoriesError && <p role="alert" className="mt-3 text-sm text-rose-700">Could not load connected repositories. Try refreshing the page.</p>}
      {installations.length === 0 && <p className="mt-3 text-sm text-slate-500">Connect the GitHub App below to choose a repository.</p>}
      {repositories.length === 0 && !repositoriesLoading && !repositoriesError && installations.length > 0 && <p className="mt-3 text-sm text-slate-500">No repositories are available to this GitHub App.</p>}
      {pullRequestsError && <p role="alert" className="mt-3 text-sm text-rose-700">{pullRequestsError}</p>}
      {pullRequests?.length === 0 && <p className="mt-3 text-sm text-slate-500">No open pull requests in this repository.</p>}
      {hasMore && <p className="mt-3 text-xs text-slate-500">Showing the 100 most recently updated open pull requests.</p>}
      {chosenPr && <a href={chosenPr.html_url} target="_blank" rel="noreferrer" className="mt-3 inline-block text-xs text-slate-950 underline-offset-2 hover:underline">View #{chosenPr.number} on GitHub ↗</a>}
      {chosenPr && <button type="button" disabled={submitting} onClick={() => void onAnalyze(chosenPr.html_url)} className="mt-4 flex w-full items-center justify-center gap-2 rounded-full bg-slate-950 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto">
        {submitting ? <><Spinner /> Submitting…</> : "Analyze selected PR"}
      </button>}
      {submitError && <p role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{submitError}</p>}
      </div>
    </section>
  );
}

function Spinner() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4 animate-spin" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.25" strokeWidth="4" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

function InstallationsCard() {
  const { user, refresh } = useAuth();
  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [disconnectingId, setDisconnectingId] = useState<number | null>(null);
  const [repositoriesByInstallation, setRepositoriesByInstallation] = useState<
    Record<number, { repositories: ConnectedRepository[]; totalCount: number; error?: boolean }>
  >({});

  const installations = user?.installations ?? [];
  const installationSettingsUrl = installations.length === 1
    ? installations[0].account_type.toLowerCase() === "organization"
      ? `https://github.com/organizations/${encodeURIComponent(installations[0].account_login)}/settings/installations/${installations[0].id}`
      : `https://github.com/settings/installations/${installations[0].id}`
    : "https://github.com/settings/installations";

  useEffect(() => {
    let active = true;
    setRepositoriesByInstallation({});
    for (const installation of installations) {
      void getInstallationRepositories(installation.id).then(
        (result) => {
          if (!active) return;
          setRepositoriesByInstallation((current) => ({
            ...current,
            [installation.id]: {
              repositories: result.repositories,
              totalCount: result.total_count,
            },
          }));
        },
        () => {
          if (!active) return;
          setRepositoriesByInstallation((current) => ({
            ...current,
            [installation.id]: { repositories: [], totalCount: 0, error: true },
          }));
        },
      );
    }
    return () => {
      active = false;
    };
  }, [installations]);

  const connect = useCallback(() => {
    setConnectError(null);
    setConnecting(true);
    startInstallationFlow();
  }, []);

  const disconnect = useCallback(
    async (installationId: number) => {
      setConnectError(null);
      setDisconnectingId(installationId);
      try {
        const { disconnectInstallation } = await import("@/lib/api");
        await disconnectInstallation(installationId);
        await refresh();
      } catch (error) {
        setConnectError(
          error instanceof ApiError ? error.detail : "Could not disconnect the installation.",
        );
      } finally {
        setDisconnectingId(null);
      }
    },
    [refresh],
  );

  return (
    <section
      id="repositories"
      data-testid="installations-card"
      className="scroll-mt-24 rounded-xl border border-slate-200 bg-white p-5 shadow-[0_14px_30px_-26px_rgba(15,23,42,0.45)] sm:p-6 xl:sticky xl:top-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-950">Connected repositories</h2>
          <p className="mt-0.5 text-xs text-slate-500">
            PRism reads PRs with a read-only GitHub App installation token.
          </p>
        </div>
        {installations.length > 0 ? (
          <a href={installationSettingsUrl} target="_blank" rel="noreferrer" data-testid="connect-github" className="inline-flex items-center gap-2 rounded-full border border-slate-300 px-4 py-2 text-sm font-medium text-slate-950 transition-colors hover:border-slate-400 hover:bg-slate-50">
            <GitHubMark className="h-4 w-4" /> Add repositories
          </a>
        ) : (
          <button
            type="button"
            onClick={() => void connect()}
            disabled={connecting}
            data-testid="connect-github"
            className="inline-flex items-center gap-2 rounded-full border border-slate-300 px-4 py-2 text-sm font-medium text-slate-950 transition-colors hover:border-slate-400 hover:bg-slate-50 disabled:opacity-60"
          >
            <GitHubMark className="h-4 w-4" />
            {connecting ? "Opening GitHub…" : "Connect GitHub App"}
          </button>
        )}
      </div>

      {connectError && (
        <p role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {connectError}
        </p>
      )}

      {installations.length === 0 ? (
        <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          No repositories connected yet. Install the PRism GitHub App on the repositories you want to analyze — PRism cannot fetch a PR without it.
        </p>
      ) : (
        <ul className="mt-4 space-y-2">
          {installations.map((installation) => (
            <li
              key={installation.id}
              className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="truncate text-xs text-slate-500">
                  Installed for <span className="font-medium text-slate-800">{installation.account_login}</span>
                  <span className="ml-2">{installation.account_type}</span>
                </p>
                <button
                  type="button"
                  onClick={() => void disconnect(installation.id)}
                  disabled={disconnectingId === installation.id}
                  data-testid={`disconnect-${installation.id}`}
                  className="shrink-0 rounded-lg px-2.5 py-1.5 text-xs text-rose-700 transition-colors hover:bg-rose-50 hover:text-rose-800 disabled:opacity-50"
                >
                  {disconnectingId === installation.id ? "Disconnecting…" : "Disconnect"}
                </button>
              </div>

              <div className="mt-3 border-t border-slate-200 pt-3">
                <p className="text-xs font-medium text-slate-600">Repositories with access</p>
                {!repositoriesByInstallation[installation.id] ? (
                  <p className="mt-2 text-sm text-slate-500">Loading repositories…</p>
                ) : repositoriesByInstallation[installation.id].error ? (
                  <p className="mt-2 text-sm text-rose-700">Could not load repositories from GitHub.</p>
                ) : repositoriesByInstallation[installation.id].repositories.length === 0 ? (
                  <p className="mt-2 text-sm text-slate-500">No repositories are available to PRism.</p>
                ) : (
                  <>
                    <ul className="mt-2 flex flex-wrap gap-2">
                      {repositoriesByInstallation[installation.id].repositories.map((repository) => (
                        <li key={repository.id}>
                          <a
                            href={repository.html_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-800 transition-colors hover:border-slate-400"
                          >
                            {repository.full_name}
                            <span className="text-[10px] uppercase tracking-wide text-slate-400">
                              {repository.private ? "Private" : "Public"}
                            </span>
                          </a>
                        </li>
                      ))}
                    </ul>
                    {repositoriesByInstallation[installation.id].totalCount > repositoriesByInstallation[installation.id].repositories.length && (
                      <p className="mt-2 text-xs text-slate-500">
                        Showing {repositoriesByInstallation[installation.id].repositories.length} of {repositoriesByInstallation[installation.id].totalCount} repositories.
                      </p>
                    )}
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function AnalysisHistory() {
  const [analyses, setAnalyses] = useState<AnalysisListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setAnalyses(null);
    try {
      setAnalyses(await listAnalyses());
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load your analyses.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const isEmpty = useMemo(() => analyses !== null && analyses.length === 0, [analyses]);

  return (
    <section id="reviews" data-testid="analysis-history" className="scroll-mt-24">
      <div className="flex items-center justify-between border-b border-slate-200 pb-3">
        <div><h2 className="text-lg font-semibold tracking-[-0.02em] text-slate-950">Recent reviews</h2><p className="mt-0.5 text-xs text-slate-500">Your completed and in-progress evidence briefs.</p></div>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-full px-2.5 py-1.5 text-xs text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-950"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}{" "}
          <button type="button" onClick={() => void load()} className="underline underline-offset-2">
            Retry
          </button>
        </div>
      )}

      {analyses === null && !error && (
        <div className="mt-3 space-y-2" data-testid="history-loading">
          {[0, 1, 2].map((index) => (
            <div key={index} className="h-16 animate-pulse rounded-xl bg-slate-100" />
          ))}
        </div>
      )}

      {isEmpty && (
        <div className="mt-3 rounded-xl border border-dashed border-slate-300 px-4 py-10 text-center">
          <p className="text-sm font-medium text-slate-800">No analyses yet</p>
          <p className="mt-1 text-sm text-slate-500">
            Submit a GitHub pull request URL above to see your first evidence-backed review.
          </p>
        </div>
      )}

      {analyses !== null && analyses.length > 0 && (
        <ul className="mt-3 space-y-2">
          {analyses.map((item) => (
            <li key={item.id}>
              <Link
                href={`/analyses/${item.id}`}
                data-testid="history-item"
                className="flex items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white px-4 py-3 transition-colors hover:border-slate-400"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-slate-950">
                    <span className="font-mono">{prLabel(item)}</span>
                    {item.pr.title && item.pr.title !== prLabel(item) && (
                      <span className="ml-2 font-normal text-slate-500">{item.pr.title}</span>
                    )}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Submitted {relativeTime(item.created_at)}
                  </p>
                </div>
                <AnalysisStatusBadge status={item.status} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
