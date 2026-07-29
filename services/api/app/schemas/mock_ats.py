from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MockAtsFormFieldSchema(BaseModel):
    name: str
    label: str
    selector: str
    kind: str
    required: bool


class MockAtsFormSchema(BaseModel):
    board_token: str
    label: str
    is_mock: bool = True
    fields: list[MockAtsFormFieldSchema] = Field(default_factory=list)


class MockAtsSubmitRequest(BaseModel):
    """A submission delivered to the in-process sandbox board."""

    application_id: str
    external_job_id: str
    payload: dict[str, str] = Field(default_factory=dict)
    browser_run_id: str | None = None
    packet_hash: str | None = None


class MockAtsReceiptSchema(BaseModel):
    id: str
    board_token: str
    external_job_id: str
    application_id: str
    browser_run_id: str | None = None
    confirmation_code: str
    packet_hash: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    received_at: datetime | None = None

    #: Constant reminder rendered wherever a receipt is displayed.
    is_mock: bool = True

    model_config = {"from_attributes": True}
