"""Candidate preferences, resumable assisted-run state, and mock ATS receipts.

Revision ID: 0007
Revises: 0006
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_preferences",
        sa.Column("row_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("candidate_profile_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("remote_only", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allowed_locations", sa.JSON(), nullable=True),
        sa.Column("employment_types", sa.JSON(), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=True),
        sa.Column("min_salary", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("candidate_profile_id", "version", name="uq_preference_version"),
    )
    op.create_index(
        "ix_candidate_preferences_candidate_profile_id",
        "candidate_preferences",
        ["candidate_profile_id"],
    )

    # Resumable, human-supervised assisted-run state.
    op.add_column(
        "browser_runs",
        sa.Column("mode", sa.String(32), nullable=False, server_default="mock_sandbox"),
    )
    op.add_column(
        "browser_runs",
        sa.Column("target_kind", sa.String(32), nullable=False, server_default="mock_ats"),
    )
    op.add_column(
        "browser_runs", sa.Column("target_url", sa.Text(), nullable=False, server_default="")
    )
    op.add_column("browser_runs", sa.Column("plan", sa.JSON(), nullable=True))
    op.add_column(
        "browser_runs", sa.Column("cursor", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("browser_runs", sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE browser_runs SET plan = '[]' WHERE plan IS NULL")
    op.alter_column("browser_runs", "plan", nullable=False)

    op.create_table(
        "mock_ats_submissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("board_token", sa.String(128), nullable=False),
        sa.Column("external_job_id", sa.String(256), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("browser_run_id", sa.String(36), nullable=True),
        sa.Column("confirmation_code", sa.String(64), nullable=False),
        sa.Column("packet_hash", sa.String(64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_mock_ats_idempotency"),
    )
    op.create_index(
        "ix_mock_ats_submissions_application_id", "mock_ats_submissions", ["application_id"]
    )
    op.create_index(
        "ix_mock_ats_submissions_browser_run_id", "mock_ats_submissions", ["browser_run_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_mock_ats_submissions_browser_run_id", table_name="mock_ats_submissions")
    op.drop_index("ix_mock_ats_submissions_application_id", table_name="mock_ats_submissions")
    op.drop_table("mock_ats_submissions")

    for column in ("paused_at", "cursor", "plan", "target_url", "target_kind", "mode"):
        op.drop_column("browser_runs", column)

    op.drop_index(
        "ix_candidate_preferences_candidate_profile_id", table_name="candidate_preferences"
    )
    op.drop_table("candidate_preferences")
