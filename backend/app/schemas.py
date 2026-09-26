"""Pydantic schemas for request / response bodies."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.models import AnalysisStatus, FacetKind, FacetStatus


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CreateAnalysisRequest(BaseModel):
    """Accepts either a GitHub PR URL or a raw diff+metadata."""

    github_pr_url: Optional[str] = None
    diff: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None

    @model_validator(mode="after")
    def at_least_one_source(self) -> "CreateAnalysisRequest":
        if not self.github_pr_url and not self.diff:
            raise ValueError("Provide either github_pr_url or diff.")
        return self


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class CreateAnalysisResponse(BaseModel):
    id: uuid.UUID


class PROut(BaseModel):
    """PR metadata shown alongside an analysis."""

    id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    repo_full_name: Optional[str] = None
    pr_number: Optional[int] = None
    github_pr_url: Optional[str] = None
    head_sha: Optional[str] = None
    base_sha: Optional[str] = None

    model_config = {"from_attributes": True}


class FindingOut(BaseModel):
    id: uuid.UUID
    verdict: str
    severity: int
    summary: str
    claim_type: Optional[str] = None
    citation_file: Optional[str] = None
    citation_line: Optional[int] = None
    citations: List[dict] = Field(default_factory=list)
    gate_reasons: List[str] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class FacetOut(BaseModel):
    id: uuid.UUID
    kind: FacetKind
    status: FacetStatus
    created_at: datetime
    updated_at: datetime
    findings: List[FindingOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AnalysisOut(BaseModel):
    id: uuid.UUID
    status: AnalysisStatus
    error: Optional[str]
    created_at: datetime
    updated_at: datetime
    pr: PROut
    coverage_status: Optional[str] = None
    coverage_rejection_reason: Optional[str] = None
    coverage_format: Optional[str] = None
    coverage_ci_provider: Optional[str] = None
    coverage_run_id: Optional[str] = None
    coverage_run_attempt: Optional[str] = None
    coverage_artifact_name: Optional[str] = None
    coverage_commit_sha: Optional[str] = None
    coverage_artifact_sha256: Optional[str] = None
    coverage_parsed_at: Optional[datetime] = None
    coverage_file_count: Optional[int] = None
    coverage_parser_warnings: Optional[list[str]] = None
    facets: List[FacetOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AnalysisListItem(BaseModel):
    """One row of the signed-in user's analysis history (GET /analyses)."""

    id: uuid.UUID
    status: AnalysisStatus
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    pr: PROut

    model_config = {"from_attributes": True}
