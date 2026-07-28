"""
Seed the database with fake data.
Requires DB to be running and migrated.
Run: python db/seeds/run_seeds.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime

# Ensure the db package root is importable when run directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://careerpilot:careerpilot@localhost:5432/careerpilot",
)

# Timestamp columns are passed to asyncpg, which (unlike psycopg2) requires real
# datetime objects rather than ISO-8601 strings. Normalize these fields up front.
_TIMESTAMP_KEYS = {
    "created_at",
    "updated_at",
    "discovered_at",
    "posted_at",
    "expires_at",
    "normalized_at",
}


def _normalize_timestamps(data: dict) -> None:
    for rows in data.values():
        for row in rows:
            for key in _TIMESTAMP_KEYS:
                value = row.get(key)
                if isinstance(value, str):
                    row[key] = datetime.fromisoformat(value.replace("Z", "+00:00"))


async def seed() -> None:
    from db.seeds.fake_data import get_seed_data

    data = get_seed_data()
    _normalize_timestamps(data)
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # ------------------------------------------------------------------
        # candidate_profiles
        # ------------------------------------------------------------------
        for profile in data["candidate_profiles"]:
            await session.execute(
                sa.text(
                    """
                    INSERT INTO candidate_profiles
                        (id, version, full_name, contact_info, summary,
                         work_experience, education, certifications,
                         skills, languages, created_at, updated_at)
                    VALUES
                        (:id, :version, :full_name, cast(:contact_info as jsonb), :summary,
                         cast(:work_experience as jsonb), cast(:education as jsonb), cast(:certifications as jsonb),
                         cast(:skills as jsonb), cast(:languages as jsonb), cast(:created_at as timestamptz), cast(:updated_at as timestamptz))
                    ON CONFLICT (id, version) DO NOTHING
                    """
                ),
                {
                    "id": profile["id"],
                    "version": profile["version"],
                    "full_name": profile["full_name"],
                    "contact_info": json.dumps(profile["contact_info"]),
                    "summary": profile["summary"],
                    "work_experience": json.dumps(profile["work_experience"]),
                    "education": json.dumps(profile["education"]),
                    "certifications": json.dumps(profile["certifications"]),
                    "skills": json.dumps(profile["skills"]),
                    "languages": json.dumps(profile["languages"]),
                    "created_at": profile["created_at"],
                    "updated_at": profile["updated_at"],
                },
            )

        # ------------------------------------------------------------------
        # jobs
        # ------------------------------------------------------------------
        for job in data["jobs"]:
            await session.execute(
                sa.text(
                    """
                    INSERT INTO jobs
                        (id, external_id, source, source_url, title, company,
                         location, is_remote, employment_type, salary_range,
                         description, requirements, nice_to_have, technologies,
                         status, snapshot_hash, discovered_at, posted_at,
                         expires_at, normalized_at)
                    VALUES
                        (:id, :external_id, :source, :source_url, :title, :company,
                         :location, :is_remote, :employment_type, cast(:salary_range as jsonb),
                         :description, cast(:requirements as jsonb), cast(:nice_to_have as jsonb),
                         cast(:technologies as jsonb), :status, :snapshot_hash, cast(:discovered_at as timestamptz),
                         cast(:posted_at as timestamptz), cast(:expires_at as timestamptz), cast(:normalized_at as timestamptz))
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {
                    **{
                        k: v
                        for k, v in job.items()
                        if k
                        not in (
                            "salary_range",
                            "requirements",
                            "nice_to_have",
                            "technologies",
                        )
                    },
                    "salary_range": json.dumps(job["salary_range"]),
                    "requirements": json.dumps(job["requirements"]),
                    "nice_to_have": json.dumps(job["nice_to_have"]),
                    "technologies": json.dumps(job["technologies"]),
                },
            )

        # ------------------------------------------------------------------
        # applications
        # ------------------------------------------------------------------
        for app in data["applications"]:
            await session.execute(
                sa.text(
                    """
                    INSERT INTO applications
                        (id, job_id, candidate_profile_id, status,
                         packet_fingerprint, created_at, updated_at)
                    VALUES
                        (:id, :job_id, :candidate_profile_id, :status,
                         cast(:packet_fingerprint as jsonb), cast(:created_at as timestamptz), cast(:updated_at as timestamptz))
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {
                    **{k: v for k, v in app.items() if k != "packet_fingerprint"},
                    "packet_fingerprint": json.dumps(app["packet_fingerprint"])
                    if app["packet_fingerprint"] is not None
                    else None,
                },
            )

        # ------------------------------------------------------------------
        # application_events
        # ------------------------------------------------------------------
        for event in data["application_events"]:
            await session.execute(
                sa.text(
                    """
                    INSERT INTO application_events
                        (id, application_id, from_status, to_status,
                         triggered_by, actor_id, note, created_at)
                    VALUES
                        (:id, :application_id, :from_status, :to_status,
                         :triggered_by, :actor_id, :note, cast(:created_at as timestamptz))
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                event,
            )

        await session.commit()

    await engine.dispose()
    print("Seed data loaded successfully.")
    print(f"  candidate_profiles : {len(data['candidate_profiles'])}")
    print(f"  jobs               : {len(data['jobs'])}")
    print(f"  applications       : {len(data['applications'])}")
    print(f"  application_events : {len(data['application_events'])}")


if __name__ == "__main__":
    asyncio.run(seed())
