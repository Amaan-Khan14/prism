import type {
  Analysis,
  AnalysisListItem,
  AuthUser,
  Citation,
  Facet,
  FacetKind,
  FacetStatus,
  Finding,
} from "@/lib/types";

const NOW = "2026-09-26T12:00:00Z";

export const ALL_FACET_KINDS: FacetKind[] = [
  "intent_vs_spec",
  "cross_file_impact",
  "test_coverage_gaps",
  "risk_hazards",
];

export function facetRow(kind: FacetKind, status: FacetStatus): Facet {
  return {
    id: `facet-${kind}`,
    kind,
    status,
    created_at: NOW,
    updated_at: NOW,
    findings: [],
  };
}

export function citation(overrides: Partial<Citation> = {}): Citation {
  return {
    kind: "added_line",
    file_path: "app/pipeline.py",
    line_number: 11,
    imported_module: null,
    supported: true,
    reason: "changed line 11 in app/pipeline.py",
    ...overrides,
  };
}

export function finding(overrides: Partial<Finding> = {}): Finding {
  return {
    id: "f-1",
    verdict: "verified",
    severity: 3,
    summary: "Retry loop can mask downstream failures.",
    claim_type: "code",
    citation_file: "app/pipeline.py",
    citation_line: 11,
    citations: [citation()],
    gate_reasons: [],
    created_at: NOW,
    ...overrides,
  };
}

export function analysis(overrides: Partial<Analysis> = {}): Analysis {
  return {
    id: "a-1",
    status: "completed",
    error: null,
    created_at: NOW,
    updated_at: NOW,
    pr: {
      id: "p-1",
      title: "Add refund endpoint",
      description: "Adds POST /refunds with idempotency keys.",
      repo_full_name: "octocat/payments",
      pr_number: 42,
      github_pr_url: "https://github.com/octocat/payments/pull/42",
      head_sha: "a".repeat(40),
      base_sha: "b".repeat(40),
    },
    coverage_status: "accepted",
    coverage_rejection_reason: null,
    coverage_format: "lcov",
    coverage_ci_provider: "github_actions",
    coverage_run_id: "12345678",
    coverage_run_attempt: "1",
    coverage_artifact_name: "coverage-report",
    coverage_commit_sha: "a".repeat(40),
    coverage_artifact_sha256: "c".repeat(64),
    coverage_parsed_at: NOW,
    coverage_file_count: 12,
    coverage_parser_warnings: [],
    facets: [
      {
        id: "facet-1",
        kind: "test_coverage_gaps",
        status: "completed",
        created_at: NOW,
        updated_at: NOW,
        findings: [
          finding(),
          finding({
            id: "f-2",
            verdict: "unverified",
            severity: 2,
            summary: "Claims a coverage gap without a coverage artifact.",
            citations: [
              citation({
                supported: false,
                reason: "coverage status is unknown for this analysis",
              }),
            ],
            gate_reasons: ["all citations failed verification"],
          }),
        ],
      },
    ],
    ...overrides,
  };
}

export function analysisListItem(overrides: Partial<AnalysisListItem> = {}): AnalysisListItem {
  const base = analysis();
  return {
    id: base.id,
    status: base.status,
    error: base.error,
    created_at: base.created_at,
    updated_at: base.updated_at,
    pr: base.pr,
    ...overrides,
  };
}

export function authUser(overrides: Partial<AuthUser> = {}): AuthUser {
  return {
    id: "u-1",
    github_login: "octocat",
    github_name: "The Octocat",
    installations: [{ id: 7, account_login: "octocat", account_type: "User" }],
    ...overrides,
  };
}

export const SAMPLE_DIFF_TEXT = [
  "diff --git a/app/pipeline.py b/app/pipeline.py",
  "--- a/app/pipeline.py",
  "+++ b/app/pipeline.py",
  "@@ -10,3 +10,4 @@ def run():",
  "     unchanged()",
  "-    old_call()",
  "+    new_call()",
  "+    second_call()",
].join("\n");
