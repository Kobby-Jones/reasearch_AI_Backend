"""batch 6: notifications, shared reports, growth fields

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-15

Adds in-app notifications, public shareable report snapshots, and the user-level
growth fields (student verification + referral program).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users: growth fields
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("student_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("referral_code", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("referred_by_id", sa.Integer(), nullable=True))
    op.create_index("ix_users_referral_code", "users", ["referral_code"], unique=True)

    # notifications
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False, server_default="info"),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("link", sa.String(length=255), nullable=True),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_read", "notifications", ["read"])

    # shared_reports
    op.create_table(
        "shared_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("html", sa.Text(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_shared_reports_user_id", "shared_reports", ["user_id"])
    op.create_index("ix_shared_reports_project_id", "shared_reports", ["project_id"])
    op.create_index("ix_shared_reports_token", "shared_reports", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_shared_reports_token", table_name="shared_reports")
    op.drop_index("ix_shared_reports_project_id", table_name="shared_reports")
    op.drop_index("ix_shared_reports_user_id", table_name="shared_reports")
    op.drop_table("shared_reports")
    op.drop_index("ix_notifications_read", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_users_referral_code", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("referred_by_id")
        batch.drop_column("referral_code")
        batch.drop_column("student_verified")
