"""Authenticated intake for GitHub Actions coverage reports."""
from __future__ import annotations

import asyncio
import hashlib
import fnmatch
import logging
import re
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Header, HTTPException, Request
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import AsyncSessionLocal
from app.facts.coverage_parsers import MAX_ARTIFACT_BYTES
from app.models import CoverageArtifactRecord
from app.storage import get_artifact_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/coverage-artifacts", tags=["coverage"])
_ISSUER = "https://token.actions.githubusercontent.com"
_JWKS_URL = f"{_ISSUER}/.well-known/jwks"
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_RUN_RE = re.compile(r"^[0-9]{1,24}$")
_jwks_client = PyJWKClient(_JWKS_URL, cache_jwk_set=True, lifespan=300)


def _verify_github_oidc_token(token: str) -> dict:
    """Verify GitHub's signed identity token and required provenance claims."""
    if not settings.github_coverage_trusted_workflow_refs:
        raise HTTPException(503, "Coverage uploads are not configured for a trusted workflow.")
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.github_actions_oidc_audience,
            issuer=_ISSUER,
            leeway=60,
            options={"require": ["exp", "iat", "repository", "sha", "run_id", "run_attempt", "workflow_ref", "event_name"]},
        )
    except Exception as exc:
        # PyJWKClient raises its own exception types; return no token details.
        logger.info("Rejected GitHub Actions OIDC token (%s)", type(exc).__name__)
        raise HTTPException(401, "The GitHub Actions identity token is invalid or expired.") from exc

    repo = claims.get("repository")
    workflow_ref = claims.get("workflow_ref")
    commit_sha = claims.get("sha")
    run_id = claims.get("run_id")
    run_attempt = claims.get("run_attempt")
    event_name = claims.get("event_name")
    if (
        not isinstance(repo, str)
        or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
        or not isinstance(workflow_ref, str)
        or not any(
            fnmatch.fnmatchcase(workflow_ref, allowed)
            for allowed in settings.github_coverage_trusted_workflow_refs
        )
        or not isinstance(commit_sha, str)
        or not _SHA_RE.fullmatch(commit_sha)
        or str(event_name) != "push"
        or not _RUN_RE.fullmatch(str(run_id))
        or not _RUN_RE.fullmatch(str(run_attempt))
    ):
        raise HTTPException(403, "This workflow identity is not allowed to upload coverage.")
    return claims


@router.post("/github-actions", status_code=201)
async def upload_github_actions_coverage(
    request: Request,
    authorization: str | None = Header(default=None),
    coverage_format: str = Header(default="auto", alias="X-Coverage-Format"),
    artifact_name: str | None = Header(default=None, alias="X-Coverage-Artifact-Name"),
) -> dict[str, str]:
    """Store a raw LCOV/Cobertura report from an allowlisted Actions workflow.

    Send raw report bytes with a GitHub Actions OIDC token as the bearer token.
    SHA/run metadata is taken only from the verified token claims.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "A GitHub Actions OIDC bearer token is required.")
    if coverage_format not in {"auto", "lcov", "cobertura"}:
        raise HTTPException(422, "X-Coverage-Format must be auto, lcov, or cobertura.")
    if artifact_name is not None and (len(artifact_name) > 200 or "\n" in artifact_name):
        raise HTTPException(422, "The artifact name is invalid.")

    token = authorization.removeprefix("Bearer ").strip()
    claims = await asyncio.to_thread(_verify_github_oidc_token, token)

    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_ARTIFACT_BYTES:
            raise HTTPException(413, "Coverage report exceeds the 50 MB upload limit.")
        chunks.append(chunk)
    raw = b"".join(chunks)
    if not raw:
        raise HTTPException(422, "Coverage report is empty.")

    repository = claims["repository"].lower()
    commit_sha = claims["sha"].lower()
    run_id = str(claims["run_id"])
    run_attempt = str(claims["run_attempt"])
    workflow_ref = claims["workflow_ref"]
    checksum = hashlib.sha256(raw).hexdigest()
    identity = f"{repository}:{commit_sha}:{run_id}:{run_attempt}:{checksum}".encode()
    storage_key = f"coverage/{hashlib.sha256(identity).hexdigest()}.report"
    store = get_artifact_store()
    await asyncio.to_thread(store.put, storage_key, raw, "application/octet-stream")

    try:
        async with AsyncSessionLocal() as db:
            record = CoverageArtifactRecord(
                repo_full_name=repository,
                commit_sha=commit_sha,
                run_id=run_id,
                run_attempt=run_attempt,
                workflow_ref=workflow_ref,
                artifact_name=artifact_name,
                format=coverage_format,
                artifact_sha256=checksum,
                storage_key=storage_key,
                created_at=datetime.now(timezone.utc),
            )
            db.add(record)
            await db.commit()
    except Exception as exc:
        async with AsyncSessionLocal() as check_db:
            try:
                referenced = await check_db.scalar(
                    select(CoverageArtifactRecord.id).where(
                        CoverageArtifactRecord.storage_key == storage_key
                    )
                )
            except Exception:
                logger.exception("Could not reconcile coverage artifact after DB error; preserving %s", storage_key)
                raise HTTPException(503, "Coverage upload persistence is temporarily unavailable.") from exc
        if referenced is not None:
            return {"status": "stored", "artifact_sha256": checksum, "commit_sha": commit_sha}
        await asyncio.to_thread(store.delete, storage_key)
        if isinstance(exc, IntegrityError):
            logger.info("Rejected duplicate GitHub Actions coverage run.")
            raise HTTPException(409, "This workflow run already uploaded a coverage report.") from exc
        logger.exception("Coverage artifact record could not be persisted")
        raise HTTPException(503, "Coverage upload persistence is temporarily unavailable.") from exc

    return {"status": "stored", "artifact_sha256": checksum, "commit_sha": commit_sha}
