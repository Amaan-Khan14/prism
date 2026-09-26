"""Tests for the GitHub Actions OIDC coverage intake endpoint.

Verifies allowlist enforcement, SHA validation, and the OIDC token
verification logic — without any real GitHub OIDC tokens, real database,
or real artifact storage.

Requires eval-type-backport (in requirements.txt) for Python 3.9 compat
with FastAPI route annotations that use `str | None` syntax.
"""
from __future__ import annotations

import textwrap
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.routers.coverage import _verify_github_oidc_token


# ---------------------------------------------------------------------------
# Minimal valid LCOV bytes
# ---------------------------------------------------------------------------

_LCOV = textwrap.dedent("""\
    TN:
    SF:src/app.py
    DA:1,1
    DA:2,0
    end_of_record
""").encode("utf-8")

_SHA = "a" * 40
_WORKFLOW_REF = "Amaan-Khan14/prism/.github/workflows/coverage.yml@refs/heads/main"
_TRUSTED_REFS = ["Amaan-Khan14/prism/.github/workflows/coverage.yml@refs/heads/*"]


# ---------------------------------------------------------------------------
# Helper: build a passing JWT claims dict
# ---------------------------------------------------------------------------

def _good_claims(**overrides: Any) -> dict:
    base = {
        "repository": "Amaan-Khan14/prism",
        "workflow_ref": _WORKFLOW_REF,
        "sha": _SHA,
        "run_id": "12345678",
        "run_attempt": "1",
        "event_name": "push",
        "exp": int((datetime.now(tz=timezone.utc) + timedelta(hours=1)).timestamp()),
        "iat": int(datetime.now(tz=timezone.utc).timestamp()),
    }
    base.update(overrides)
    return base


def _call(claims: dict, trusted_refs: list = _TRUSTED_REFS) -> dict:
    """Patch settings and JWT decode; return the verified claims dict."""
    fake_key = MagicMock()
    fake_key.key = "signing-key"

    with (
        patch("app.routers.coverage._jwks_client") as mock_jwks,
        patch("app.routers.coverage.jwt.decode", return_value=claims),
        patch("app.routers.coverage.settings") as mock_settings,
    ):
        mock_jwks.get_signing_key_from_jwt.return_value = fake_key
        mock_settings.github_coverage_trusted_workflow_refs = trusted_refs
        mock_settings.github_actions_oidc_audience = "prism"
        return _verify_github_oidc_token("fake.jwt.token")


# ===========================================================================
# 1. _verify_github_oidc_token — isolated unit tests
# ===========================================================================


