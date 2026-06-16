"""add onboarding_completed and project is_sample

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-15

Supports Batch 1 activation features:
  - users.onboarding_completed     (bool) - has the user finished the tour
  - research_projects.is_sample    (bool) - the pre-loaded demo project
Both are additive and default to false for existing rows.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table("research_projects") as batch:
        batch.add_column(
            sa.Column("is_sample", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("research_projects") as batch:
        batch.drop_column("is_sample")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("onboarding_completed")
