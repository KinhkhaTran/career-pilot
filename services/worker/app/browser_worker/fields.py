"""Field taxonomy, answer values, and sensitivity classification.

The runner only ever fills fields whose category is in ``FILLABLE_CATEGORIES``
and only from a human-approved answer set. Protected-class / EEO questions and
attestations are never auto-filled; encountering one pauses the run.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FieldCategory(str, Enum):
    """Application form field categories the Workday adapter can recognise."""

    # Lawful, pre-approved fields the runner may fill (requirement 5).
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS_LINE1 = "address_line1"
    ADDRESS_LINE2 = "address_line2"
    CITY = "city"
    STATE = "state"
    POSTAL_CODE = "postal_code"
    COUNTRY = "country"
    EDUCATION = "education"
    EMPLOYMENT_HISTORY = "employment_history"
    SKILLS = "skills"
    PORTFOLIO_URL = "portfolio_url"
    LINKEDIN_URL = "linkedin_url"
    WORK_AUTHORIZATION = "work_authorization"
    SPONSORSHIP = "sponsorship"
    RELOCATION = "relocation"
    START_DATE = "start_date"
    SCREENING_ANSWER = "screening_answer"
    RESUME = "resume"
    COVER_LETTER = "cover_letter"

    # Never auto-filled — always hands off to the human (requirement 8).
    EEO_RACE = "eeo_race"
    EEO_GENDER = "eeo_gender"
    EEO_VETERAN = "eeo_veteran"
    EEO_DISABILITY = "eeo_disability"
    DATE_OF_BIRTH = "date_of_birth"
    CRIMINAL_HISTORY = "criminal_history"
    ATTESTATION = "attestation"


# Categories the runner is permitted to fill from an approved answer set.
FILLABLE_CATEGORIES: frozenset[FieldCategory] = frozenset(
    {
        FieldCategory.FIRST_NAME,
        FieldCategory.LAST_NAME,
        FieldCategory.EMAIL,
        FieldCategory.PHONE,
        FieldCategory.ADDRESS_LINE1,
        FieldCategory.ADDRESS_LINE2,
        FieldCategory.CITY,
        FieldCategory.STATE,
        FieldCategory.POSTAL_CODE,
        FieldCategory.COUNTRY,
        FieldCategory.EDUCATION,
        FieldCategory.EMPLOYMENT_HISTORY,
        FieldCategory.SKILLS,
        FieldCategory.PORTFOLIO_URL,
        FieldCategory.LINKEDIN_URL,
        FieldCategory.WORK_AUTHORIZATION,
        FieldCategory.SPONSORSHIP,
        FieldCategory.RELOCATION,
        FieldCategory.START_DATE,
        FieldCategory.SCREENING_ANSWER,
        FieldCategory.RESUME,
        FieldCategory.COVER_LETTER,
    }
)

# Legally sensitive / protected-class questions and attestations. These are
# never filled from the answer set; the run pauses so the human answers them.
LEGALLY_SENSITIVE_CATEGORIES: frozenset[FieldCategory] = frozenset(
    {
        FieldCategory.EEO_RACE,
        FieldCategory.EEO_GENDER,
        FieldCategory.EEO_VETERAN,
        FieldCategory.EEO_DISABILITY,
        FieldCategory.DATE_OF_BIRTH,
        FieldCategory.CRIMINAL_HISTORY,
    }
)

# File-upload categories are filled via ``set_input_files`` rather than ``fill``.
UPLOAD_CATEGORIES: frozenset[FieldCategory] = frozenset(
    {FieldCategory.RESUME, FieldCategory.COVER_LETTER}
)

# Input mechanics: how a filled field is written to the page.
TEXT_KIND = "text"
SELECT_KIND = "select"
RADIO_KIND = "radio"
CHECKBOX_KIND = "checkbox"
FILE_KIND = "file"


@dataclass(frozen=True)
class FieldValue:
    """An approved answer with the confidence the human review assigned it."""

    value: str
    confidence: float
    source: str = "approved_answer_set"

    def is_sensitive_placeholder(self) -> bool:
        return self.value == ""


@dataclass(frozen=True)
class DetectedField:
    """A form field the adapter located on the current page/step."""

    category: FieldCategory
    selector: str
    kind: str
    label: str = ""
    required: bool = True

    @property
    def is_sensitive(self) -> bool:
        return (
            self.category in LEGALLY_SENSITIVE_CATEGORIES
            or self.category is FieldCategory.ATTESTATION
        )

    @property
    def is_upload(self) -> bool:
        return self.category in UPLOAD_CATEGORIES


def redact(category: FieldCategory, value: str) -> str:
    """Redact values for the audit trail so sensitive data is never persisted.

    Fillable, lawful fields are recorded verbatim (they were approved for the
    application); sensitive categories are never filled, but if a value ever
    reached this helper it would be masked.
    """
    if category in LEGALLY_SENSITIVE_CATEGORIES or category is FieldCategory.ATTESTATION:
        return "«redacted»"
    return value
