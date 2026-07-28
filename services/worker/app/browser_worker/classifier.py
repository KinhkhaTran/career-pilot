"""ATS provider classification and adapter routing.

Classification is purely observational: it reads the URL and rendered DOM the
human has already navigated to. It never probes private endpoints, defeats
access controls, or fingerprints to conceal automation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageSignals:
    """Observable, non-invasive signals used to classify the current page."""

    url: str
    html: str

    def _hay(self) -> str:
        return f"{self.url}\n{self.html}".lower()


# Provider -> (host substrings, DOM markers). Ordered most specific first.
_MATCHERS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "workday",
        ("myworkdayjobs.com", "wd1.myworkday", "workday.com"),
        ("data-automation-id=", "wd-popup", "css-workday"),
    ),
    (
        "greenhouse",
        ("boards.greenhouse.io", "greenhouse.io", "grnh.se"),
        ("#grnhse_app", "greenhouse-application", 'id="grnhse'),
    ),
    (
        "lever",
        ("jobs.lever.co", "lever.co"),
        ("lever-application", 'data-qa="', "postings-btn"),
    ),
    (
        "ashby",
        ("jobs.ashbyhq.com", "ashbyhq.com"),
        ("ashby-application-form", "_ashby"),
    ),
)


def classify_ats(signals: PageSignals) -> str:
    """Return the ATS provider name, or ``"unknown"`` if none matches."""
    hay = signals._hay()
    for name, hosts, markers in _MATCHERS:
        if any(host in hay for host in hosts):
            return name
        if any(marker.lower() in hay for marker in markers):
            return name
    return "unknown"
