from __future__ import annotations

import time

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: float
    submission_mode: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    from app.config import settings

    return HealthResponse(
        status="ok",
        version="0.1.0",
        timestamp=time.time(),
        submission_mode=settings.initial_submission_mode,
    )
