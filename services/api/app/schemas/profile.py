from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ContactInfoSchema(BaseModel):
    email: str
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None
    github: str | None = None
    website: str | None = None


class WorkExperienceSchema(BaseModel):
    company: str
    title: str
    start_date: str  # ISO date string, e.g. "2022-01"
    end_date: str | None = None  # None means current
    is_current: bool = False
    location: str | None = None
    is_remote: bool = False
    description: str | None = None
    achievements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)


class EducationSchema(BaseModel):
    institution: str
    degree: str
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    gpa: float | None = None
    # Matches the shared TS contract (Education.honors: string[]) and the seed data.
    honors: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)


class CertificationSchema(BaseModel):
    name: str
    issuer: str
    issued_date: str | None = None
    expiry_date: str | None = None
    credential_id: str | None = None
    credential_url: str | None = None


class LanguageSchema(BaseModel):
    language: str
    proficiency: str  # e.g. "native", "fluent", "professional", "elementary"


class CandidateProfileSchema(BaseModel):
    """Full candidate profile including all version metadata."""

    id: str
    version: int
    full_name: str
    contact_info: ContactInfoSchema | None = None
    summary: str | None = None
    work_experience: list[WorkExperienceSchema] = Field(default_factory=list)
    education: list[EducationSchema] = Field(default_factory=list)
    certifications: list[CertificationSchema] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    # Matches the shared TS contract (CandidateProfile.languages: string[]) and the seed data.
    languages: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CandidateProfileSummarySchema(BaseModel):
    """Lightweight profile for list views."""

    id: str
    version: int
    full_name: str
    email: str | None = None
    location: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CandidateProfileCreateSchema(BaseModel):
    """Payload for creating a new profile (no id / version / timestamps)."""

    full_name: str
    contact_info: ContactInfoSchema | None = None
    summary: str | None = None
    work_experience: list[WorkExperienceSchema] = Field(default_factory=list)
    education: list[EducationSchema] = Field(default_factory=list)
    certifications: list[CertificationSchema] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    languages: list[LanguageSchema] = Field(default_factory=list)
