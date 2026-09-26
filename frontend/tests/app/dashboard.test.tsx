import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import DashboardPage from "@/app/dashboard/page";
import { AuthProvider } from "@/components/AuthProvider";
import { analysisListItem, authUser } from "../fixtures";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/dashboard",
}));

type Route = {
  test: RegExp;
  method?: string;
  status: number;
  body?: unknown;
  text?: string;
};

function stubFetch(routes: Route[]) {
  const calls: { url: string; method: string; body?: string }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input instanceof Request ? input.url : input);
      const method = (init?.method ?? (input instanceof Request ? input.method : "GET") ?? "GET").toUpperCase();
      const body = typeof init?.body === "string" ? init.body : undefined;
      calls.push({ url, method, body });
      for (const route of routes) {
        if (route.test.test(url) && (!route.method || route.method === method)) {
          if (route.text !== undefined) return new Response(route.text, { status: route.status });
          return new Response(
            route.body === undefined ? null : JSON.stringify(route.body),
            { status: route.status, headers: { "Content-Type": "application/json" } },
          );
        }
      }
      throw new Error(`Unhandled fetch in test: ${method} ${url}`);
    }),
  );
  return calls;
}

function renderDashboard() {
  return render(
    <AuthProvider>
      <DashboardPage />
    </AuthProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  pushMock.mockClear();
  sessionStorage.clear();
});

describe("DashboardPage", () => {
  it("prompts sign-in when the session is missing", async () => {
    stubFetch([{ test: /\/auth\/me$/, status: 401, body: { detail: "Sign in" } }]);
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByTestId("dashboard-sign-in")).toBeInTheDocument();
    });
    expect(screen.getByTestId("dashboard-sign-in-button")).toHaveAttribute(
      "href",
      expect.stringContaining("/auth/github/login"),
    );
    expect(screen.queryByTestId("new-analysis-form")).toBeNull();
  });

  it("submits a PR URL and navigates to the created analysis", async () => {
    const calls = stubFetch([
      { test: /\/auth\/me$/, status: 200, body: authUser() },
      { test: /\/analyses\/a-1$/, method: "GET", status: 200, body: { id: "a-1" } },
      {
        test: /\/analyses$/,
        method: "POST",
        status: 201,
        body: { id: "a-1" },
      },
      { test: /\/analyses$/, method: "GET", status: 200, body: [analysisListItem()] },
    ]);
    renderDashboard();

    await screen.findByTestId("new-analysis-form");
    await userEvent.type(
      screen.getByLabelText("Pull request URL"),
      "https://github.com/octocat/payments/pull/42",
    );
    await userEvent.click(screen.getByTestId("submit-analysis"));

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/analyses/a-1");
    });
    const post = calls.find((call) => call.method === "POST");
    expect(post?.body).toContain("github_pr_url");
    expect(screen.queryByTestId("submit-error")).toBeNull();
  });

  it("surfaces backend submission errors (e.g. missing installation)", async () => {
    stubFetch([
      { test: /\/auth\/me$/, status: 200, body: authUser() },
      {
        test: /\/analyses$/,
        method: "POST",
        status: 403,
        body: {
          detail: "Connect the PRism GitHub App to a repository before analyzing a pull request.",
        },
      },
      { test: /\/analyses$/, method: "GET", status: 200, body: [] },
    ]);
    renderDashboard();

    await screen.findByTestId("new-analysis-form");
    await userEvent.type(
      screen.getByLabelText("Pull request URL"),
      "https://github.com/octocat/payments/pull/42",
    );
    await userEvent.click(screen.getByTestId("submit-analysis"));

    const alert = await screen.findByTestId("submit-error");
    expect(alert).toHaveTextContent(
      "Connect the PRism GitHub App to a repository before analyzing a pull request.",
    );
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("rejects non-GitHub-PR URLs before calling the API", async () => {
    const calls = stubFetch([
      { test: /\/auth\/me$/, status: 200, body: authUser() },
      { test: /\/analyses$/, method: "GET", status: 200, body: [] },
    ]);
    renderDashboard();

    await screen.findByTestId("new-analysis-form");
    // A syntactically valid URL that is not a GitHub PR URL — native `type=url`
    // validation already blocks malformed input before this handler runs.
    await userEvent.type(
      screen.getByLabelText("Pull request URL"),
      "https://gitlab.com/octocat/payments/-/merge_requests/1",
    );
    await userEvent.click(screen.getByTestId("submit-analysis"));

    expect(await screen.findByTestId("submit-error")).toHaveTextContent(
      "Enter a GitHub pull request URL",
    );
    expect(calls.find((call) => call.method === "POST")).toBeUndefined();
  });

  it("lists prior analyses with status and empties cleanly", async () => {
    stubFetch([
      { test: /\/auth\/me$/, status: 200, body: authUser() },
      { test: /\/analyses$/, method: "GET", status: 200, body: [analysisListItem()] },
    ]);
    renderDashboard();

    const items = await screen.findAllByTestId("history-item");
    expect(items).toHaveLength(1);
    expect(items[0]).toHaveTextContent("octocat/payments#42");
    expect(items[0]).toHaveTextContent("Completed");
    expect(screen.queryByText("No analyses yet")).toBeNull();
  });

  it("shows the empty state when no analyses exist", async () => {
    stubFetch([
      { test: /\/auth\/me$/, status: 200, body: authUser({ installations: [] }) },
      { test: /\/analyses$/, method: "GET", status: 200, body: [] },
    ]);
    renderDashboard();

    expect(await screen.findByText("No analyses yet")).toBeInTheDocument();
    expect(screen.getByText(/No repositories connected yet/)).toBeInTheDocument();
  });

  it("shows the connection banner after the GitHub App install callback", async () => {
    sessionStorage.setItem("prism:github_connected", "1");
    stubFetch([
      { test: /\/auth\/me$/, status: 200, body: authUser() },
      { test: /\/analyses$/, method: "GET", status: 200, body: [] },
    ]);
    renderDashboard();

    expect(await screen.findByTestId("connected-notice")).toHaveTextContent(
      "GitHub App connected",
    );
  });
});
