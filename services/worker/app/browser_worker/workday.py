"""Clean-room Workday application adapter.

Reimplements Workday's *observable* form conventions (``data-automation-id``
attributes, a stepped wizard, a final Review page, a post-submit confirmation).
No code is copied from any reference project. The adapter only reads and fills;
it exposes a submit **selector** but never clicks it — the runner does that, and
only under an approval token.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .fields import (
    CHECKBOX_KIND,
    FILE_KIND,
    RADIO_KIND,
    SELECT_KIND,
    TEXT_KIND,
    DetectedField,
    FieldCategory,
)
from .page import BrowserPage
from .pause import PauseReason, PauseSignal


class WorkdayStep(str, Enum):
    MY_INFORMATION = "my_information"
    MY_EXPERIENCE = "my_experience"
    APPLICATION_QUESTIONS = "application_questions"
    VOLUNTARY_DISCLOSURES = "voluntary_disclosures"
    REVIEW = "review"
    CONFIRMATION = "confirmation"
    UNKNOWN = "unknown"


def _aid(value: str) -> str:
    """Build a Workday ``data-automation-id`` attribute selector."""
    return f"[data-automation-id='{value}']"


# Ordered step detection: the container automation-id that marks each step.
_STEP_MARKERS: tuple[tuple[WorkdayStep, str], ...] = (
    (WorkdayStep.CONFIRMATION, _aid("confirmationPage")),
    (WorkdayStep.REVIEW, _aid("reviewPage")),
    (WorkdayStep.VOLUNTARY_DISCLOSURES, _aid("selfIdentificationPage")),
    (WorkdayStep.APPLICATION_QUESTIONS, _aid("questionnairePage")),
    (WorkdayStep.MY_EXPERIENCE, _aid("myExperiencePage")),
    (WorkdayStep.MY_INFORMATION, _aid("myInformationPage")),
)

# Field layout per step. The adapter checks visibility before treating a field
# as present, so optional fields that a given posting omits are simply skipped.
_STEP_FIELDS: dict[WorkdayStep, tuple[DetectedField, ...]] = {
    WorkdayStep.MY_INFORMATION: (
        DetectedField(FieldCategory.FIRST_NAME, _aid("legalName--firstName"), TEXT_KIND, "First name"),
        DetectedField(FieldCategory.LAST_NAME, _aid("legalName--lastName"), TEXT_KIND, "Last name"),
        DetectedField(FieldCategory.EMAIL, _aid("email"), TEXT_KIND, "Email"),
        DetectedField(FieldCategory.PHONE, _aid("phone-number"), TEXT_KIND, "Phone"),
        DetectedField(FieldCategory.ADDRESS_LINE1, _aid("addressLine1"), TEXT_KIND, "Address line 1"),
        DetectedField(FieldCategory.ADDRESS_LINE2, _aid("addressLine2"), TEXT_KIND, "Address line 2", required=False),
        DetectedField(FieldCategory.CITY, _aid("city"), TEXT_KIND, "City"),
        DetectedField(FieldCategory.STATE, _aid("countryRegion"), SELECT_KIND, "State/Region"),
        DetectedField(FieldCategory.POSTAL_CODE, _aid("postalCode"), TEXT_KIND, "Postal code"),
        DetectedField(FieldCategory.COUNTRY, _aid("country"), SELECT_KIND, "Country"),
    ),
    WorkdayStep.MY_EXPERIENCE: (
        DetectedField(FieldCategory.EMPLOYMENT_HISTORY, _aid("workExperience-1"), TEXT_KIND, "Work experience"),
        DetectedField(FieldCategory.EDUCATION, _aid("education-1"), TEXT_KIND, "Education"),
        DetectedField(FieldCategory.SKILLS, _aid("skills"), TEXT_KIND, "Skills"),
        DetectedField(FieldCategory.LINKEDIN_URL, _aid("linkedinQuestion"), TEXT_KIND, "LinkedIn"),
        DetectedField(FieldCategory.PORTFOLIO_URL, _aid("websiteQuestion"), TEXT_KIND, "Portfolio/Website", required=False),
        DetectedField(FieldCategory.RESUME, _aid("resumeUpload"), FILE_KIND, "Résumé"),
        DetectedField(FieldCategory.COVER_LETTER, _aid("coverLetterUpload"), FILE_KIND, "Cover letter", required=False),
    ),
    WorkdayStep.APPLICATION_QUESTIONS: (
        DetectedField(FieldCategory.WORK_AUTHORIZATION, _aid("workAuthorization"), SELECT_KIND, "Work authorization"),
        DetectedField(FieldCategory.SPONSORSHIP, _aid("sponsorship"), RADIO_KIND, "Sponsorship"),
        DetectedField(FieldCategory.RELOCATION, _aid("relocation"), RADIO_KIND, "Relocation"),
        DetectedField(FieldCategory.START_DATE, _aid("startDate"), TEXT_KIND, "Start date"),
        DetectedField(FieldCategory.SCREENING_ANSWER, _aid("screeningQuestion-1"), TEXT_KIND, "Screening question"),
    ),
    WorkdayStep.VOLUNTARY_DISCLOSURES: (
        DetectedField(FieldCategory.EEO_GENDER, _aid("gender"), SELECT_KIND, "Gender", required=False),
        DetectedField(FieldCategory.EEO_RACE, _aid("ethnicity"), SELECT_KIND, "Race/Ethnicity", required=False),
        DetectedField(FieldCategory.EEO_VETERAN, _aid("veteranStatus"), SELECT_KIND, "Veteran status", required=False),
        DetectedField(FieldCategory.EEO_DISABILITY, _aid("disabilityStatus"), SELECT_KIND, "Disability status", required=False),
        DetectedField(FieldCategory.ATTESTATION, _aid("attestationCheckbox"), CHECKBOX_KIND, "Attestation"),
    ),
}

# Environmental interrupts the runner must never attempt to satisfy itself.
_INTERRUPT_MARKERS: tuple[tuple[PauseReason, tuple[str, ...]], ...] = (
    (PauseReason.CAPTCHA, (_aid("captcha"), "recaptcha", "hcaptcha", "cf-turnstile")),
    (PauseReason.MFA, (_aid("mfaChallenge"), "one-time passcode", "authenticator app")),
    (PauseReason.IDENTITY_VERIFICATION, (_aid("identityVerification"), "verify your identity")),
    (PauseReason.LOGIN_REQUIRED, (_aid("signInFormFields"), _aid("password"))),
)


@dataclass(frozen=True)
class WorkdayAdapter:
    name: str = "workday"

    async def at_application_form(self, page: BrowserPage) -> bool:
        """True once the human has navigated to a recognisable Workday form."""
        for _step, marker in _STEP_MARKERS:
            if await page.is_visible(marker):
                return True
        return False

    async def current_step(self, page: BrowserPage) -> WorkdayStep:
        for step, marker in _STEP_MARKERS:
            if await page.is_visible(marker):
                return step
        return WorkdayStep.UNKNOWN

    async def fields_for_step(
        self, page: BrowserPage, step: WorkdayStep
    ) -> list[DetectedField]:
        present: list[DetectedField] = []
        for spec in _STEP_FIELDS.get(step, ()):  # noqa: RUF010
            if await page.is_visible(spec.selector):
                present.append(spec)
        return present

    async def detect_interrupts(self, page: BrowserPage) -> list[PauseSignal]:
        """Detect CAPTCHA / MFA / identity / login walls without acting on them."""
        html = (await page.content()).lower()
        signals: list[PauseSignal] = []
        for reason, markers in _INTERRUPT_MARKERS:
            for marker in markers:
                selector_hit = marker.startswith("[") and await page.is_visible(marker)
                text_hit = not marker.startswith("[") and marker in html
                if selector_hit or text_hit:
                    signals.append(
                        PauseSignal(
                            reason=reason,
                            message=(
                                f"{reason.value} detected; a human must complete this "
                                "step in the visible browser."
                            ),
                            detail={"marker": marker},
                        )
                    )
                    break
        return signals

    async def read_validation_errors(self, page: BrowserPage) -> list[str]:
        """Read Workday inline validation error text, if any is shown."""
        container = _aid("errorMessage")
        if not await page.is_visible(container):
            return []
        text = await page.text_content(container)
        if not text:
            return []
        return [line.strip() for line in text.splitlines() if line.strip()]

    async def advance(self, page: BrowserPage) -> None:
        """Click the step's Next / Continue / Save-and-Continue control."""
        await page.click(_aid("bottom-navigation-next-button"))

    async def is_review_page(self, page: BrowserPage) -> bool:
        return await self.current_step(page) is WorkdayStep.REVIEW

    async def is_confirmation_page(self, page: BrowserPage) -> bool:
        return await self.current_step(page) is WorkdayStep.CONFIRMATION

    async def review_summary(self, page: BrowserPage) -> str:
        """Return the visible Review-page summary used for the final-page fingerprint."""
        text = await page.text_content(_aid("reviewSummary"))
        return text or ""

    def submit_selector(self) -> str:
        """The selector for the employer's existing Submit control on Review."""
        return _aid("submitApplication")

    async def confirmation_evidence(self, page: BrowserPage) -> dict[str, str]:
        """Extract proof-of-submission from the confirmation page."""
        number = await page.text_content(_aid("confirmationNumber"))
        message = await page.text_content(_aid("confirmationMessage"))
        return {
            "confirmation_number": (number or "").strip(),
            "confirmation_message": (message or "").strip(),
        }
