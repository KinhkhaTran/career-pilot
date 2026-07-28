"""Tests for the job normalization module."""

from __future__ import annotations

from app.adapters.base import RawJobPosting
from app.adapters.normalizer import (
    compute_snapshot_hash,
    detect_employment_type,
    detect_is_remote,
    detect_technologies,
    extract_list_items,
    normalize,
    strip_html,
)


def make_raw(
    *,
    external_id: str = "job-001",
    source: str = "greenhouse",
    source_url: str = "https://example.com/jobs/001",
    title: str = "Senior Engineer",
    company: str = "Acme",
    location: str | None = "Remote",
    is_remote: bool = False,
    description: str = "<p>Join us as an engineer.</p><ul><li>5+ years experience</li><li>Python skills</li></ul>",
    raw_data: dict | None = None,
) -> RawJobPosting:
    return RawJobPosting(
        external_id=external_id,
        source=source,
        source_url=source_url,
        title=title,
        company=company,
        location=location,
        is_remote=is_remote,
        description=description,
        raw_data=raw_data or {},
    )


class TestStripHtml:
    def test_strips_tags(self) -> None:
        assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_decodes_entities(self) -> None:
        assert ">" in strip_html("foo &gt; bar")

    def test_collapses_whitespace(self) -> None:
        result = strip_html("<p>a</p>   <p>b</p>")
        assert "  " not in result

    def test_empty_string(self) -> None:
        assert strip_html("") == ""

    def test_plain_text_unchanged(self) -> None:
        assert strip_html("plain text") == "plain text"


class TestExtractListItems:
    def test_extracts_items(self) -> None:
        html = "<ul><li>Python</li><li>FastAPI</li></ul>"
        items = extract_list_items(html)
        assert "Python" in items
        assert "FastAPI" in items

    def test_strips_nested_tags(self) -> None:
        html = "<li><strong>3+ years</strong> experience</li>"
        items = extract_list_items(html)
        assert any("years" in item for item in items)

    def test_empty_items_skipped(self) -> None:
        html = "<li></li><li>Valid</li>"
        items = extract_list_items(html)
        assert all(item for item in items)

    def test_no_list_returns_empty(self) -> None:
        assert extract_list_items("<p>no list here</p>") == []


class TestComputeSnapshotHash:
    def test_deterministic(self) -> None:
        h1 = compute_snapshot_hash("greenhouse", "123", "Engineer", "We are hiring")
        h2 = compute_snapshot_hash("greenhouse", "123", "Engineer", "We are hiring")
        assert h1 == h2

    def test_different_inputs_different_hash(self) -> None:
        h1 = compute_snapshot_hash("greenhouse", "123", "Engineer", "original")
        h2 = compute_snapshot_hash("greenhouse", "123", "Engineer", "updated")
        assert h1 != h2

    def test_source_affects_hash(self) -> None:
        h1 = compute_snapshot_hash("greenhouse", "123", "Eng", "desc")
        h2 = compute_snapshot_hash("lever", "123", "Eng", "desc")
        assert h1 != h2

    def test_returns_hex_string(self) -> None:
        h = compute_snapshot_hash("s", "e", "t", "d")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestDetectIsRemote:
    def test_remote_in_location(self) -> None:
        assert detect_is_remote("Engineer", "Remote", "") is True

    def test_remote_in_title(self) -> None:
        assert detect_is_remote("Remote Software Engineer", "Austin", "") is True

    def test_remote_in_description(self) -> None:
        assert detect_is_remote("Engineer", None, "This is a fully remote position.") is True

    def test_not_remote(self) -> None:
        assert detect_is_remote("Engineer", "Austin, TX", "On-site role.") is False

    def test_wfh_keyword(self) -> None:
        assert detect_is_remote("Engineer", None, "work from home allowed") is True

    def test_case_insensitive(self) -> None:
        assert detect_is_remote("REMOTE Engineer", None, "") is True


class TestDetectEmploymentType:
    def test_full_time(self) -> None:
        assert detect_employment_type("Full-time position") == "full_time"

    def test_part_time(self) -> None:
        assert detect_employment_type("Part-time role") == "part_time"

    def test_contract(self) -> None:
        assert detect_employment_type("Contract position") == "contract"

    def test_internship(self) -> None:
        assert detect_employment_type("Summer internship program") == "internship"

    def test_unknown_returns_none(self) -> None:
        assert detect_employment_type("Some role description") is None

    def test_case_insensitive(self) -> None:
        assert detect_employment_type("FULL-TIME") == "full_time"


class TestDetectTechnologies:
    def test_detects_known_tech(self) -> None:
        desc = "We use Python, FastAPI, PostgreSQL, and Redis."
        techs = detect_technologies(desc)
        assert "python" in techs
        assert "fastapi" in techs
        assert "postgresql" in techs
        assert "redis" in techs

    def test_case_insensitive(self) -> None:
        techs = detect_technologies("We use PYTHON and TypeScript")
        assert "python" in techs
        assert "typescript" in techs

    def test_no_false_positives(self) -> None:
        techs = detect_technologies("We do awesome work")
        assert techs == []


class TestNormalize:
    def test_normalize_returns_correct_source(self) -> None:
        raw = make_raw(source="greenhouse")
        result = normalize(raw)
        assert result.source == "greenhouse"

    def test_normalize_strips_html_description(self) -> None:
        raw = make_raw(description="<p>Hello</p>")
        result = normalize(raw)
        assert "<p>" not in result.description
        assert "Hello" in result.description

    def test_normalize_computes_snapshot_hash(self) -> None:
        raw = make_raw()
        result = normalize(raw)
        assert len(result.snapshot_hash) == 64

    def test_normalize_is_deterministic(self) -> None:
        raw = make_raw()
        h1 = normalize(raw).snapshot_hash
        h2 = normalize(raw).snapshot_hash
        assert h1 == h2

    def test_normalize_extracts_requirements(self) -> None:
        raw = make_raw(description="<ul><li>5+ years experience</li><li>Python</li></ul>")
        result = normalize(raw)
        assert len(result.requirements) >= 1

    def test_normalize_detects_remote_from_location(self) -> None:
        raw = make_raw(location="Remote", is_remote=False)
        result = normalize(raw)
        assert result.is_remote is True

    def test_normalize_preserves_is_remote_true(self) -> None:
        raw = make_raw(location="New York", is_remote=True)
        result = normalize(raw)
        assert result.is_remote is True

    def test_normalize_detects_technologies(self) -> None:
        raw = make_raw(description="<p>We use Python, React, and PostgreSQL daily.</p>")
        result = normalize(raw)
        assert "python" in result.technologies
        assert "react" in result.technologies

    def test_normalize_parses_posted_at_iso(self) -> None:
        raw = make_raw(raw_data={"posted_at": "2024-07-01T09:00:00Z"})
        result = normalize(raw)
        assert result.posted_at is not None

    def test_normalize_parses_posted_at_ms(self) -> None:
        raw = make_raw(raw_data={"posted_at": 1719820800000})
        result = normalize(raw)
        assert result.posted_at is not None

    def test_normalize_no_posted_at(self) -> None:
        raw = make_raw(raw_data={})
        result = normalize(raw)
        assert result.posted_at is None
