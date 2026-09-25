"""add_artifact_storage_columns_to_prs

Adds diff_storage_key, diff_size_bytes, and diff_sha256 columns to the prs
table.  The existing diff (TEXT) column is kept nullable for backward
compatibility; new rows will leave it NULL and store the diff via ArtifactStore.

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-02 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("prs", sa.Column("diff_storage_key", sa.Text(), nullable=True))
    op.add_column("prs", sa.Column("diff_size_bytes", sa.BigInteger(), nullable=True))
    op.add_column("prs", sa.Column("diff_sha256", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("prs", "diff_sha256")
    op.drop_column("prs", "diff_size_bytes")
    op.drop_column("prs", "diff_storage_key")
