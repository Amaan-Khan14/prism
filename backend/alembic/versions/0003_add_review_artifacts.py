"""add facts artifact references and structured finding evidence

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analyses", sa.Column("facts_storage_key", sa.Text(), nullable=True))
    op.add_column("findings", sa.Column("claim_type", sa.Text(), nullable=True))
    op.add_column(
        "findings",
        sa.Column(
            "citations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "findings",
        sa.Column(
            "gate_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("findings", "gate_reasons")
    op.drop_column("findings", "citations")
    op.drop_column("findings", "claim_type")
    op.drop_column("analyses", "facts_storage_key")
