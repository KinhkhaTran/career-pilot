from __future__ import annotations

from pydantic import BaseModel, Field


class MaterialSchema(BaseModel):
    id: str
    application_id: str
    kind: str
    version: int
    content: str
    diff: str | None = None
    source_claims: list[str] = Field(default_factory=list)
    reviewed: bool = False
    model_config = {"from_attributes": True}


class GenerateMaterialsRequest(BaseModel):
    answer_keys: list[str] = Field(default_factory=list)

class AnswerCreateSchema(BaseModel):
    candidate_profile_id: str
    question_key: str
    question: str
    answer: str
    reviewed: bool = False


class AnswerSchema(AnswerCreateSchema):
    id: str
    version: int
    model_config = {"from_attributes": True}


class PacketResponseSchema(BaseModel):
    resume: MaterialSchema
    cover_letter: MaterialSchema
    answers: list[AnswerSchema] = Field(default_factory=list)
    fingerprint: dict[str, object]


class ReviewRequestSchema(BaseModel):
    decision: str
    note: str | None = None
