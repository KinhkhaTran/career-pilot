"""Persist approval-bound assisted browser runs.

Revision ID: 0006
Revises: 0005
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "browser_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(64), nullable=False, server_default="queued"),
        sa.Column("packet_fingerprint", sa.JSON(), nullable=False),
        sa.Column("immutable_inputs", sa.JSON(), nullable=False),
        sa.Column("approved_fields", sa.JSON(), nullable=False),
        sa.Column("headless", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("adapter_name", sa.String(100), nullable=False),
        sa.Column("stopped_before_submit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_browser_runs_application_id", "browser_runs", ["application_id"])
    for table, event_col in (("browser_run_steps", "action"), ("browser_run_events", "event_type")):
        op.create_table(
            table,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("run_id", sa.String(36), sa.ForeignKey("browser_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column(event_col, sa.String(64 if table == "browser_run_steps" else 100), nullable=False),
            sa.Column("detail", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index(f"ix_{table}_run_id", table, ["run_id"])
    op.create_table(
        "browser_screenshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("browser_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_browser_screenshots_run_id", "browser_screenshots", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_browser_screenshots_run_id", table_name="browser_screenshots")
    op.drop_table("browser_screenshots")
    for table in ("browser_run_events", "browser_run_steps"):
        op.drop_index(f"ix_{table}_run_id", table_name=table)
        op.drop_table(table)
    op.drop_index("ix_browser_runs_application_id", table_name="browser_runs")
    op.drop_table("browser_runs")
