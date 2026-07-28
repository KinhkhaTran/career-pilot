"""Add truthful application materials and reusable answer library.

Revision ID: 0004
Revises: 0003
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_materials",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("diff", sa.Text(), nullable=True),
        sa.Column("source_claims", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", "kind", "version", name="uq_material_version"),
    )
    op.create_index("ix_application_materials_application_id", "application_materials", ["application_id"])
    op.create_table(
        "answer_library",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("candidate_profile_id", sa.String(36), nullable=False),
        sa.Column("question_key", sa.String(128), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_profile_id", "question_key", "version", name="uq_answer_version"),
    )
    op.create_index("ix_answer_library_candidate_profile_id", "answer_library", ["candidate_profile_id"])


def downgrade() -> None:
    op.drop_index("ix_answer_library_candidate_profile_id", table_name="answer_library")
    op.drop_table("answer_library")
    op.drop_index("ix_application_materials_application_id", table_name="application_materials")
    op.drop_table("application_materials")
