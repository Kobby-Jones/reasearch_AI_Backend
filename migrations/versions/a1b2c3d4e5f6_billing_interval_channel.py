"""add billing interval, channel and cancel_at_period_end

Revision ID: a1b2c3d4e5f6
Revises: cf16716419f5
Create Date: 2026-06-15

Adds the columns the richer billing flow needs:
  - payments.channel        (mobile_money | card)
  - payments.interval       (monthly | annual)
  - subscriptions.interval  (monthly | annual)
  - subscriptions.cancel_at_period_end (bool)
All are additive and backwards-compatible with existing rows.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "cf16716419f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("payments") as batch:
        batch.add_column(sa.Column("channel", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("interval", sa.String(length=16), nullable=True))

    with op.batch_alter_table("subscriptions") as batch:
        batch.add_column(sa.Column("interval", sa.String(length=16), nullable=True))
        batch.add_column(
            sa.Column(
                "cancel_at_period_end",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    # Backfill sensible defaults for existing rows.
    op.execute("UPDATE payments SET channel = 'card' WHERE channel IS NULL")
    op.execute("UPDATE payments SET interval = 'monthly' WHERE interval IS NULL")
    op.execute("UPDATE subscriptions SET interval = 'monthly' WHERE interval IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch:
        batch.drop_column("cancel_at_period_end")
        batch.drop_column("interval")

    with op.batch_alter_table("payments") as batch:
        batch.drop_column("interval")
        batch.drop_column("channel")
