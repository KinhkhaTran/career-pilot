from __future__ import annotations

from app.browser_worker import PauseReason, WorkdayAdapter, WorkdayStep
from app.browser_worker.fields import FieldCategory
from tests.fixtures.mock_workday import MockWorkdayApplication


async def _loaded() -> MockWorkdayApplication:
    sim = MockWorkdayApplication()
    await sim.goto("https://acme.wd1.myworkdayjobs.com/apply/x")
    return sim


async def test_detects_form_and_current_step() -> None:
    sim = await _loaded()
    adapter = WorkdayAdapter()
    assert await adapter.at_application_form(sim) is True
    assert await adapter.current_step(sim) is WorkdayStep.MY_INFORMATION


async def test_lists_fillable_fields_for_information_step() -> None:
    sim = await _loaded()
    adapter = WorkdayAdapter()
    fields = await adapter.fields_for_step(sim, WorkdayStep.MY_INFORMATION)
    categories = {f.category for f in fields}
    assert FieldCategory.FIRST_NAME in categories
    assert FieldCategory.EMAIL in categories
    assert FieldCategory.COUNTRY in categories


async def test_voluntary_disclosures_fields_are_sensitive() -> None:
    sim = await _loaded()
    sim.step = 3  # voluntary disclosures
    adapter = WorkdayAdapter()
    fields = await adapter.fields_for_step(sim, WorkdayStep.VOLUNTARY_DISCLOSURES)
    assert fields, "expected EEO + attestation fields on the disclosures step"
    assert all(f.is_sensitive for f in fields)


async def test_detects_interrupts_without_acting() -> None:
    sim = await _loaded()
    sim.interrupt_at = {"my_information": "captcha"}
    adapter = WorkdayAdapter()
    signals = await adapter.detect_interrupts(sim)
    assert [s.reason for s in signals] == [PauseReason.CAPTCHA]


async def test_review_and_confirmation_detection_and_evidence() -> None:
    sim = await _loaded()
    adapter = WorkdayAdapter()
    sim.step = 4  # review
    assert await adapter.is_review_page(sim) is True
    assert "Review your application" in await adapter.review_summary(sim)

    await sim.click(adapter.submit_selector())
    assert await adapter.is_confirmation_page(sim) is True
    evidence = await adapter.confirmation_evidence(sim)
    assert evidence["confirmation_number"] == "WD-CONF-2026-0001"
    assert "successfully submitted" in evidence["confirmation_message"]
