"""add dataset versioning columns

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-15

Batch 3: dataset versioning. A revised upload supersedes a prior dataset and its
analyses are re-run, so corrections propagate.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("datasets") as batch:
        batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("supersedes_id", sa.Integer(), nullable=True))
    op.execute("UPDATE datasets SET version = 1 WHERE version IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("datasets") as batch:
        batch.drop_column("supersedes_id")
        batch.drop_column("version")
