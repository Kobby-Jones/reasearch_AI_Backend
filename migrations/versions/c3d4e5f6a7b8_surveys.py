"""create survey and survey_responses tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-15

Batch 2: live survey distribution. A questionnaire can be published as a public
survey; responses are collected and later imported into a dataset.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "surveys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("questionnaire_id", sa.Integer(), sa.ForeignKey("questionnaires.id", ondelete="CASCADE"), nullable=False),
        sa.Column("public_token", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("structure", sa.JSON(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_surveys_user_id", "surveys", ["user_id"])
    op.create_index("ix_surveys_project_id", "surveys", ["project_id"])
    op.create_index("ix_surveys_questionnaire_id", "surveys", ["questionnaire_id"])
    op.create_index("ix_surveys_public_token", "surveys", ["public_token"], unique=True)

    op.create_table(
        "survey_responses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("survey_id", sa.Integer(), sa.ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_survey_responses_survey_id", "survey_responses", ["survey_id"])


def downgrade() -> None:
    op.drop_index("ix_survey_responses_survey_id", table_name="survey_responses")
    op.drop_table("survey_responses")
    op.drop_index("ix_surveys_public_token", table_name="surveys")
    op.drop_index("ix_surveys_questionnaire_id", table_name="surveys")
    op.drop_index("ix_surveys_project_id", table_name="surveys")
    op.drop_index("ix_surveys_user_id", table_name="surveys")
    op.drop_table("surveys")
