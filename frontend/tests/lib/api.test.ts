import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, API_URL, createAnalysis, getAnalysisDiff, getMe } from "@/lib/api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("sends cookies and hits the configured API base", async () => {
    const fetchMock = vi.fn(
      async (_input: string | URL | Request, _init?: RequestInit) =>
        jsonResponse({ github_login: "octocat" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await getMe();

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`${API_URL}/auth/me`);
    expect(init.credentials).toBe("include");
  });

  it("surfaces backend detail messages as ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({ detail: "Connect the PRism GitHub App to a repository before analyzing a pull request." }, 403),
      ),
    );

    const error = await createAnalysis("https://github.com/o/r/pull/1").catch(
      (err: unknown) => err,
    );
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(403);
    expect((error as ApiError).message).toContain("Connect the PRism GitHub App");
  });

  it("maps network failures to a reachable-status ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    }));

    await expect(getMe()).rejects.toMatchObject({ status: 0 });
  });

  it("returns raw text for the diff endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("diff --git a/x.py b/x.py\n", { status: 200 })),
    );

    await expect(getAnalysisDiff("abc")).resolves.toContain("diff --git");
  });

  it("maps a 404 diff to an ApiError with status 404", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response('{"detail":"No diff available"}', { status: 404 })),
    );

    await expect(getAnalysisDiff("abc")).rejects.toMatchObject({ status: 404 });
  });
});
