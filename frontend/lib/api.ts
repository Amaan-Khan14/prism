/** Cookie-authenticated client for the PRism backend API. */
import type {
  Analysis,
  AnalysisListItem,
  AuthUser,
  InstallationRepositories,
  InstallationPullRequests,
  StreamState,
} from "./types";

export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function detailFrom(status: number, body: string): string {
  if (body) {
    try {
      const parsed: unknown = JSON.parse(body);
      if (
        parsed &&
        typeof parsed === "object" &&
        typeof (parsed as { detail?: unknown }).detail === "string"
      ) {
        return (parsed as { detail: string }).detail;
      }
    } catch {
      // fall through to generic messages below
    }
  }
  if (status === 401) return "Sign in with GitHub to continue.";
  if (status === 0) return "Could not reach the PRism API. Is the backend running?";
  return `Request failed with status ${status}.`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      credentials: "include",
      ...init,
    });
  } catch {
    throw new ApiError(0, "Could not reach the PRism API. Is the backend running?");
  }
  if (response.status === 204) return undefined as T;
  const body = await response.text();
  if (!response.ok) throw new ApiError(response.status, detailFrom(response.status, body));
  if (!body) return undefined as T;
  try {
    return JSON.parse(body) as T;
  } catch {
    throw new ApiError(response.status, "The PRism API returned an unreadable response.");
  }
}

export function getMe(): Promise<AuthUser> {
  return request<AuthUser>("/auth/me");
}

export function logout(): Promise<void> {
  return request<void>("/auth/logout", { method: "POST" });
}

export function listAnalyses(): Promise<AnalysisListItem[]> {
  return request<AnalysisListItem[]>("/analyses");
}

export function getAnalysis(id: string): Promise<Analysis> {
  return request<Analysis>(`/analyses/${encodeURIComponent(id)}`);
}

export function createAnalysis(githubPrUrl: string): Promise<{ id: string }> {
  return request<{ id: string }>("/analyses", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ github_pr_url: githubPrUrl }),
  });
}

export function disconnectInstallation(installationId: number): Promise<void> {
  return request<void>(`/auth/github/installations/${installationId}`, {
    method: "DELETE",
  });
}

export function getInstallationRepositories(
  installationId: number,
): Promise<InstallationRepositories> {
  return request<InstallationRepositories>(
    `/auth/github/installations/${installationId}/repositories`,
  );
}

export function getInstallationPullRequests(
  installationId: number,
  repository: string,
): Promise<InstallationPullRequests> {
  const query = new URLSearchParams({ repository, state: "open" });
  return request<InstallationPullRequests>(
    `/auth/github/installations/${installationId}/pull-requests?${query.toString()}`,
  );
}

/** Fetch the raw unified diff served privately by the backend. */
export async function getAnalysisDiff(id: string): Promise<string> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/analyses/${encodeURIComponent(id)}/diff`, {
      credentials: "include",
    });
  } catch {
    throw new ApiError(0, "Could not reach the PRism API. Is the backend running?");
  }
  const body = await response.text();
  if (!response.ok) throw new ApiError(response.status, detailFrom(response.status, body));
  return body;
}

/** Navigate directly so the browser follows the API's cross-origin redirect to GitHub. */
export function startInstallationFlow(): void {
  window.location.assign(`${API_URL}/auth/github/install`);
}
