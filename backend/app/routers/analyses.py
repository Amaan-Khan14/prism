"""Analyses router — POST /analyses, GET /analyses/{id}, GET /analyses/{id}/stream, GET /analyses/{id}/diff."""
from __future__ import annotations

import asyncio
import functools
import json
import logging
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal, get_db
from app.ingestion import FileIngestion, GitHubIngestion
from app.models import Analysis, AnalysisStatus, PR
from app.schemas import AnalysisOut, CreateAnalysisRequest, CreateAnalysisResponse
from app.storage import diff_key, get_artifact_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyses", tags=["analyses"])


# ---------------------------------------------------------------------------
# POST /analyses
# ---------------------------------------------------------------------------


@router.post("", response_model=CreateAnalysisResponse, status_code=201)
async def create_analysis(
    body: CreateAnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> CreateAnalysisResponse:
    """Create a new Analysis row from a GitHub PR URL or a raw diff.

    The raw diff (if any) is stored via the configured ArtifactStore.
    Only the storage key, size, and checksum are persisted in PostgreSQL;
    the diff bytes are never written into the database row.
    """
    if body.github_pr_url:
        ingestion = GitHubIngestion()
        bundle = ingestion.ingest(body.github_pr_url)
        pr = PR(
            github_pr_url=bundle.github_pr_url,
            title=bundle.title or None,
            description=bundle.description or None,
        )
    else:
        ingestion = FileIngestion()
        bundle = ingestion.ingest(
            diff=body.diff or "",
            title=body.title or "",
            description=body.description or "",
        )
        pr = PR(
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
    db: AsyncSession = Depends(get_db),
) -> AnalysisOut:
    """Return analysis status and any completed facets."""
    result = await db.execute(
        select(Analysis)
        .where(Analysis.id == analysis_id)
        .options(selectinload(Analysis.facets))
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
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return the raw unified diff for this analysis.

    The diff is retrieved from the ArtifactStore (local or S3) and served
    as ``text/x-patch``.  The bucket remains private; no public S3 URL is
    ever returned.
    """
    result = await db.execute(
        select(Analysis).where(Analysis.id == analysis_id)
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    result2 = await db.execute(select(PR).where(PR.id == analysis.pr_id))
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


async def _event_generator(analysis_id: uuid.UUID) -> AsyncIterator[str]:
    """Yield SSE-formatted events.  Currently emits a static ping then closes."""
    ping = {"event": "ping", "analysis_id": str(analysis_id)}
    yield f"event: ping\ndata: {json.dumps(ping)}\n\n"
    # Simulate async work before the stream closes.
    await asyncio.sleep(0)
    done = {"event": "done", "analysis_id": str(analysis_id)}
    yield f"event: done\ndata: {json.dumps(done)}\n\n"


@router.get("/{analysis_id}/stream")
async def stream_analysis(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """SSE endpoint — emits a ping event to prove the streaming path works."""
    result = await db.execute(
        select(Analysis).where(Analysis.id == analysis_id)
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return StreamingResponse(
        _event_generator(analysis_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
