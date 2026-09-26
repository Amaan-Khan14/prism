"""add PRism users and per-user GitHub App installation ownership

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("github_user_id", sa.BigInteger(), nullable=False),
        sa.Column("github_login", sa.Text(), nullable=False),
        sa.Column("github_name", sa.Text(), nullable=True),
        sa.Column("github_token_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("github_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("github_refresh_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("github_user_id", name="uq_users_github_user_id"),
    )
    op.create_table(
        "github_installations",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("account_login", sa.Text(), nullable=False),
        sa.Column("account_type", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "user_github_installations",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["installation_id"], ["github_installations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "installation_id"),
    )
    op.add_column("prs", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("prs", sa.Column("github_installation_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_prs_user_id_users", "prs", "users", ["user_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key(
        "fk_prs_github_installation_id_github_installations",
        "prs",
        "github_installations",
        ["github_installation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_prs_user_id", "prs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_prs_user_id", table_name="prs")
    op.drop_constraint("fk_prs_github_installation_id_github_installations", "prs", type_="foreignkey")
    op.drop_constraint("fk_prs_user_id_users", "prs", type_="foreignkey")
    op.drop_column("prs", "github_installation_id")
    op.drop_column("prs", "user_id")
    op.drop_table("user_github_installations")
    op.drop_table("github_installations")
    op.drop_table("users")
