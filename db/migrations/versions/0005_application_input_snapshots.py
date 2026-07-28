"""Persist immutable application material inputs.

Revision ID: 0005
Revises: 0004
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("profile_version", sa.Integer(), nullable=True))
    op.add_column("applications", sa.Column("job_snapshot_hash", sa.String(64), nullable=True))
    op.add_column("applications", sa.Column("job_snapshot", sa.JSON(), nullable=True))
    op.create_index("ix_applications_job_snapshot_hash", "applications", ["job_snapshot_hash"])


def downgrade() -> None:
    op.drop_index("ix_applications_job_snapshot_hash", table_name="applications")
    op.drop_column("applications", "job_snapshot")
    op.drop_column("applications", "job_snapshot_hash")
    op.drop_column("applications", "profile_version")
