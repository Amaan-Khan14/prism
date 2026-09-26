import Link from "next/link";

export default function BenchmarksPage() {
  return (
    <div className="space-y-8" data-testid="benchmark-impact-page">
      <header>
        <h1 className="text-3xl font-semibold tracking-[-0.03em] text-slate-950">
          Benchmark impact
        </h1>
        <p className="mt-1.5 max-w-2xl text-sm leading-6 text-slate-600">
          See how PRism performs on a measured set of pull requests. Results appear only after a benchmark run is published.
        </p>
      </header>

      <section className="grid gap-8 border-y border-slate-200 py-8 lg:grid-cols-[minmax(0,1fr)_minmax(240px,0.55fr)]">
        <div className="max-w-2xl" data-testid="benchmark-empty-state">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
            No published runs
          </p>
          <h2 className="mt-3 text-xl font-semibold tracking-[-0.02em] text-slate-950">
            Impact data is not available yet
          </h2>
          <p className="mt-3 text-sm leading-6 text-slate-700">
            PRism does not have measured benchmark results to show in this build. When a run is available, this page will report its observed review-time and missed-regression outcomes without estimating missing values.
          </p>
          <Link
            href="/about"
            className="mt-5 inline-flex text-sm font-semibold text-brand-800 underline decoration-brand-200 underline-offset-4 hover:decoration-brand-800"
          >
            How PRism verifies a review
          </Link>
        </div>

        <aside className="border-t border-slate-200 pt-5 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
          <h2 className="text-sm font-semibold text-slate-950">What this view reports</h2>
          <dl className="mt-4 space-y-4 text-sm">
            <div>
              <dt className="font-medium text-slate-900">Review time</dt>
              <dd className="mt-1 leading-5 text-slate-600">Measured against the benchmark baseline.</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-900">Missed regressions</dt>
              <dd className="mt-1 leading-5 text-slate-600">Counted against known outcomes in the benchmark corpus.</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-900">Evidence coverage</dt>
              <dd className="mt-1 leading-5 text-slate-600">Shown only when a run includes ground-truth evidence.</dd>
            </div>
          </dl>
        </aside>
      </section>
    </div>
  );
}
