"""Analyses router — POST /analyses, GET /analyses/{id}, GET /analyses/{id}/stream."""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.ingestion import FileIngestion, GitHubIngestion
from app.models import Analysis, AnalysisStatus, PR
from app.schemas import AnalysisOut, CreateAnalysisRequest, CreateAnalysisResponse

router = APIRouter(prefix="/analyses", tags=["analyses"])


# ---------------------------------------------------------------------------
# POST /analyses
# ---------------------------------------------------------------------------


@router.post("", response_model=CreateAnalysisResponse, status_code=201)
async def create_analysis(
    body: CreateAnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> CreateAnalysisResponse:
    """Create a new Analysis row from a GitHub PR URL or a raw diff."""

    if body.github_pr_url:
        ingestion = GitHubIngestion()
        bundle = ingestion.ingest(body.github_pr_url)
        pr = PR(
            github_pr_url=bundle.github_pr_url,
            title=bundle.title or None,
            description=bundle.description or None,
            diff=bundle.diff_raw or None,
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
            diff=bundle.diff_raw or None,
        )

    db.add(pr)
    await db.flush()  # get pr.id

    analysis = Analysis(pr_id=pr.id, status=AnalysisStatus.pending)
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    return CreateAnalysisResponse(id=analysis.id)


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
