/** Type definitions mirroring the PRism backend API schemas exactly. */

export type AnalysisStatus = "pending" | "running" | "completed" | "failed";
export type FacetKind =
  | "intent_vs_spec"
  | "cross_file_impact"
  | "test_coverage_gaps"
  | "risk_hazards";
export type FacetStatus = "pending" | "running" | "completed" | "failed";
export type FindingVerdict = "verified" | "unverified";
export type CoverageStatus = "accepted" | "rejected" | "none";

/** One evidence citation attached to a finding (verified against PR facts). */
export interface Citation {
  kind: "added_line" | "dependency_edge" | "coverage";
  file_path: string;
  line_number: number | null;
  imported_module: string | null;
  supported: boolean;
  reason: string;
}

export interface Finding {
  id: string;
  verdict: FindingVerdict;
  severity: number;
  summary: string;
  claim_type: string | null;
  citation_file: string | null;
  citation_line: number | null;
  citations: Citation[];
  gate_reasons: string[];
  created_at: string;
}

export interface Facet {
  id: string;
  kind: FacetKind;
  status: FacetStatus;
  created_at: string;
  updated_at: string;
  findings: Finding[];
}

/** PR metadata returned with analyses (backend PROut schema). */
export interface PRSummary {
  id: string;
  title: string | null;
  description: string | null;
  repo_full_name: string | null;
  pr_number: number | null;
  github_pr_url: string | null;
  head_sha: string | null;
  base_sha: string | null;
}

export interface CoverageProvenance {
  coverage_status: CoverageStatus | null;
  coverage_rejection_reason: string | null;
  coverage_format: string | null;
  coverage_ci_provider: string | null;
  coverage_run_id: string | null;
  coverage_run_attempt: string | null;
  coverage_artifact_name: string | null;
  coverage_commit_sha: string | null;
  coverage_artifact_sha256: string | null;
  coverage_parsed_at: string | null;
  coverage_file_count: number | null;
  coverage_parser_warnings: string[] | null;
}

export interface Analysis extends CoverageProvenance {
  id: string;
  status: AnalysisStatus;
  error: string | null;
  created_at: string;
  updated_at: string;
  pr: PRSummary;
  facets: Facet[];
}

export type AnalysisListItem = Pick<
  Analysis,
  "id" | "status" | "error" | "created_at" | "updated_at" | "pr"
>;

export interface Installation {
  id: number;
  account_login: string;
  account_type: string;
}

export interface ConnectedRepository {
  id: number;
  full_name: string;
  html_url: string;
  private: boolean;
}

export interface InstallationRepositories {
  total_count: number;
  repositories: ConnectedRepository[];
}

export interface PullRequestOption {
  number: number;
  title: string;
  state: "open" | "closed";
  draft: boolean;
  html_url: string;
  updated_at: string;
}

export interface InstallationPullRequests {
  pull_requests: PullRequestOption[];
  has_more: boolean;
}

export interface AuthUser {
  id: string;
  github_login: string;
  github_name: string | null;
  installations: Installation[];
}

/** Payload of the backend's SSE `progress`/`done` events. */
export interface StreamState {
  analysis_id: string;
  status: AnalysisStatus;
  error: string | null;
  facets: { kind: FacetKind; status: FacetStatus }[];
}
