"""Add discovery_runs and discovery_run_events tables.

Revision ID: 0002
Revises: 0001
Create Date: 2024-07-15 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # discovery_runs
    # Tracks each scheduled or manual job-discovery run.
    # idempotency_key prevents double-enqueuing the same run.
    # Status: pending → running → completed | failed
    # ------------------------------------------------------------------
    op.create_table(
        "discovery_runs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("company_id", sa.String(256), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("jobs_discovered", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("jobs_upserted", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("jobs_skipped", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_discovery_run_idempotency_key"),
    )
    op.create_index(
        op.f("ix_discovery_runs_source"),
        "discovery_runs",
        ["source"],
        unique=False,
    )
    op.create_index(
        op.f("ix_discovery_runs_status"),
        "discovery_runs",
        ["status"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # discovery_run_events
    # Immutable append-only milestones for each discovery run.
    # Rows are never updated or deleted.
    # ------------------------------------------------------------------
    op.create_table(
        "discovery_run_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("discovery_run_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["discovery_run_id"],
            ["discovery_runs.id"],
            name="fk_discovery_run_events_run_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_discovery_run_events_discovery_run_id"),
        "discovery_run_events",
        ["discovery_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_discovery_run_events_discovery_run_id"),
        table_name="discovery_run_events",
    )
    op.drop_table("discovery_run_events")

    op.drop_index(op.f("ix_discovery_runs_status"), table_name="discovery_runs")
    op.drop_index(op.f("ix_discovery_runs_source"), table_name="discovery_runs")
    op.drop_table("discovery_runs")
