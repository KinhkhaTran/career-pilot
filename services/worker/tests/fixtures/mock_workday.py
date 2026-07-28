"""In-memory mock of a Workday-style application, driven via the BrowserPage API.

This is the local fixture the Workday adapter and supervised runner are proven
against before any real employer site is ever touched. It models Workday's
observable behaviour: a stepped wizard keyed by ``data-automation-id``, inline
validation, a final Review page, and a post-submit confirmation — all in memory,
with no network and no browser binary.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_SELECTOR_RE = re.compile(r"\[data-automation-id='(?P<id>[^']+)'\](?:\[value='(?P<value>[^']+)'\])?")

NEXT_BUTTON = "bottom-navigation-next-button"
SUBMIT_BUTTON = "submitApplication"

# Ordered wizard: (step id, container automation-id, visible field automation-ids).
_STEPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "my_information",
        "myInformationPage",
        (
            "legalName--firstName",
            "legalName--lastName",
            "email",
            "phone-number",
            "addressLine1",
            "addressLine2",
            "city",
            "countryRegion",
            "postalCode",
            "country",
        ),
    ),
    (
        "my_experience",
        "myExperiencePage",
        (
            "workExperience-1",
            "education-1",
            "skills",
            "linkedinQuestion",
            "websiteQuestion",
            "resumeUpload",
            "coverLetterUpload",
        ),
    ),
    (
        "application_questions",
        "questionnairePage",
        (
            "workAuthorization",
            "sponsorship",
            "relocation",
            "startDate",
            "screeningQuestion-1",
        ),
    ),
    (
        "voluntary_disclosures",
        "selfIdentificationPage",
        ("gender", "ethnicity", "veteranStatus", "disabilityStatus", "attestationCheckbox"),
    ),
    ("review", "reviewPage", ("reviewSummary", SUBMIT_BUTTON)),
    ("confirmation", "confirmationPage", ("confirmationNumber", "confirmationMessage")),
)

_STEP_INDEX = {step_id: i for i, (step_id, _c, _f) in enumerate(_STEPS)}

# Interrupt markers this mock can render on a given step (never solved, only shown).
_INTERRUPT_IDS = {
    "captcha": "captcha",
    "mfa": "mfaChallenge",
    "identity": "identityVerification",
    "login": "signInFormFields",
}
_INTERRUPT_TEXT = {
    "captcha": "recaptcha challenge",
    "mfa": "one-time passcode from your authenticator app",
    "identity": "verify your identity",
    "login": "please sign in to continue",
}


def parse_selector(selector: str) -> tuple[str | None, str | None]:
    match = _SELECTOR_RE.search(selector)
    if not match:
        return None, None
    return match.group("id"), match.group("value")


@dataclass
class MockWorkdayApplication:
    """A stateful, Playwright-compatible mock of one Workday application."""

    loaded: bool = False
    step: int = 0
    values: dict[str, str] = field(default_factory=dict)
    uploads: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    screenshots: list[str] = field(default_factory=list)
    submitted: bool = False
    confirmation_number: str = "WD-CONF-2026-0001"
    # Config: fields whose submit is rejected (to exercise validation handling).
    reject_fields: frozenset[str] = frozenset()
    # Config: {step_id: interrupt_kind} to render a challenge wall on a step.
    interrupt_at: dict[str, str] = field(default_factory=dict)

    # -- helpers -------------------------------------------------------------

    @property
    def _step_id(self) -> str:
        return _STEPS[self.step][0]

    def _visible_ids(self) -> set[str]:
        if not self.loaded:
            return set()
        _sid, container, fields = _STEPS[self.step]
        ids = {container, *fields}
        if self._step_id not in {"confirmation"}:
            ids.add(NEXT_BUTTON)
        if self.error is not None:
            ids.add("errorMessage")
        interrupt = self.interrupt_at.get(self._step_id)
        if interrupt:
            ids.add(_INTERRUPT_IDS[interrupt])
        return ids

    def _review_text(self) -> str:
        lines = [f"{key}={self.values[key]}" for key in sorted(self.values)]
        lines += [f"upload:{key}={Path(val).name}" for key, val in sorted(self.uploads.items())]
        return "Review your application\n" + "\n".join(lines)

    # -- human-driven transitions (used by tests to simulate manual steps) ---

    def human_complete_voluntary_disclosures(self) -> None:
        """Simulate a human answering EEO questions + attestation and continuing."""
        assert self._step_id == "voluntary_disclosures"
        self.values.update({"gender": "declined", "attestationCheckbox": "true"})
        self.step = _STEP_INDEX["review"]
        self.error = None

    def clear_interrupt(self) -> None:
        self.interrupt_at.pop(self._step_id, None)

    # -- BrowserPage protocol -----------------------------------------------

    async def goto(self, url: str) -> None:
        self.loaded = True
        self.step = 0
        self.error = None

    async def current_url(self) -> str:
        return f"https://acme.wd1.myworkdayjobs.com/apply/{self._step_id}"

    async def content(self) -> str:
        ids = self._visible_ids()
        markup = "".join(f'<div data-automation-id="{i}"></div>' for i in ids)
        interrupt = self.interrupt_at.get(self._step_id)
        extra = _INTERRUPT_TEXT.get(interrupt or "", "")
        return f"<html data-automation-id='workdayApp'>{markup}{extra}</html>"

    async def is_visible(self, selector: str) -> bool:
        aid, value = parse_selector(selector)
        if aid is None:
            return False
        if value is not None:  # radio option probe, e.g. sponsorship[value='no']
            return aid in self._visible_ids()
        return aid in self._visible_ids()

    async def text_content(self, selector: str) -> str | None:
        aid, _ = parse_selector(selector)
        if aid == "reviewSummary" and self._step_id == "review":
            return self._review_text()
        if aid == "confirmationNumber" and self.submitted:
            return self.confirmation_number
        if aid == "confirmationMessage" and self.submitted:
            return "You have successfully submitted your application."
        if aid == "errorMessage" and self.error is not None:
            return self.error
        return None

    async def fill(self, selector: str, value: str) -> None:
        aid, _ = parse_selector(selector)
        if aid and aid in self._visible_ids():
            self.values[aid] = value
            self.error = None

    async def select_option(self, selector: str, value: str) -> None:
        await self.fill(selector, value)

    async def check(self, selector: str) -> None:
        aid, value = parse_selector(selector)
        if aid and aid in self._visible_ids():
            self.values[aid] = value or "true"
            self.error = None

    async def set_input_files(self, selector: str, path: str) -> None:
        aid, _ = parse_selector(selector)
        if aid and aid in self._visible_ids():
            self.uploads[aid] = path
            self.error = None

    async def click(self, selector: str) -> None:
        aid, _ = parse_selector(selector)
        if aid == SUBMIT_BUTTON and self._step_id == "review":
            self.submitted = True
            self.step = _STEP_INDEX["confirmation"]
            return
        if aid == NEXT_BUTTON:
            self._advance()

    def _advance(self) -> None:
        _sid, _c, fields = _STEPS[self.step]
        if self.reject_fields & set(fields):
            self.error = "Please correct the highlighted fields."
            return
        if self.step < len(_STEPS) - 1:
            self.step += 1
            self.error = None

    async def screenshot(self, *, path: str) -> bytes:
        self.screenshots.append(path)
        Path(path).write_bytes(b"mock-workday-screenshot")
        return b"mock-workday-screenshot"
