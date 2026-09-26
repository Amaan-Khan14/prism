"""add coverage provenance columns to analyses

Adds columns that persist the coverage intake outcome for each analysis:
- coverage_status: 'accepted', 'rejected', or 'none' (no artifact supplied)
- coverage_rejection_reason: human-readable rejection message (NULL when accepted or none)
- coverage_format: 'lcov' or 'cobertura' (NULL when not accepted)
- coverage_ci_provider: e.g. 'github_actions' (NULL when not accepted)
- coverage_run_id: provider-specific run identifier (NULL when not accepted)
- coverage_artifact_name: optional artifact name within the run (NULL when not accepted)
- coverage_commit_sha: verified commit SHA (NULL when not accepted)
- coverage_artifact_sha256: hex SHA-256 of the raw artifact bytes (NULL when not accepted)
- coverage_parsed_at: UTC timestamp of acceptance (NULL when not accepted)
- coverage_file_count: number of files in the parsed artifact (NULL when not accepted)
- coverage_parser_warnings: JSON array of non-fatal parser warnings

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # coverage_status uses a simple text column with a check constraint rather
    # than a PostgreSQL enum so we can add new values without a migration.
    op.add_column(
        "analyses",
        sa.Column(
            "coverage_status",
            sa.Text(),
            nullable=True,
            comment="'accepted' | 'rejected' | 'none'",
        ),
    )
    op.add_column(
        "analyses",
        sa.Column(
            "coverage_rejection_reason",
            sa.Text(),
            nullable=True,
            comment="Human-readable rejection reason when coverage_status = 'rejected'",
        ),
    )
    op.add_column(
        "analyses",
        sa.Column(
            "coverage_format",
            sa.Text(),
            nullable=True,
            comment="'lcov' or 'cobertura'",
        ),
    )
    op.add_column(
        "analyses",
        sa.Column("coverage_ci_provider", sa.Text(), nullable=True),
    )
    op.add_column(
        "analyses",
        sa.Column("coverage_run_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "analyses",
        sa.Column("coverage_artifact_name", sa.Text(), nullable=True),
    )
    op.add_column(
        "analyses",
        sa.Column(
            "coverage_commit_sha",
            sa.Text(),
            nullable=True,
            comment="Commit SHA the artifact was verified against",
        ),
    )
    op.add_column(
        "analyses",
        sa.Column(
            "coverage_artifact_sha256",
            sa.Text(),
            nullable=True,
            comment="Hex SHA-256 of the raw artifact bytes",
        ),
    )
    op.add_column(
        "analyses",
        sa.Column(
            "coverage_parsed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC timestamp when the artifact was accepted and parsed",
        ),
    )
    op.add_column(
        "analyses",
        sa.Column(
            "coverage_file_count",
            sa.Integer(),
            nullable=True,
            comment="Number of distinct files in the parsed artifact",
        ),
    )
    op.add_column(
        "analyses",
        sa.Column(
            "coverage_parser_warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
            comment="Non-fatal parser warnings from artifact parsing",
        ),
    )

    # Add a check constraint so the column only holds the three valid values.
    op.create_check_constraint(
        "ck_analyses_coverage_status",
        "analyses",
        "coverage_status IN ('accepted', 'rejected', 'none')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_analyses_coverage_status", "analyses", type_="check")
    op.drop_column("analyses", "coverage_parser_warnings")
    op.drop_column("analyses", "coverage_file_count")
    op.drop_column("analyses", "coverage_parsed_at")
    op.drop_column("analyses", "coverage_artifact_sha256")
    op.drop_column("analyses", "coverage_commit_sha")
    op.drop_column("analyses", "coverage_artifact_name")
    op.drop_column("analyses", "coverage_run_id")
    op.drop_column("analyses", "coverage_ci_provider")
    op.drop_column("analyses", "coverage_format")
    op.drop_column("analyses", "coverage_rejection_reason")
    op.drop_column("analyses", "coverage_status")
