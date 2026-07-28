"""Initial schema — all core tables.

Revision ID: 0001
Revises: (none)
Create Date: 2024-07-01 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # candidate_profiles
    # Append-only versioned table: row_id is the surrogate PK,
    # `id` (candidate UUID) + `version` form the logical unique key.
    # The `id` column is indexed separately so lookups by candidate UUID
    # are fast across all version rows.
    # ------------------------------------------------------------------
    op.create_table(
        "candidate_profiles",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("contact_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("work_experience", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("education", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("certifications", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("skills", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("languages", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("id", "version", name="uq_profile_id_version"),
    )
    op.create_index(
        op.f("ix_candidate_profiles_id"),
        "candidate_profiles",
        ["id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # jobs
    # Normalised job posting snapshot, deduplicated by (source, external_id).
    # snapshot_hash is a SHA-256 hex of canonical fields for change detection.
    # ------------------------------------------------------------------
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("external_id", sa.String(256), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("is_remote", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("employment_type", sa.String(64), nullable=True),
        sa.Column("salary_range", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("nice_to_have", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("technologies", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status",
            sa.String(64),
            nullable=False,
            server_default=sa.text("'discovered'"),
        ),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("normalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "external_id", name="uq_job_source_external_id"),
    )
    op.create_index(
        op.f("ix_jobs_snapshot_hash"),
        "jobs",
        ["snapshot_hash"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # applications
    # Tracks the lifecycle of a candidate's application for a single job.
    # `status` is managed exclusively by the state machine.
    # `packet_fingerprint` captures approved packet versions at approval time.
    #
    # Note: candidate_profile_id carries a logical reference to
    # candidate_profiles.id (the candidate UUID) across all version rows.
    # A formal DB-level FK is intentionally omitted here because
    # candidate_profiles.id is not unique per row (multiple version rows
    # share the same candidate UUID). The integrity is enforced by the
    # service layer.
    # ------------------------------------------------------------------
    op.create_table(
        "applications",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("candidate_profile_id", sa.String(36), nullable=False),
        sa.Column(
            "status",
            sa.String(64),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("packet_fingerprint", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name="fk_applications_job_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_applications_job_id"),
        "applications",
        ["job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_applications_candidate_profile_id"),
        "applications",
        ["candidate_profile_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # application_events
    # Immutable, append-only audit log of every status transition.
    # Rows are NEVER updated or deleted.
    # ------------------------------------------------------------------
    op.create_table(
        "application_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("from_status", sa.String(64), nullable=True),
        sa.Column("to_status", sa.String(64), nullable=False),
        sa.Column("triggered_by", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(256), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_application_events_application_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_application_events_application_id"),
        "application_events",
        ["application_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_application_events_application_id"),
        table_name="application_events",
    )
    op.drop_table("application_events")

    op.drop_index(
        op.f("ix_applications_candidate_profile_id"),
        table_name="applications",
    )
    op.drop_index(op.f("ix_applications_job_id"), table_name="applications")
    op.drop_table("applications")

    op.drop_index(op.f("ix_jobs_snapshot_hash"), table_name="jobs")
    op.drop_table("jobs")

    op.drop_index(
        op.f("ix_candidate_profiles_id"),
        table_name="candidate_profiles",
    )
    op.drop_table("candidate_profiles")
