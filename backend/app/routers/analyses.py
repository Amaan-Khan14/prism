"""Analyses router — POST /analyses, GET /analyses/{id}, GET /analyses/{id}/stream, GET /analyses/{id}/diff."""
from __future__ import annotations

import asyncio
import functools
import json
import logging
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal, get_db
from app.ingestion import FileIngestion, GitHubIngestion
from app.ingestion.github_ingestion import GitHubIngestionError
from app.github_auth import assert_user_can_access_repo, get_current_user, get_github_user_token, require_csrf_origin
from app.models import Analysis, AnalysisStatus, Facet, FacetKind, FacetStatus, PR, User
from app.schemas import AnalysisOut, CreateAnalysisRequest, CreateAnalysisResponse
from app.storage import diff_key, get_artifact_store
from app.review.orchestration import FACET_ORDER, execute_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyses", tags=["analyses"])


# ---------------------------------------------------------------------------
# POST /analyses
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=CreateAnalysisResponse,
    status_code=201,
    dependencies=[Depends(require_csrf_origin)],
)
async def create_analysis(
    body: CreateAnalysisRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None,  # type: ignore[assignment]
) -> CreateAnalysisResponse:
    """Create a new Analysis row from a GitHub PR URL or a raw diff.

    The raw diff (if any) is stored via the configured ArtifactStore.
    Only the storage key, size, and checksum are persisted in PostgreSQL;
    the diff bytes are never written into the database row.
    """
    if body.github_pr_url:
        ingestion = GitHubIngestion()
        try:
            repo_full_name, _ = ingestion.parse_pr_url(body.github_pr_url)
            github_token = await get_github_user_token(db, user)
            await assert_user_can_access_repo(github_token, repo_full_name)
            allowed_installation_ids = {installation.id for installation in user.installations}
            if not allowed_installation_ids:
                raise HTTPException(
                    403,
                    "Connect the PRism GitHub App to a repository before analyzing a pull request.",
                )
            bundle = await ingestion.ingest(
                body.github_pr_url,
                allowed_installation_ids=allowed_installation_ids,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except GitHubIngestionError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        pr = PR(
            github_pr_url=bundle.github_pr_url,
            user_id=user.id,
            github_installation_id=bundle.github_installation_id,
            repo_full_name=bundle.repo_full_name,
            pr_number=bundle.pr_number,
            head_sha=bundle.head_sha,
            base_sha=bundle.base_sha,
            title=bundle.title or None,
            description=bundle.description or None,
        )
    else:
        ingestion = FileIngestion()
        try:
            bundle = ingestion.ingest(
                diff=body.diff or "",
                title=body.title or "",
                description=body.description or "",
            )
        except Exception as exc:
            raise HTTPException(status_code=422, detail="Invalid unified diff.") from exc
        if not bundle.patches:
            raise HTTPException(
                status_code=422,
                detail="The supplied diff contains no parseable file changes.",
            )
        pr = PR(
            user_id=user.id,
            title=bundle.title or None,
            description=bundle.description or None,
        )

    db.add(pr)
    await db.flush()  # materialise pr.id so we can derive the storage key

    # Store the diff artifact (if there is one) outside the database row.
    # boto3 is synchronous; offload to the default thread-pool executor so S3
    # network I/O never blocks the event loop.
    diff_bytes = bundle.diff_raw.encode() if bundle.diff_raw else None
    stored_key: str | None = None
    if diff_bytes:
        store = get_artifact_store()
        key = diff_key(pr.id)
        loop = asyncio.get_running_loop()
        artifact = await loop.run_in_executor(
            None,
            functools.partial(store.put, key, diff_bytes, "text/x-patch"),
        )
        pr.diff_storage_key = artifact.key
        pr.diff_size_bytes = artifact.size_bytes
        pr.diff_sha256 = artifact.sha256
        stored_key = artifact.key

    analysis = Analysis(pr_id=pr.id, status=AnalysisStatus.pending)
    db.add(analysis)
    for facet_kind in FACET_ORDER:
        db.add(
            Facet(
                analysis=analysis,
                kind=facet_kind,
                status=FacetStatus.pending,
            )
        )
    try:
        await db.commit()
    except Exception:
        # db.commit() raising has an ambiguous outcome: PostgreSQL may have
        # committed the transaction even if the application did not receive
        # confirmation (e.g. the connection dropped after the server ACK'd).
        # We therefore MUST NOT delete the artifact without first confirming
        # via a fresh database connection that no row references it.
        await db.rollback()  # safe no-op if the transaction already committed
        if stored_key is not None:
            await _try_delete_orphaned_artifact(stored_key)
        raise

    await db.refresh(analysis)
    if background_tasks is not None:
        background_tasks.add_task(execute_analysis, analysis.id)
    return CreateAnalysisResponse(id=analysis.id)


async def _try_delete_orphaned_artifact(storage_key: str) -> None:
    """Delete *storage_key* only after confirming no database row references it.

    Opens a fresh database connection so the check is independent of the
    failed transaction.  If the DB check itself fails (e.g. the database is
    completely down), the artifact is preserved and the key is logged for
    manual reconciliation — we must not delete an artifact that may be
    referenced by a committed row we cannot see.
    """
    try:
        async with AsyncSessionLocal() as fresh_db:
            result = await fresh_db.execute(
                select(PR).where(PR.diff_storage_key == storage_key)
            )
            row = result.scalar_one_or_none()
    except Exception as db_err:
        # Database is unreachable or erroring; we cannot confirm the state.
        # Preserve the artifact and surface the key for later reconciliation.
        logger.error(
            "artifact-storage: could not confirm DB state after commit failure; "
            "preserving artifact for manual reconciliation. key=%r db_error=%r",
            storage_key,
            db_err,
        )
        return

    if row is not None:
        # A committed row references this key — the commit succeeded despite
        # the exception.  Do not delete.
        logger.warning(
            "artifact-storage: commit raised but DB row exists; artifact kept. key=%r",
            storage_key,
        )
        return

    # No row found — safe to delete the orphaned artifact.
    loop = asyncio.get_running_loop()
    store = get_artifact_store()
    try:
        await loop.run_in_executor(None, store.delete, storage_key)
        logger.info("artifact-storage: orphaned artifact deleted. key=%r", storage_key)
    except Exception as del_err:
        logger.error(
            "artifact-storage: failed to delete orphaned artifact; "
            "log key for manual cleanup. key=%r error=%r",
            storage_key,
            del_err,
        )


# ---------------------------------------------------------------------------
# GET /analyses/{id}
# ---------------------------------------------------------------------------


@router.get("/{analysis_id}", response_model=AnalysisOut)
async def get_analysis(
    analysis_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisOut:
    """Return analysis status and any completed facets."""
    result = await db.execute(
        select(Analysis)
        .join(Analysis.pr)
        .where(Analysis.id == analysis_id, PR.user_id == user.id)
        .options(
            selectinload(Analysis.facets).selectinload(Facet.findings)
        )
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return AnalysisOut.model_validate(analysis)


# ---------------------------------------------------------------------------
# GET /analyses/{id}/diff
# ---------------------------------------------------------------------------


@router.get("/{analysis_id}/diff")
async def get_analysis_diff(
    analysis_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return the raw unified diff for this analysis.

    The diff is retrieved from the ArtifactStore (local or S3) and served
    as ``text/x-patch``.  The bucket remains private; no public S3 URL is
    ever returned.
    """
    result = await db.execute(
        select(Analysis)
        .join(Analysis.pr)
        .where(Analysis.id == analysis_id, PR.user_id == user.id)
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    result2 = await db.execute(select(PR).where(PR.id == analysis.pr_id, PR.user_id == user.id))
    pr = result2.scalar_one_or_none()
    if pr is None:
        raise HTTPException(status_code=404, detail="PR record not found")  # pragma: no cover

    # Compatibility: prefer the artifact store; fall back to the inline diff
    # column that legacy rows (created before artifact storage was added) may
    # still carry.
    if not pr.diff_storage_key and not pr.diff:
        raise HTTPException(status_code=404, detail="No diff available for this analysis")

    if pr.diff_storage_key:
        store = get_artifact_store()
        loop = asyncio.get_running_loop()
        try:
            data = await loop.run_in_executor(None, store.get, pr.diff_storage_key)
        except KeyError:
            raise HTTPException(status_code=404, detail="Diff artifact missing from storage")
    else:
        # Legacy inline diff — encode to bytes for a uniform response.
        data = (pr.diff or "").encode()

    return Response(
        content=data,
        media_type="text/x-patch",
        headers={"Content-Disposition": f'attachment; filename="{pr.id}.patch"'},
    )


# ---------------------------------------------------------------------------
# GET /analyses/{id}/stream
# ---------------------------------------------------------------------------


async def _event_generator(
    analysis_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
) -> AsyncIterator[str]:
    """Poll persisted analysis state and emit progress until a terminal status."""
    previous: str | None = None
    while True:
        if await request.is_disconnected():
            return
        async with AsyncSessionLocal() as poll_db:
            result = await poll_db.execute(
                select(Analysis)
                .join(Analysis.pr)
                .where(Analysis.id == analysis_id, PR.user_id == user_id)
                .options(selectinload(Analysis.facets))
                .execution_options(populate_existing=True)
            )
            analysis = result.scalar_one_or_none()
            if analysis is None:
                return
            state = {
                "analysis_id": str(analysis.id),
                "status": analysis.status.value,
                "error": analysis.error,
                "facets": [
                    {"kind": facet.kind.value, "status": facet.status.value}
                    for facet in sorted(analysis.facets, key=lambda item: item.kind.value)
                ],
            }
            terminal = analysis.status in (AnalysisStatus.completed, AnalysisStatus.failed)

        encoded = json.dumps(state)
        if encoded != previous:
            yield f"event: progress\ndata: {encoded}\n\n"
            previous = encoded

        if terminal:
            yield f"event: done\ndata: {encoded}\n\n"
            return
        await asyncio.sleep(1)


@router.get("/{analysis_id}/stream")
async def stream_analysis(
    analysis_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """SSE endpoint — streams persisted analysis and facet status changes."""
    result = await db.execute(
        select(Analysis)
        .join(Analysis.pr)
        .where(Analysis.id == analysis_id, PR.user_id == user.id)
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return StreamingResponse(
        _event_generator(analysis_id, user.id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
