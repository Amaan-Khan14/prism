"""persist trusted coverage upload references

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analyses", sa.Column("coverage_run_attempt", sa.Text(), nullable=True))
    op.create_table(
        "coverage_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repo_full_name", sa.Text(), nullable=False),
        sa.Column("commit_sha", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("run_attempt", sa.Text(), nullable=False),
        sa.Column("workflow_ref", sa.Text(), nullable=False),
        sa.Column("artifact_name", sa.Text(), nullable=True),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("artifact_sha256", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_coverage_artifacts_storage_key"),
        sa.UniqueConstraint(
            "repo_full_name", "commit_sha", "run_id", "run_attempt",
            name="uq_coverage_artifacts_run",
        ),
    )
    op.create_index(
        "ix_coverage_artifacts_repo_sha_created",
        "coverage_artifacts",
        ["repo_full_name", "commit_sha", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_coverage_artifacts_repo_sha_created", table_name="coverage_artifacts")
    op.drop_table("coverage_artifacts")
    op.drop_column("analyses", "coverage_run_attempt")
