"""create project_references table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-15

Batch 2: reference / citation manager. A curated, persistent per-project library
of real scholarly references that also feeds the report writer.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_references",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("citation_key", sa.String(length=64), nullable=False),
        sa.Column("authors", sa.JSON(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("container", sa.Text(), nullable=True),
        sa.Column("volume", sa.String(length=32), nullable=True),
        sa.Column("issue", sa.String(length=32), nullable=True),
        sa.Column("pages", sa.String(length=64), nullable=True),
        sa.Column("doi", sa.String(length=255), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("cited_by", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_project_references_project_id", "project_references", ["project_id"])
    op.create_index("ix_project_references_user_id", "project_references", ["user_id"])
    op.create_index("ix_project_references_doi", "project_references", ["doi"])


def downgrade() -> None:
    op.drop_index("ix_project_references_doi", table_name="project_references")
    op.drop_index("ix_project_references_user_id", table_name="project_references")
    op.drop_index("ix_project_references_project_id", table_name="project_references")
    op.drop_table("project_references")
