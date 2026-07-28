from __future__ import annotations

import pytest

from app.browser_worker import PageSignals, classify_ats


@pytest.mark.parametrize(
    ("url", "html", "expected"),
    [
        ("https://acme.wd1.myworkdayjobs.com/apply/x", "<div data-automation-id='email'>", "workday"),
        ("https://x.example/apply", "<div data-automation-id='foo'></div>", "workday"),
        ("https://boards.greenhouse.io/acme/jobs/1", "<div id='grnhse_app'>", "greenhouse"),
        ("https://jobs.lever.co/acme/1", "<div class='lever-application'>", "lever"),
        ("https://jobs.ashbyhq.com/acme/1", "<div class='ashby-application-form'>", "ashby"),
        ("https://careers.example.com/apply", "<form>generic</form>", "unknown"),
    ],
)
def test_classify_ats(url: str, html: str, expected: str) -> None:
    assert classify_ats(PageSignals(url=url, html=html)) == expected
