"use client";

import { useEffect, useState } from "react";
import { API_URL, getInstallationRepositories } from "@/lib/api";
import type { ConnectedRepository } from "@/lib/types";
import { useAuth } from "@/components/AuthProvider";

type RepositoryState = {
  repositories: ConnectedRepository[];
  error?: boolean;
};

export default function RepositoriesPage() {
  const { user, status } = useAuth();
  const installations = user?.installations ?? [];
  const [repositoriesByInstallation, setRepositoriesByInstallation] = useState<Record<number, RepositoryState>>({});
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
            [installation.id]: { repositories: result.repositories },
          }));
        },
        () => {
          if (!active) return;
          setRepositoriesByInstallation((current) => ({
            ...current,
            [installation.id]: { repositories: [], error: true },
          }));
        },
      );
    }

    return () => {
      active = false;
    };
  }, [installations]);

  if (status === "loading") {
    return (
      <div className="space-y-4" aria-label="Loading repositories">
        <div className="h-16 animate-pulse rounded-xl bg-slate-100" />
        <div className="h-48 animate-pulse rounded-xl bg-slate-100" />
      </div>
    );
  }

  if (status !== "signedIn") {
    return (
      <div className="space-y-6 pb-4" data-testid="repositories-page">
        <PageHeader />
        <section className="rounded-xl border border-slate-200 bg-white p-5 sm:p-6">
          <p className="text-sm text-slate-600">Sign in with GitHub to connect and manage repository access.</p>
          <a href={`${API_URL}/auth/github/login`} className="mt-5 inline-flex rounded-lg bg-brand-700 px-5 py-3 text-sm font-semibold text-white hover:bg-brand-800">Sign in with GitHub</a>
        </section>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-4" data-testid="repositories-page">
      <PageHeader />

      <section className="rounded-xl border border-slate-200 bg-white p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-950">Connected repositories</h2>
            <p className="mt-0.5 text-xs text-slate-500">Repositories PRism can read for pull-request analysis.</p>
          </div>
          <a
            href={installations.length ? installationSettingsUrl : `${API_URL}/auth/github/install`}
            target={installations.length ? "_blank" : undefined}
            rel={installations.length ? "noreferrer" : undefined}
            className="inline-flex items-center justify-center rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-950 transition-colors hover:border-slate-400 hover:bg-slate-50"
          >
            {installations.length ? "Add repositories" : "Connect GitHub App"}
          </a>
        </div>

        {installations.length === 0 ? (
          <p className="mt-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
            No repositories connected yet. Install the PRism GitHub App on the repositories you want to analyze.
          </p>
        ) : (
          <ul className="mt-5 space-y-3">
            {installations.map((installation) => {
              const state = repositoriesByInstallation[installation.id];
              return (
                <li key={installation.id} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-4 sm:px-5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs text-slate-500">
                      Installed for <span className="font-medium text-slate-800">{installation.account_login}</span>
                      <span className="ml-2">{installation.account_type}</span>
                    </p>
                    <span className="text-xs text-slate-500">Read-only access</span>
                  </div>
                  <div className="mt-3 border-t border-slate-200 pt-3">
                    {state === undefined ? (
                      <p className="text-sm text-slate-500">Loading repositories…</p>
                    ) : state.error ? (
                      <p role="status" className="text-sm text-rose-700">Could not load repositories from GitHub.</p>
                    ) : state.repositories.length === 0 ? (
                      <p className="text-sm text-slate-500">No repositories are available to PRism.</p>
                    ) : (
                      <ul className="divide-y divide-slate-200">
                        {state.repositories.map((repository) => (
                          <li key={repository.id}>
                            <a
                              href={repository.html_url}
                              target="_blank"
                              rel="noreferrer"
                              className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm transition-colors hover:text-brand-800"
                            >
                              <span className="font-medium text-slate-900">{repository.full_name}</span>
                              <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-medium uppercase tracking-wide text-slate-500">
                                {repository.private ? "Private" : "Public"}
                              </span>
                            </a>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}

function PageHeader() {
  return (
    <header className="flex flex-col justify-between gap-3 border-b border-slate-200 pb-5 sm:flex-row sm:items-end">
      <div>
        <h1 className="text-2xl font-semibold tracking-[-0.035em] text-slate-950">Repositories</h1>
        <p className="mt-1.5 max-w-2xl text-sm leading-6 text-slate-600">
          Choose which GitHub repositories PRism can read when analyzing pull requests. Access is read-only.
        </p>
      </div>
    </header>
  );
}
