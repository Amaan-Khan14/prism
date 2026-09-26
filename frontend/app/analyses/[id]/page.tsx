"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ApiError, getAnalysis } from "@/lib/api";
import { streamAnalysisProgress, type StreamHandle } from "@/lib/sse";
import type { Analysis, FacetStatus, StreamState } from "@/lib/types";
import { AnalysisReport } from "@/components/AnalysisReport";
import { FacetProgress } from "@/components/FacetProgress";

const POLL_INTERVAL_MS = 3000;

function mergeStreamState(analysis: Analysis, state: StreamState): Analysis {
  const statuses = new Map<string, FacetStatus>(
    state.facets.map((facet) => [facet.kind, facet.status]),
  );
  return {
    ...analysis,
    status: state.status,
    error: state.error,
    facets: analysis.facets.map((facet) => {
      const next = statuses.get(facet.kind);
      return next ? { ...facet, status: next } : facet;
    }),
  };
}

export default function AnalysisPage() {
  const params = useParams<{ id: string }>();
  const analysisId = typeof params.id === "string" ? params.id : "";

  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setAnalysis(null);
    setLoadError(null);
    setNotFound(false);
    getAnalysis(analysisId)
      .then((result) => {
        if (!cancelled) setAnalysis(result);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 404) {
          setNotFound(true);
        } else {
          setLoadError(error instanceof Error ? error.message : "Could not load this analysis.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [analysisId]);

  // Live progress while the analysis runs: SSE first, polling as fallback.
  const isLive = analysis !== null && (analysis.status === "pending" || analysis.status === "running");
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!isLive || !analysis) return;

    const stopPolling = () => {
      if (pollTimer.current) {
        clearInterval(pollTimer.current);
        pollTimer.current = null;
      }
    };
    const refetch = async () => {
      try {
        const fresh = await getAnalysis(analysisId);
        setAnalysis(fresh);
      } catch {
        // Keep the last known state; the next poll may succeed.
      }
    };
    const startPolling = () => {
      if (pollTimer.current) return;
      pollTimer.current = setInterval(() => void refetch(), POLL_INTERVAL_MS);
    };

    let handle: StreamHandle | null = streamAnalysisProgress(analysisId, {
      onProgress: (state, done) => {
        setAnalysis((current) => (current ? mergeStreamState(current, state) : current));
        if (done) {
          stopPolling();
          handle?.abort();
          void refetch(); // pull the full findings payload once complete
        }
      },
      onError: () => {
        // Stream broke or stalled: fall back to polling the REST endpoint.
        startPolling();
      },
    });

    return () => {
      handle?.abort();
      handle = null;
      stopPolling();
    };
  }, [isLive, analysisId]);

  if (notFound) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white px-6 py-16 text-center">
        <h1 className="text-lg font-semibold tracking-tight text-slate-950">Review not found</h1>
        <p className="mt-2 text-sm text-slate-600">
          It may belong to a different account, or the link is wrong.
        </p>
        <Link
          href="/dashboard"
          className="mt-6 inline-block rounded-full bg-zinc-950 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700"
        >
          Back to Overview
        </Link>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 px-6 py-10 text-center" data-testid="load-error">
        <p className="text-sm text-rose-700">{loadError}</p>
        <Link href="/dashboard" className="mt-4 inline-block text-sm text-zinc-950 underline-offset-2 hover:underline">
          Back to Overview
        </Link>
      </div>
    );
  }

  if (analysis === null) {
    return (
      <div className="space-y-4" data-testid="analysis-loading">
        <div className="h-28 animate-pulse rounded-xl bg-slate-200/70" />
        <div className="h-48 animate-pulse rounded-xl bg-slate-200/70" />
      </div>
    );
  }

  if (analysis.status === "pending" || analysis.status === "running") {
    return <LiveProgress analysis={analysis} />;
  }

  return <AnalysisReport analysis={analysis} />;
}

function LiveProgress({ analysis }: { analysis: Analysis }) {
  return (
    <div className="mx-auto max-w-2xl space-y-6" data-testid="analysis-progress">
      <header className="text-center">
        <p className="inline-flex items-center gap-2 rounded-md border border-brand-200 bg-brand-50 px-3 py-1.5 text-xs font-semibold text-brand-900">
          <span className="h-2 w-2 animate-pulse rounded-full bg-brand-700" aria-hidden="true" />
          {analysis.status === "pending" ? "Queued" : "Analyzing"}
        </p>
        <h1 className="mt-4 text-xl font-semibold tracking-tight text-slate-950 sm:text-2xl">
          {analysis.pr.title || analysis.pr.repo_full_name || "Pull request"}
        </h1>
        <p className="mt-2 text-sm leading-6 text-slate-700">
          Building diff, dependency, and coverage facts before the review facets run. Citation checks follow, and this view updates as each step completes.
        </p>
      </header>
      <FacetProgress
        facets={analysis.facets.map((facet) => ({ kind: facet.kind, status: facet.status }))}
      />
    </div>
  );
}
