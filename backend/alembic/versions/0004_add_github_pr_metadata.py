"""persist GitHub pull request identity and revision SHAs

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("prs", sa.Column("repo_full_name", sa.Text(), nullable=True))
    op.add_column("prs", sa.Column("pr_number", sa.Integer(), nullable=True))
    op.add_column("prs", sa.Column("head_sha", sa.Text(), nullable=True))
    op.add_column("prs", sa.Column("base_sha", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("prs", "base_sha")
    op.drop_column("prs", "head_sha")
    op.drop_column("prs", "pr_number")
    op.drop_column("prs", "repo_full_name")
