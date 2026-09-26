import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "How it works",
  description:
    "PRism's pipeline: deterministic facts, four parallel review facets, and a citation-level evidence gate.",
};

const steps = [
  {
    number: "1",
    title: "Connect GitHub",
    body: "You sign in through the PRism GitHub App and install it on the repositories you want analyzed. Repository access uses short-lived, read-only installation tokens (metadata, contents, and pull requests only).",
  },
  {
    number: "2",
    title: "Ingest the exact PR",
    body: "Submit a pull request URL. PRism fetches the PR's exact unified diff and head/base commit SHAs from GitHub, and stores the diff as a private artifact served only to you through the API.",
  },
  {
    number: "3",
    title: "Compute deterministic facts",
    body: "Before any model runs, the facts engine extracts exact changed-line ranges, walks Python imports to build cross-file dependency edges, and loads CI coverage that matches the PR's exact head SHA.",
  },
  {
    number: "4",
    title: "Run four review facets",
    body: "Intent vs spec, cross-file impact, test-coverage gaps, and risk hazards run concurrently. Each facet sees only the facts, description, and diff context it needs, and returns strictly typed, structured findings.",
  },
  {
    number: "5",
    title: "Verify every citation",
    body: "The deterministic evidence gate checks each finding's citations against the computed facts. Unsupported claims are demoted to an unverified appendix with the reason — they are never shown as verified.",
  },
  {
    number: "6",
    title: "Read the brief",
    body: "You get a risk-ordered brief with verified findings, exact file and line citations linked into the diff, coverage provenance, and the verification state of every claim.",
  },
];

const states = [
  {
    title: "Coverage accepted",
    body: "A CI coverage report was uploaded for this exact commit, passed integrity checks, and parsed cleanly. Coverage claims can cite it.",
    tone: "border-emerald-200 bg-emerald-50",
    heading: "text-emerald-800",
    dot: "bg-emerald-500",
  },
  {
    title: "Coverage rejected",
    body: "A report was uploaded but failed the SHA match or parse. Coverage is treated as unknown and cannot back a coverage-gap claim.",
    tone: "border-amber-200 bg-amber-50",
    heading: "text-amber-800",
    dot: "bg-amber-500",
  },
  {
    title: "No coverage artifact",
    body: "Nothing was supplied for this commit. Test-coverage claims are limited to what the diff itself shows, and the report's provenance says so.",
    tone: "border-slate-200 bg-white",
    heading: "text-slate-900",
    dot: "bg-slate-400",
  },
];

export default function AboutPage() {
  return (
    <div className="space-y-20 pb-8">
      <section className="border-b border-slate-200 pb-10 pt-4">
        <h1 className="max-w-4xl text-4xl font-semibold leading-[1.08] tracking-[-0.035em] text-slate-950 sm:text-5xl">
          A finding only counts when its evidence holds up.
        </h1>
        <p className="mt-5 max-w-3xl text-base leading-7 text-slate-700 sm:text-lg sm:leading-8">
          PRism checks large and AI-generated pull requests against their stated intent, cross-file dependencies, and test coverage. A deterministic gate checks each citation; anything it cannot support remains clearly marked as unverified.
        </p>
        <p className="mt-6 font-mono text-xs font-medium text-brand-800">DIFF FACTS <span className="px-2 text-slate-500">→</span> FOUR REVIEW FACETS <span className="px-2 text-slate-500">→</span> CITATION CHECK</p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold tracking-[-0.03em] text-slate-950">The review pipeline</h2>
        <div className="mt-6 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
          {steps.map((step) => (
            <div key={step.number} className="border-t border-slate-200 pt-5">
              <p className="font-mono text-xs text-brand-800">{step.number.padStart(2, "0")}</p>
              <h3 className="mt-2 text-base font-semibold text-slate-950">{step.title}</h3>
              <p className="mt-1.5 text-sm leading-6 text-slate-700">{step.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-semibold tracking-[-0.03em] text-slate-950">What verification means</h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-6">
            <h3 className="text-base font-semibold text-emerald-800">Verified findings</h3>
            <p className="mt-2 text-sm leading-6 text-emerald-900/70">
              The gate confirmed every citation against the facts: the cited line
              exists and is changed by this PR, the import edge exists, or the
              coverage report covers (or does not cover) the cited line.
            </p>
          </div>
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
            <h3 className="text-base font-semibold text-amber-800">Unverified appendix</h3>
            <p className="mt-2 text-sm leading-6 text-amber-900/70">
              Claims that could not be tied to facts. They remain readable, with
              the exact rejection reason per citation, so you can judge them yourself.
            </p>
          </div>
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold tracking-tighter text-slate-950">
          How coverage provenance works
        </h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
          Coverage is never guessed. Your CI uploads a coverage.py report to
          PRism&apos;s intake endpoint using a GitHub Actions OIDC identity, bound
          to the exact commit it was produced for. Each analysis records which
          report — if any — it used:
        </p>
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          {states.map((state) => (
            <div key={state.title} className={`rounded-2xl border p-6 ${state.tone}`}>
              <div className="flex items-center gap-2">
                <span className={`h-2 w-2 rounded-full ${state.dot}`} aria-hidden="true" />
                <h3 className={`text-sm font-semibold ${state.heading}`}>{state.title}</h3>
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-500">{state.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-3xl bg-slate-950 px-6 py-14 text-center sm:px-10">
        <h2 className="text-3xl font-bold tracking-tighter text-white">Scope and limits</h2>
        <ul className="mx-auto mt-6 max-w-2xl space-y-3 text-left text-sm leading-6 text-slate-400">
          <li className="flex gap-3">
            <span className="mt-0.5 font-mono text-slate-600">—</span>
            Analysis runs entirely on the PRism backend. PRism never runs your
            PR&apos;s code, and it never posts comments back to GitHub.
          </li>
          <li className="flex gap-3">
            <span className="mt-0.5 font-mono text-slate-600">—</span>
            Facts are deterministic; models only propose findings, and the gate
            decides what you see as verified.
          </li>
          <li className="flex gap-3">
            <span className="mt-0.5 font-mono text-slate-600">—</span>
            Benchmark comparisons appear only once the backend publishes measured
            results from the seeded corpus — no numbers are invented for display.
          </li>
        </ul>
        <Link
          href="/dashboard"
          className="mt-9 inline-block rounded-full bg-white px-6 py-3 text-sm font-medium text-slate-950 transition-colors hover:bg-slate-200"
        >
          Try it on a pull request →
        </Link>
      </section>
    </div>
  );
}
