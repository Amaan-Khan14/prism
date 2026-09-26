"""SQLAlchemy ORM models for PRism."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Index,
    LargeBinary,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


user_github_installations = Table(
    "user_github_installations",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("installation_id", BigInteger, ForeignKey("github_installations.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


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


class User(Base):
    """PRism user authenticated through the GitHub App OAuth flow."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    github_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    github_login: Mapped[str] = mapped_column(Text, nullable=False)
    github_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    github_token_ciphertext: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    github_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    github_refresh_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    installations: Mapped[List["GitHubInstallation"]] = relationship(
        secondary=user_github_installations, back_populates="users"
    )


class GitHubInstallation(Base):
    """An installation of PRism's GitHub App on a user or organization account."""

    __tablename__ = "github_installations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    account_login: Mapped[str] = mapped_column(Text, nullable=False)
    account_type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    users: Mapped[List[User]] = relationship(
        secondary=user_github_installations, back_populates="installations"
    )


class PR(Base):
    """Represents a pull-request input (either a GitHub URL or a raw diff)."""

    __tablename__ = "prs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    github_pr_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    github_installation_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("github_installations.id", ondelete="SET NULL"), nullable=True
    )
    repo_full_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pr_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    head_sha: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    base_sha: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Legacy inline diff column — kept nullable for backward compatibility with
    # existing rows and local dev without a storage backend.  New rows store the
    # diff via ArtifactStore and set diff=None.
    diff: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Artifact-storage references (populated when diff is stored externally)
    diff_storage_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    """Object key within the configured ArtifactStore (e.g. ``diffs/<id>.patch``)."""

    diff_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    """Exact byte length of the stored diff."""

    diff_sha256: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    """Hex SHA-256 of the diff bytes, for integrity verification."""

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
    facts_storage_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ------------------------------------------------------------------
    # Coverage provenance — populated by the coverage intake pipeline.
    # coverage_status distinguishes three states:
    #   'accepted'  — artifact was validated and parsed successfully.
    #   'rejected'  — artifact was supplied but failed SHA/parse checks.
    #   'none'      — no artifact was supplied for this analysis.
    # NULL means this analysis pre-dates coverage intake support.
    # ------------------------------------------------------------------
    coverage_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    coverage_rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    coverage_format: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    coverage_ci_provider: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    coverage_run_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    coverage_run_attempt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    coverage_artifact_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    coverage_commit_sha: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    coverage_artifact_sha256: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    coverage_parsed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    coverage_file_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    coverage_parser_warnings: Mapped[Optional[list]] = mapped_column(
        JSONB, nullable=True, server_default=text("'[]'::jsonb")
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

    pr: Mapped["PR"] = relationship(back_populates="analyses")
    facets: Mapped[List["Facet"]] = relationship(back_populates="analysis")


class CoverageArtifactRecord(Base):
    """Raw report uploaded by a trusted GitHub Actions OIDC workflow."""

    __tablename__ = "coverage_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "repo_full_name", "commit_sha", "run_id", "run_attempt",
            name="uq_coverage_artifacts_run",
        ),
        Index("ix_coverage_artifacts_repo_sha_created", "repo_full_name", "commit_sha", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_full_name: Mapped[str] = mapped_column(Text, nullable=False)
    commit_sha: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str] = mapped_column(Text, nullable=False)
    run_attempt: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_ref: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    format: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


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
    claim_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    citations: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    gate_reasons: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    citation_file: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    citation_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    raw_llm_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    facet: Mapped["Facet"] = relationship(back_populates="findings")
