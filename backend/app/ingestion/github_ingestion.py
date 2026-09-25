"""GitHubIngestion — fetches a PR via the GitHub REST API and returns a PRBundle.

No GitHub API calls are made in this stub; the structure is complete so the
facts engine can consume it immediately once a token is wired in.
"""
from __future__ import annotations

from app.ingestion.bundle import PRBundle
from app.ingestion.diff_parser import parse_diff


class GitHubIngestion:
    """Fetches a GitHub PR and normalises it into a PRBundle.

    In Step 1 this is a structural stub: parse_pr_url is implemented,
    the actual HTTP calls are marked TODO and will be filled in Step 3
    when a GITHUB_TOKEN is wired into settings.
    """

    @staticmethod
    def parse_pr_url(github_pr_url: str) -> tuple[str, int]:
        """Extract (owner/repo, pr_number) from a GitHub PR URL.

        Accepts:
          https://github.com/owner/repo/pull/123
          https://github.com/owner/repo/pull/123/files
        """
        import re

        match = re.search(r"github\.com/([^/]+/[^/]+)/pull/(\d+)", github_pr_url)
        if not match:
            raise ValueError(f"Cannot parse GitHub PR URL: {github_pr_url!r}")
        return match.group(1), int(match.group(2))

    def ingest(self, github_pr_url: str) -> PRBundle:
        """Fetch PR data from GitHub and return a PRBundle.

        TODO (Step 3): implement real GitHub REST API calls using GITHUB_TOKEN.
        """
        repo_full_name, pr_number = self.parse_pr_url(github_pr_url)

        # --- placeholder values until real API calls are wired ---
        title = ""
        description = ""
        diff_raw = ""
        head_sha: str | None = None
        base_sha: str | None = None
        # ----------------------------------------------------------

        patches = parse_diff(diff_raw) if diff_raw else []

        return PRBundle(
            title=title,
            description=description,
            diff_raw=diff_raw,
            patches=patches,
            github_pr_url=github_pr_url,
            head_sha=head_sha,
            base_sha=base_sha,
            repo_full_name=repo_full_name,
            pr_number=pr_number,
        )
