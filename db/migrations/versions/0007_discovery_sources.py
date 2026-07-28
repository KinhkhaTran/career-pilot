"""Configurable discovery source list for the scheduler.

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
        "discovery_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("company_id", sa.String(256), nullable=False),
        sa.Column("label", sa.String(200)),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.UniqueConstraint("source", "company_id", name="uq_discovery_source"),
    )
    op.create_index("ix_discovery_sources_enabled", "discovery_sources", ["enabled"])

    # Seed a couple of real public boards so the scheduler has work on first run.
    # These are public, read-only ATS boards — not fake PII.
    sources = sa.table(
        "discovery_sources",
        sa.column("id", sa.String),
        sa.column("source", sa.String),
        sa.column("company_id", sa.String),
        sa.column("label", sa.String),
        sa.column("enabled", sa.Boolean),
    )
    op.bulk_insert(
        sources,
        [
            {
                "id": "00000000-0000-0000-0000-0000000000a1",
                "source": "greenhouse",
                "company_id": "figma",
                "label": "Figma",
                "enabled": True,
            },
            {
                "id": "00000000-0000-0000-0000-0000000000a2",
                "source": "greenhouse",
                "company_id": "gitlab",
                "label": "GitLab",
                "enabled": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_discovery_sources_enabled", table_name="discovery_sources")
    op.drop_table("discovery_sources")
