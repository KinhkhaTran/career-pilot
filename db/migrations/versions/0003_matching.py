"""Add deterministic job/profile matching results.

Revision ID: 0003
Revises: 0002
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "matches",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("candidate_profile_id", sa.String(36), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("explanation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name="fk_matches_job_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id", "candidate_profile_id", "profile_version", "input_fingerprint",
            name="uq_match_input",
        ),
    )
    op.create_index("ix_matches_candidate_profile_id", "matches", ["candidate_profile_id"])
    op.create_index("ix_matches_score", "matches", ["score"])


def downgrade() -> None:
    op.drop_index("ix_matches_score", table_name="matches")
    op.drop_index("ix_matches_candidate_profile_id", table_name="matches")
    op.drop_table("matches")
