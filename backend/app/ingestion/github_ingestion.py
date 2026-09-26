"""Read-only GitHub App ingestion for pull request diffs."""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx
import jwt

from app.config import settings
from app.ingestion.bundle import PRBundle
from app.ingestion.diff_parser import parse_diff

logger = logging.getLogger(__name__)
_MAX_DIFF_BYTES = 20 * 1024 * 1024
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


class GitHubIngestionError(Exception):
    """A safe, user-facing GitHub ingestion failure."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class GitHubIngestion:
    """Fetch PR metadata and its unified diff using an installed GitHub App.

    The private key signs a short-lived app JWT. That JWT is exchanged for an
    installation token limited to the requested repository and read-only
    ``pull_requests``/``contents`` permissions.
    """

    @staticmethod
    def parse_pr_url(github_pr_url: str) -> tuple[str, int]:
        """Return ``(owner/repo, number)`` for a github.com PR URL."""
        try:
            parsed = urlsplit(github_pr_url)
        except ValueError as exc:
            raise ValueError("Provide a valid GitHub pull request URL.") from exc
        if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
            raise ValueError("Only HTTPS pull request URLs on github.com are supported.")

        parts = parsed.path.strip("/").split("/")
        if (
            len(parts) < 4
            or parts[2] != "pull"
            or not parts[3].isdigit()
            or not all(parts[:2])
            or any(part in {".", ".."} for part in parts[:2])
            or not re.fullmatch(r"[A-Za-z0-9-]+", parts[0])
            or not re.fullmatch(r"[A-Za-z0-9._-]+", parts[1])
        ):
            raise ValueError("URL must look like https://github.com/owner/repo/pull/123.")
        return f"{parts[0]}/{parts[1]}", int(parts[3])

    @staticmethod
    def _app_jwt() -> str:
        if not settings.github_app_id or not settings.github_private_key_path:
            raise GitHubIngestionError(
                503,
                "GitHub PR fetching is not configured. Set GITHUB_APP_ID and "
                "GITHUB_PRIVATE_KEY_PATH for an installed GitHub App.",
            )
        try:
            private_key = Path(settings.github_private_key_path).read_text(encoding="utf-8")
        except OSError as exc:
            logger.error("GitHub App private key could not be read: %s", exc)
            raise GitHubIngestionError(
                503, "The configured GitHub App private key could not be read."
            ) from exc
        issued_at = int(time.time())
        try:
            return jwt.encode(
                {"iat": issued_at - 60, "exp": issued_at + 540, "iss": settings.github_app_id},
                private_key,
                algorithm="RS256",
            )
        except Exception as exc:
            logger.error("GitHub App JWT signing failed: %s", exc)
            raise GitHubIngestionError(
                503, "The configured GitHub App credentials are invalid."
            ) from exc

    def _headers(self, token: str, accept: str = "application/vnd.github+json") -> dict[str, str]:
        return {
            "Accept": accept,
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": settings.github_api_version,
            "User-Agent": "PRism-PR-review",
        }

    @staticmethod
    def _raise_for_github_error(response: httpx.Response, *, is_pr_request: bool = False) -> None:
        status = response.status_code
        if status < 400:
            return
        if is_pr_request and status == 404:
            raise GitHubIngestionError(404, "The pull request was not found or is not accessible to the installed app.")
        if status in (401, 403, 404):
            raise GitHubIngestionError(
                403,
                "The GitHub App cannot access this repository. Check that it is installed "
                "for this repository and has read access to Pull requests and Contents.",
            )
        if status == 429 or status >= 500:
            raise GitHubIngestionError(502, "GitHub is temporarily unavailable. Try again shortly.")
        raise GitHubIngestionError(502, f"GitHub rejected the request (HTTP {status}).")

    async def ingest(
        self,
        github_pr_url: str,
        *,
        allowed_installation_ids: set[int] | None = None,
    ) -> PRBundle:
        """Fetch title, body, commit SHAs, and diff for a GitHub PR."""
        repo_full_name, pr_number = self.parse_pr_url(github_pr_url)
        owner, repo_name = repo_full_name.split("/", 1)
        app_jwt = self._app_jwt()
        api = settings.github_api_url.rstrip("/")

        timeout = httpx.Timeout(settings.github_request_timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                installation_response = await client.get(
                    f"{api}/repos/{owner}/{repo_name}/installation",
                    headers=self._headers(app_jwt),
                )
                self._raise_for_github_error(installation_response)
                installation = installation_response.json()
                if not isinstance(installation, dict):
                    raise GitHubIngestionError(502, "GitHub returned an invalid installation response.")
                installation_id = installation.get("id")
                if not isinstance(installation_id, int):
                    raise GitHubIngestionError(502, "GitHub returned an invalid installation response.")
                if allowed_installation_ids is not None and installation_id not in allowed_installation_ids:
                    raise GitHubIngestionError(
                        403,
                        "Connect the GitHub App to this repository from your PRism account before analyzing it.",
                    )

                token_response = await client.post(
                    f"{api}/app/installations/{installation_id}/access_tokens",
                    headers=self._headers(app_jwt),
                    json={
                        "repositories": [repo_name],
                        "permissions": {"pull_requests": "read", "contents": "read"},
                    },
                )
                self._raise_for_github_error(token_response)
                token_payload = token_response.json()
                if not isinstance(token_payload, dict):
                    raise GitHubIngestionError(502, "GitHub returned an invalid token response.")
                installation_token = token_payload.get("token")
                if not isinstance(installation_token, str) or not installation_token:
                    raise GitHubIngestionError(502, "GitHub did not return an installation token.")

                pr_url = f"{api}/repos/{owner}/{repo_name}/pulls/{pr_number}"
                metadata_response = await client.get(
                    pr_url,
                    headers=self._headers(installation_token),
                )
                self._raise_for_github_error(metadata_response, is_pr_request=True)
                metadata = metadata_response.json()
                if not isinstance(metadata, dict):
                    raise GitHubIngestionError(502, "GitHub returned an invalid pull request response.")

                diff_response = await client.get(
                    pr_url,
                    headers=self._headers(installation_token, "application/vnd.github.diff"),
                )
                self._raise_for_github_error(diff_response, is_pr_request=True)
                diff_bytes = diff_response.content
                if len(diff_bytes) > _MAX_DIFF_BYTES:
                    raise GitHubIngestionError(413, "The pull request diff exceeds the 20 MB ingestion limit.")
                diff_raw = diff_bytes.decode("utf-8", errors="replace")
        except GitHubIngestionError:
            raise
        except httpx.TimeoutException as exc:
            logger.warning("GitHub request timed out for %s#%s", repo_full_name, pr_number)
            raise GitHubIngestionError(504, "GitHub did not respond before the request timed out.") from exc
        except httpx.HTTPError as exc:
            logger.warning("GitHub request failed for %s#%s: %s", repo_full_name, pr_number, exc)
            raise GitHubIngestionError(502, "Could not reach GitHub to fetch this pull request.") from exc
        except (ValueError, KeyError, TypeError) as exc:
            logger.warning("Unexpected GitHub response for %s#%s: %s", repo_full_name, pr_number, exc)
            raise GitHubIngestionError(502, "GitHub returned an invalid pull request response.") from exc

        patches = parse_diff(diff_raw) if diff_raw else []
        if not patches:
            raise GitHubIngestionError(422, "GitHub returned no parseable file changes for this pull request.")

        head = metadata.get("head")
        base = metadata.get("base")
        if not isinstance(head, dict) or not isinstance(base, dict):
            raise GitHubIngestionError(502, "GitHub returned incomplete pull request revision metadata.")

        return PRBundle(
            title=metadata.get("title") or "",
            description=metadata.get("body") or "",
            diff_raw=diff_raw,
            patches=patches,
            github_pr_url=github_pr_url,
            head_sha=head.get("sha"),
            base_sha=base.get("sha"),
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            github_installation_id=installation_id,
        )

    async def fetch_changed_python_sources(
        self,
        repo_full_name: str,
        commit_sha: str,
        installation_id: int,
        paths: list[str],
    ) -> dict[str, str]:
        """Fetch bounded changed Python files at the exact PR head revision.

        The installation token is limited to this repository and Contents
        read. Missing or oversized files are skipped so source enrichment
        cannot make an otherwise valid diff review fail.
        """
        if not _SHA_RE.fullmatch(commit_sha or ""):
            return {}
        normalized_paths = list(dict.fromkeys(p for p in paths if p.endswith(".py")))[:100]
        if not normalized_paths:
            return {}
        owner, repo_name = repo_full_name.split("/", 1)
        app_jwt = self._app_jwt()
        api = settings.github_api_url.rstrip("/")
        timeout = httpx.Timeout(settings.github_request_timeout_seconds)
        source_map: dict[str, str] = {}
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                token_response = await client.post(
                    f"{api}/app/installations/{installation_id}/access_tokens",
                    headers=self._headers(app_jwt),
                    json={"repositories": [repo_name], "permissions": {"contents": "read"}},
                )
                self._raise_for_github_error(token_response)
                token_payload = token_response.json()
                token = token_payload.get("token") if isinstance(token_payload, dict) else None
                if not isinstance(token, str) or not token:
                    raise GitHubIngestionError(502, "GitHub did not return an installation token.")
                for path in normalized_paths:
                    if path.startswith("/") or ".." in path.split("/"):
                        continue
                    response = await client.get(
                        f"{api}/repos/{owner}/{repo_name}/contents/{quote(path, safe='/')}?ref={commit_sha}",
                        headers=self._headers(token, "application/vnd.github.raw+json"),
                    )
                    if response.status_code >= 400 or len(response.content) > 1_000_000:
                        continue
                    try:
                        source_map[path] = response.content.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
        except (GitHubIngestionError, httpx.HTTPError, ValueError, TypeError):
            logger.info("Changed source enrichment unavailable for %s@%s", repo_full_name, commit_sha[:8])
        return source_map
