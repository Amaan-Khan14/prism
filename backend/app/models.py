"""SQLAlchemy ORM models for PRism."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class AnalysisStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class FacetKind(str, enum.Enum):
    intent_vs_spec = "intent_vs_spec"
    cross_file_impact = "cross_file_impact"
    test_coverage_gaps = "test_coverage_gaps"
    risk_hazards = "risk_hazards"


class FacetStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class FindingVerdict(str, enum.Enum):
    verified = "verified"
    unverified = "unverified"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class PR(Base):
    """Represents a pull-request input (either a GitHub URL or a raw diff)."""

    __tablename__ = "prs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    github_pr_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    diff: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analyses: Mapped[List["Analysis"]] = relationship(back_populates="pr")


class Analysis(Base):
    """A single review run against a PR."""

    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pr_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prs.id"), nullable=False
    )
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus, name="analysisstatus"),
        default=AnalysisStatus.pending,
        nullable=False,
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    pr: Mapped["PR"] = relationship(back_populates="analyses")
    facets: Mapped[List["Facet"]] = relationship(back_populates="analysis")


class Facet(Base):
    """One of the four parallel review facets within an Analysis."""

    __tablename__ = "facets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id"), nullable=False
    )
    kind: Mapped[FacetKind] = mapped_column(
        Enum(FacetKind, name="facetkind"), nullable=False
    )
    status: Mapped[FacetStatus] = mapped_column(
        Enum(FacetStatus, name="facetstatus"),
        default=FacetStatus.pending,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    analysis: Mapped["Analysis"] = relationship(back_populates="facets")
    findings: Mapped[List["Finding"]] = relationship(back_populates="facet")


class Finding(Base):
    """A single finding produced by a facet, with evidence gate verdict."""

    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    facet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facets.id"), nullable=False
    )
    verdict: Mapped[FindingVerdict] = mapped_column(
        Enum(FindingVerdict, name="findingverdict"), nullable=False
    )
    severity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    citation_file: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    citation_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    raw_llm_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    facet: Mapped["Facet"] = relationship(back_populates="findings")