class TestVerifyGitHubOidcToken:

    def test_valid_claims_accepted(self) -> None:
        claims = _call(_good_claims())
        assert claims["sha"] == _SHA

    def test_empty_trusted_refs_raises_503(self) -> None:
        """Empty allowlist → 503 (config error, not an auth failure)."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _call(_good_claims(), trusted_refs=[])
        assert exc_info.value.status_code == 503

    def test_untrusted_workflow_ref_raises_403(self) -> None:
        from fastapi import HTTPException

        bad_claims = _good_claims(
            workflow_ref="NotTrusted/repo/.github/workflows/other.yml@refs/heads/main"
        )
        with pytest.raises(HTTPException) as exc_info:
            _call(bad_claims)
        assert exc_info.value.status_code == 403

    def test_wrong_event_name_raises_403(self) -> None:
        """Only push events are accepted — pull_request events are rejected."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _call(_good_claims(event_name="pull_request"))
        assert exc_info.value.status_code == 403

    def test_invalid_sha_format_raises_403(self) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _call(_good_claims(sha="not-a-sha"))
        assert exc_info.value.status_code == 403

    def test_invalid_repo_format_raises_403(self) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _call(_good_claims(repository="no-slash-in-here"))
        assert exc_info.value.status_code == 403

    def test_wildcard_branch_ref_matches(self) -> None:
        """@refs/heads/* must match any branch name, not just main."""
        claims = _call(
            _good_claims(
                workflow_ref="Amaan-Khan14/prism/.github/workflows/coverage.yml@refs/heads/feature"
            )
        )
        assert claims["sha"] == _SHA

    def test_specific_branch_also_accepted(self) -> None:
        claims = _call(
            _good_claims(
                workflow_ref="Amaan-Khan14/prism/.github/workflows/coverage.yml@refs/heads/main"
            )
        )
        assert claims["sha"] == _SHA

    def test_tag_ref_rejected_by_branch_wildcard(self) -> None:
        """refs/tags/* must not match refs/heads/* pattern."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _call(
                _good_claims(
                    workflow_ref="Amaan-Khan14/prism/.github/workflows/coverage.yml@refs/tags/v1.0"
                )
            )
        assert exc_info.value.status_code == 403

    def test_jwt_exception_raises_401(self) -> None:
        from fastapi import HTTPException

        with (
            patch("app.routers.coverage._jwks_client") as mock_jwks,
            patch("app.routers.coverage.settings") as mock_settings,
        ):
            mock_settings.github_coverage_trusted_workflow_refs = _TRUSTED_REFS
            mock_settings.github_actions_oidc_audience = "prism"
            mock_jwks.get_signing_key_from_jwt.side_effect = Exception("bad token")
            with pytest.raises(HTTPException) as exc_info:
                _verify_github_oidc_token("bad.jwt.token")
        assert exc_info.value.status_code == 401

    def test_no_jwt_decode_call_when_trusted_refs_empty(self) -> None:
        """The function must bail before jwt.decode when unconfigured."""
        from fastapi import HTTPException

        with (
            patch("app.routers.coverage.jwt.decode") as mock_decode,
            patch("app.routers.coverage.settings") as mock_settings,
        ):
            mock_settings.github_coverage_trusted_workflow_refs = []
            with pytest.raises(HTTPException):
                _verify_github_oidc_token("any.token")
        mock_decode.assert_not_called()

    def test_no_github_api_calls_in_verification(self) -> None:
        """Verification must not call the GitHub REST API — OIDC-only."""
        import inspect
        source = inspect.getsource(_verify_github_oidc_token)
        assert "api.github.com" not in source


# ===========================================================================
# 2. Allowlist scope — restricted to prism's coverage workflow
# ===========================================================================


class TestAllowlistScope:

    def test_different_repo_is_rejected(self) -> None:
        from fastapi import HTTPException

        bad_claims = _good_claims(
            repository="someone-else/other-repo",
            workflow_ref="someone-else/other-repo/.github/workflows/coverage.yml@refs/heads/main",
        )
        with pytest.raises(HTTPException) as exc_info:
            _call(bad_claims)
        assert exc_info.value.status_code == 403

    def test_different_workflow_in_same_repo_is_rejected(self) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _call(
                _good_claims(
                    workflow_ref="Amaan-Khan14/prism/.github/workflows/deploy.yml@refs/heads/main",
                )
            )
        assert exc_info.value.status_code == 403

    def test_correct_workflow_on_main_is_accepted(self) -> None:
        claims = _call(_good_claims())
        assert claims["sha"] == _SHA

    def test_correct_workflow_on_feature_branch_is_accepted(self) -> None:
        claims = _call(
            _good_claims(
                workflow_ref="Amaan-Khan14/prism/.github/workflows/coverage.yml@refs/heads/feature-x"
            )
        )
        assert claims["sha"] == _SHA


# ===========================================================================
# 3. Mismatched-SHA rejection — exercises accept_coverage() directly
# ===========================================================================


class TestMismatchedSHARejection:
    """Confirm that mismatched SHA does not yield an accepted coverage result."""

    def test_mismatched_sha_yields_rejected_coverage(self) -> None:
        from app.facts.coverage_intake import (
            CIRunMetadata, CoverageArtifact, RejectedCoverage, accept_coverage,
        )

        artifact = CoverageArtifact(
            raw=_LCOV,
            metadata=CIRunMetadata(commit_sha="b" * 40, ci_provider="github_actions", run_id="99"),
            format="lcov",
        )
        result = accept_coverage(artifact, pr_head_sha=_SHA)
        assert isinstance(result, RejectedCoverage)
        assert "does not match" in result.reason

    def test_mismatched_sha_rejection_reason_identifies_artifact_sha(self) -> None:
        from app.facts.coverage_intake import (
            CIRunMetadata, CoverageArtifact, RejectedCoverage, accept_coverage,
        )

        artifact = CoverageArtifact(
            raw=_LCOV,
            metadata=CIRunMetadata(commit_sha="b" * 40, ci_provider="ci", run_id="1"),
            format="lcov",
        )
        result = accept_coverage(artifact, pr_head_sha="a" * 40)
        assert isinstance(result, RejectedCoverage)
        assert "bbbbbbbb" in result.reason or ("b" * 40) in result.reason

    def test_mismatched_sha_does_not_produce_coverage_findings(self) -> None:
        """build_coverage_facts must return all-unknown when SHA mismatches."""
        from app.facts.coverage_facts import build_coverage_facts
        from app.facts.coverage_intake import CIRunMetadata, CoverageArtifact
        from app.facts.models import CoverageStatus

        artifact = CoverageArtifact(
            raw=_LCOV,
            metadata=CIRunMetadata(commit_sha="c" * 40, ci_provider="github_actions", run_id="77"),
            format="lcov",
        )
        facts = build_coverage_facts(
            changed_file_paths=["src/app.py"],
            coverage_artifact=artifact,
            pr_head_sha=_SHA,
        )
        assert all(fc.status == CoverageStatus.unknown for fc in facts)
        assert all(fc.source is None for fc in facts)

    def test_matching_sha_yields_accepted_coverage(self) -> None:
        """Control case: matching SHA must yield AcceptedCoverage."""
        from app.facts.coverage_intake import (
            AcceptedCoverage, CIRunMetadata, CoverageArtifact, accept_coverage,
        )

        artifact = CoverageArtifact(
            raw=_LCOV,
            metadata=CIRunMetadata(commit_sha=_SHA, ci_provider="github_actions", run_id="123"),
            format="lcov",
        )
        result = accept_coverage(artifact, pr_head_sha=_SHA)
        assert isinstance(result, AcceptedCoverage)
        assert result.provenance.commit_sha == _SHA.lower()

    def test_matching_sha_produces_real_coverage_status(self) -> None:
        """With a matching SHA, files in the artifact get a non-unknown status."""
        from app.facts.coverage_facts import build_coverage_facts
        from app.facts.coverage_intake import CIRunMetadata, CoverageArtifact
        from app.facts.models import CoverageStatus

        artifact = CoverageArtifact(
            raw=_LCOV,
            metadata=CIRunMetadata(commit_sha=_SHA, ci_provider="github_actions", run_id="123"),
            format="lcov",
        )
        facts = build_coverage_facts(
            changed_file_paths=["src/app.py"],
            coverage_artifact=artifact,
            pr_head_sha=_SHA,
        )
        assert any(fc.status != CoverageStatus.unknown for fc in facts)


class TestCoverageUploadEndpoint:
    @pytest.mark.asyncio
    async def test_verified_upload_is_saved_through_artifact_store_and_database(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from app.models import CoverageArtifactRecord
        from app.routers.coverage import upload_github_actions_coverage
        from starlette.requests import Request

        class FakeStore:
            def __init__(self) -> None:
                self.put = MagicMock(return_value=None)

        class FakeDb:
            def __init__(self) -> None:
                self.add = MagicMock()
                self.commit = AsyncMock()

        store = FakeStore()
        db = FakeDb()

        @asynccontextmanager
        async def session_context():
            yield db

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": _LCOV, "more_body": False}

        request = Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": "/coverage-artifacts/github-actions",
                "raw_path": b"/coverage-artifacts/github-actions",
                "query_string": b"",
                "headers": [],
                "client": ("127.0.0.1", 1234),
                "server": ("testserver", 80),
            },
            receive,
        )
        claims = _good_claims(
            repository="Amaan-Khan14/codedocket",
            workflow_ref="Amaan-Khan14/codedocket/.github/workflows/ci.yml@refs/heads/main",
        )

        with (
            patch("app.routers.coverage._verify_github_oidc_token", return_value=claims),
            patch("app.routers.coverage.get_artifact_store", return_value=store),
            patch("app.routers.coverage.AsyncSessionLocal", side_effect=lambda: session_context()),
        ):
            response = await upload_github_actions_coverage(
                request,
                authorization="Bearer signed-token",
                coverage_format="lcov",
                artifact_name="coverage.lcov",
            )

        assert response["status"] == "stored"
        assert response["commit_sha"] == _SHA
        assert response["artifact_sha256"]
        store.put.assert_called_once()
        assert store.put.call_args.args[1] == _LCOV
        record = db.add.call_args.args[0]
        assert isinstance(record, CoverageArtifactRecord)
        assert record.repo_full_name == "amaan-khan14/codedocket"
        assert record.commit_sha == _SHA
        assert record.run_id == "12345678"
        assert record.run_attempt == "1"
        assert record.workflow_ref == claims["workflow_ref"]
        assert record.artifact_sha256 == response["artifact_sha256"]
        db.commit.assert_awaited_once()
