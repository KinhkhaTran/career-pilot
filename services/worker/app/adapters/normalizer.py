"""
Job normalization: converts RawJobPosting → NormalizedJobData.

This module is pure (no I/O) and fully unit-testable.
All functions are deterministic given the same input.
"""

from __future__ import annotations

import hashlib
import html
import re
from datetime import UTC, datetime

from .base import NormalizedJobData, RawJobPosting

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_LIST_ITEM_RE = re.compile(r"<li[^>]*>(.*?)</li>", re.IGNORECASE | re.DOTALL)


def strip_html(text: str) -> str:
    """Strip HTML tags and decode entities, collapsing whitespace."""
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def extract_list_items(html_text: str) -> list[str]:
    """Extract text content from <li> elements."""
    items: list[str] = []
    for match in _LIST_ITEM_RE.finditer(html_text):
        item = strip_html(match.group(1)).strip()
        if item:
            items.append(item)
    return items


def compute_snapshot_hash(source: str, external_id: str, title: str, description: str) -> str:
    """
    Deterministic SHA-256 hash of the canonical job snapshot fields.

    Used for content-addressable deduplication: if the hash is unchanged,
    the job posting has not changed since last discovery.
    """
    content = f"{source}|{external_id}|{title}|{description}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


_REMOTE_KEYWORDS = frozenset(
    ["remote", "work from home", "wfh", "anywhere", "distributed", "fully remote"]
)

_EMPLOYMENT_TYPE_MAP: list[tuple[str, str]] = [
    ("full-time", "full_time"),
    ("full time", "full_time"),
    ("fulltime", "full_time"),
    ("part-time", "part_time"),
    ("part time", "part_time"),
    ("contract", "contract"),
    ("freelance", "contract"),
    ("internship", "internship"),
    ("intern", "internship"),
    ("temporary", "temporary"),
    ("temp ", "temporary"),
]

_TECH_KEYWORDS = [
    "python",
    "typescript",
    "javascript",
    "go",
    "golang",
    "rust",
    "java",
    "kotlin",
    "scala",
    "ruby",
    "c++",
    "c#",
    ".net",
    "swift",
    "react",
    "vue",
    "angular",
    "node.js",
    "nodejs",
    "fastapi",
    "django",
    "flask",
    "spring",
    "rails",
    "postgresql",
    "postgres",
    "mysql",
    "sqlite",
    "redis",
    "mongodb",
    "elasticsearch",
    "kafka",
    "rabbitmq",
    "celery",
    "arq",
    "graphql",
    "rest",
    "grpc",
    "kubernetes",
    "k8s",
    "docker",
    "terraform",
    "ansible",
    "aws",
    "gcp",
    "azure",
    "spark",
    "airflow",
    "dbt",
    "snowflake",
    "bigquery",
    "dask",
    "pytorch",
    "tensorflow",
    "scikit-learn",
    "pandas",
    "numpy",
    "git",
    "github",
    "gitlab",
    "ci/cd",
    "jenkins",
]


def detect_is_remote(title: str, location: str | None, description: str) -> bool:
    """Heuristic remote detection from title, location, and description snippet."""
    haystack = f"{title} {location or ''} {description[:1000]}".lower()
    return any(kw in haystack for kw in _REMOTE_KEYWORDS)


def detect_employment_type(text: str) -> str | None:
    """Infer employment type from free-form commitment/type text."""
    lower = text.lower()
    for pattern, result in _EMPLOYMENT_TYPE_MAP:
        if pattern in lower:
            return result
    return None


def detect_technologies(description: str) -> list[str]:
    """Extract technology keywords present in a job description."""
    lower = description.lower()
    found: list[str] = []
    for tech in _TECH_KEYWORDS:
        if tech in lower and tech not in found:
            found.append(tech)
    return found


def normalize(raw: RawJobPosting) -> NormalizedJobData:
    """
    Convert a RawJobPosting to a NormalizedJobData.

    Deterministic: same input always produces the same output.
    """
    plain_description = strip_html(raw.description)

    is_remote = raw.is_remote or detect_is_remote(raw.title, raw.location, plain_description)

    employment_type = detect_employment_type(raw.description)

    requirements = extract_list_items(raw.description) if "<li" in raw.description.lower() else []

    technologies = detect_technologies(plain_description)

    snapshot_hash = compute_snapshot_hash(raw.source, raw.external_id, raw.title, plain_description)

    posted_at: datetime | None = None
    raw_posted = raw.raw_data.get("posted_at") or raw.raw_data.get("publishedAt")
    if isinstance(raw_posted, str):
        try:
            posted_at = datetime.fromisoformat(raw_posted.replace("Z", "+00:00"))
        except ValueError:
            pass
    elif isinstance(raw_posted, int | float):
        try:
            posted_at = datetime.fromtimestamp(raw_posted / 1000.0, UTC)
        except (OSError, OverflowError, ValueError):
            pass

    return NormalizedJobData(
        external_id=raw.external_id,
        source=raw.source,
        source_url=raw.source_url,
        title=raw.title,
        company=raw.company,
        location=raw.location,
        is_remote=is_remote,
        employment_type=employment_type,
        description=plain_description,
        requirements=requirements,
        nice_to_have=[],
        technologies=technologies,
        snapshot_hash=snapshot_hash,
        posted_at=posted_at,
        salary_range=None,
    )
