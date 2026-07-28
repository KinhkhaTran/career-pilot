"""Token-gated submission: approval tokens + browser-run submission evidence.

Adds the explicitly authorized submission path (ADR 0008). All changes are
additive; the default ``stop_before_submit`` boundary is unaffected.

Revision ID: 0008
Revises: 0007
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "browser_runs",
        sa.Column("final_page_fingerprint", sa.String(64), nullable=True),
    )
    op.add_column(
        "browser_runs",
        sa.Column("submitted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("browser_runs", sa.Column("confirmation", sa.JSON(), nullable=True))
    op.add_column(
        "browser_runs",
        sa.Column(
            "submission_mode",
            sa.String(32),
            nullable=False,
            server_default="stop_before_submit",
        ),
    )

    op.create_table(
        "approval_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "application_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "browser_run_id",
            sa.String(36),
            sa.ForeignKey("browser_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_id", sa.String(64), nullable=False, unique=True),
        sa.Column("binding_digest", sa.String(64), nullable=False),
        sa.Column("resume_version", sa.Integer(), nullable=False),
        sa.Column("answer_set_version", sa.Integer(), nullable=False),
        sa.Column("final_page_fingerprint", sa.String(64), nullable=False),
        sa.Column("consumed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_approval_tokens_application_id", "approval_tokens", ["application_id"]
    )
    op.create_index("ix_approval_tokens_run_id", "approval_tokens", ["browser_run_id"])


def downgrade() -> None:
    op.drop_index("ix_approval_tokens_run_id", table_name="approval_tokens")
    op.drop_index("ix_approval_tokens_application_id", table_name="approval_tokens")
    op.drop_table("approval_tokens")
    op.drop_column("browser_runs", "submission_mode")
    op.drop_column("browser_runs", "confirmation")
    op.drop_column("browser_runs", "submitted")
    op.drop_column("browser_runs", "final_page_fingerprint")
