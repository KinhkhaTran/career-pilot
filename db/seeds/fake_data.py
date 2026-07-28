"""
Fake seed data generator. Uses only standard-library randomness + hardcoded plausible data.
All data is fictitious. Never use real emails, passwords, or credentials.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

FAKE_CANDIDATE = {
    "id": str(uuid.UUID("00000000-0000-0000-0000-000000000001")),
    "version": 1,
    "full_name": "Jordan Rivers",
    "contact_info": {
        "email": "jordan.rivers@example.invalid",
        "phone": "+1-555-0100",
        "linkedin_url": "https://linkedin.com/in/jordan-rivers-example",
        "github_url": "https://github.com/jordanrivers-example",
        "portfolio_url": None,
        "location": "Austin, TX",
    },
    "summary": (
        "Experienced software engineer with 7 years building distributed systems, APIs, "
        "and data pipelines. Strong background in Python, TypeScript, and cloud-native architectures."
    ),
    "work_experience": [
        {
            "id": str(uuid.UUID("00000000-0000-0000-0001-000000000001")),
            "company": "Acme Corp (Fictitious)",
            "title": "Senior Software Engineer",
            "start_date": "2021-03",
            "end_date": None,
            "is_current": True,
            "description": (
                "Led backend platform team. Designed event-driven microservices "
                "processing 2M events/day."
            ),
            "achievements": [
                "Reduced p99 API latency by 40% via async refactor",
                "Onboarded 3 engineers and established code review standards",
            ],
            "technologies": ["Python", "FastAPI", "PostgreSQL", "Redis", "Kafka", "AWS"],
        },
        {
            "id": str(uuid.UUID("00000000-0000-0000-0001-000000000002")),
            "company": "Beta Systems (Fictitious)",
            "title": "Software Engineer",
            "start_date": "2018-06",
            "end_date": "2021-02",
            "is_current": False,
            "description": (
                "Built internal tooling and customer-facing APIs. Owned the notification service."
            ),
            "achievements": [
                "Launched notifications service used by 50k users",
                "Migrated monolith to service-oriented architecture",
            ],
            "technologies": ["Python", "Django", "PostgreSQL", "React", "TypeScript"],
        },
    ],
    "education": [
        {
            "id": str(uuid.UUID("00000000-0000-0000-0002-000000000001")),
            "institution": "State University (Fictitious)",
            "degree": "Bachelor of Science",
            "field": "Computer Science",
            "start_date": "2014-09",
            "end_date": "2018-05",
            "gpa": 3.7,
            "honors": ["Dean's List 2016-2018"],
        }
    ],
    "certifications": [
        {
            "id": str(uuid.UUID("00000000-0000-0000-0003-000000000001")),
            "name": "AWS Certified Solutions Architect - Associate",
            "issuer": "Amazon Web Services",
            "issued_date": "2022-04",
            "expiry_date": "2025-04",
            "credential_id": "FAKE-AWS-SA-001",
        }
    ],
    "skills": [
        "Python",
        "TypeScript",
        "FastAPI",
        "PostgreSQL",
        "Redis",
        "AWS",
        "Docker",
        "Kubernetes",
        "Git",
        "React",
    ],
    "languages": ["English (native)", "Spanish (conversational)"],
    "created_at": "2024-01-15T10:00:00Z",
    "updated_at": "2024-06-01T14:30:00Z",
}

FAKE_JOBS = [
    {
        "id": str(uuid.UUID(f"00000000-0000-0000-0004-{str(i).zfill(12)}")),
        "external_id": f"GH-JOB-{1000 + i}",
        "source": "greenhouse",
        "source_url": f"https://boards.greenhouse.io/example{i}/jobs/{1000 + i}",
        "title": title,
        "company": company,
        "location": location,
        "is_remote": is_remote,
        "employment_type": "full_time",
        "salary_range": {
            "min": min_sal,
            "max": max_sal,
            "currency": "USD",
            "period": "annual",
        },
        "description": f"Join {company} as a {title}. We are building innovative products.",
        "requirements": [
            "5+ years experience",
            "Python or equivalent",
            "System design skills",
        ],
        "nice_to_have": ["Kubernetes", "AWS", "PostgreSQL"],
        "technologies": techs,
        "status": "discovered",
        "snapshot_hash": f"sha256-fakehash{i:04d}",
        "discovered_at": "2024-07-01T09:00:00Z",
        "posted_at": "2024-06-28T00:00:00Z",
        "expires_at": None,
        "normalized_at": "2024-07-01T09:05:00Z",
    }
    for i, (title, company, location, is_remote, min_sal, max_sal, techs) in enumerate(
        [
            (
                "Senior Backend Engineer",
                "Veritas Systems (Fictitious)",
                "San Francisco, CA",
                True,
                160000,
                200000,
                ["Python", "FastAPI", "PostgreSQL"],
            ),
            (
                "Staff Software Engineer",
                "Nexus Labs (Fictitious)",
                "New York, NY",
                True,
                190000,
                240000,
                ["Go", "Kubernetes", "AWS"],
            ),
            (
                "Senior Full-Stack Engineer",
                "Orbit Tech (Fictitious)",
                "Austin, TX",
                False,
                140000,
                180000,
                ["TypeScript", "React", "Node.js"],
            ),
            (
                "Platform Engineer",
                "Apex Solutions (Fictitious)",
                "Remote",
                True,
                150000,
                190000,
                ["Python", "Terraform", "AWS"],
            ),
            (
                "Senior Python Engineer",
                "Cascade AI (Fictitious)",
                "Seattle, WA",
                True,
                165000,
                210000,
                ["Python", "ML", "FastAPI"],
            ),
            (
                "Backend Engineer",
                "Prism Cloud (Fictitious)",
                "Denver, CO",
                True,
                130000,
                170000,
                ["Rust", "PostgreSQL", "Redis"],
            ),
            (
                "Senior Software Engineer",
                "Strata Data (Fictitious)",
                "Boston, MA",
                False,
                155000,
                195000,
                ["Python", "Spark", "Kafka"],
            ),
            (
                "Software Engineer II",
                "Nimbus Corp (Fictitious)",
                "Chicago, IL",
                True,
                120000,
                155000,
                ["TypeScript", "GraphQL", "PostgreSQL"],
            ),
            (
                "Engineering Lead",
                "Vertex AI (Fictitious)",
                "Los Angeles, CA",
                True,
                200000,
                260000,
                ["Python", "ML", "Kubernetes"],
            ),
            (
                "Senior API Engineer",
                "Meridian Systems (Fictitious)",
                "Remote",
                True,
                145000,
                185000,
                ["Python", "FastAPI", "Docker"],
            ),
        ],
        1,
    )
]

FAKE_APPLICATIONS = [
    {
        "id": str(uuid.UUID("00000000-0000-0000-0005-000000000001")),
        "job_id": str(uuid.UUID("00000000-0000-0000-0004-000000000001")),
        "candidate_profile_id": str(uuid.UUID("00000000-0000-0000-0000-000000000001")),
        "status": "matched",
        "packet_fingerprint": None,
        "created_at": "2024-07-10T08:00:00Z",
        "updated_at": "2024-07-10T08:05:00Z",
    },
    {
        "id": str(uuid.UUID("00000000-0000-0000-0005-000000000002")),
        "job_id": str(uuid.UUID("00000000-0000-0000-0004-000000000002")),
        "candidate_profile_id": str(uuid.UUID("00000000-0000-0000-0000-000000000001")),
        "status": "packet_ready",
        "packet_fingerprint": {
            "profile_version": 1,
            "resume_version": 1,
            "answer_versions": {},
            "job_snapshot_hash": "sha256-fakehash0002",
            "packet_hash": "sha256-packetfake0002",
            "generated_at": "2024-07-11T14:00:00Z",
        },
        "created_at": "2024-07-11T10:00:00Z",
        "updated_at": "2024-07-11T14:00:00Z",
    },
    {
        "id": str(uuid.UUID("00000000-0000-0000-0005-000000000003")),
        "job_id": str(uuid.UUID("00000000-0000-0000-0004-000000000003")),
        "candidate_profile_id": str(uuid.UUID("00000000-0000-0000-0000-000000000001")),
        "status": "stopped_before_submit",
        "packet_fingerprint": {
            "profile_version": 1,
            "resume_version": 1,
            "answer_versions": {},
            "job_snapshot_hash": "sha256-fakehash0003",
            "packet_hash": "sha256-packetfake0003",
            "generated_at": "2024-07-12T10:00:00Z",
        },
        "created_at": "2024-07-12T09:00:00Z",
        "updated_at": "2024-07-12T11:00:00Z",
    },
]

FAKE_APPLICATION_EVENTS = [
    {
        "id": str(uuid.UUID("00000000-0000-0000-0006-000000000001")),
        "application_id": str(uuid.UUID("00000000-0000-0000-0005-000000000001")),
        "from_status": None,
        "to_status": "draft",
        "triggered_by": "system",
        "actor_id": None,
        "note": "Application created",
        "created_at": "2024-07-10T08:00:00Z",
    },
    {
        "id": str(uuid.UUID("00000000-0000-0000-0006-000000000002")),
        "application_id": str(uuid.UUID("00000000-0000-0000-0005-000000000001")),
        "from_status": "draft",
        "to_status": "matched",
        "triggered_by": "system",
        "actor_id": None,
        "note": "Matched by eligibility filter",
        "created_at": "2024-07-10T08:05:00Z",
    },
    {
        "id": str(uuid.UUID("00000000-0000-0000-0006-000000000003")),
        "application_id": str(uuid.UUID("00000000-0000-0000-0005-000000000003")),
        "from_status": None,
        "to_status": "draft",
        "triggered_by": "system",
        "actor_id": None,
        "note": "Application created",
        "created_at": "2024-07-12T09:00:00Z",
    },
    {
        "id": str(uuid.UUID("00000000-0000-0000-0006-000000000004")),
        "application_id": str(uuid.UUID("00000000-0000-0000-0005-000000000003")),
        "from_status": "approved",
        "to_status": "stopped_before_submit",
        "triggered_by": "system",
        "actor_id": None,
        "note": (
            "Stopped before submission per initial release policy "
            "(INITIAL_SUBMISSION_MODE=stop_before_submit)"
        ),
        "created_at": "2024-07-12T11:00:00Z",
    },
]


def get_seed_data() -> dict:
    return {
        "candidate_profiles": [FAKE_CANDIDATE],
        "jobs": FAKE_JOBS,
        "applications": FAKE_APPLICATIONS,
        "application_events": FAKE_APPLICATION_EVENTS,
    }


if __name__ == "__main__":
    data = get_seed_data()
    print(json.dumps(data, indent=2))
