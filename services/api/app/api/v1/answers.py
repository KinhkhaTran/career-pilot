from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.materials.answers import validate_answer
from app.models.material import AnswerLibraryEntry
from app.models.profile import CandidateProfile
from app.schemas.material import AnswerCreateSchema, AnswerSchema

router = APIRouter()


@router.get("", response_model=list[AnswerSchema])
async def list_answers(
    candidate_profile_id: str = Query(...), db: AsyncSession = Depends(get_db)
) -> list[AnswerSchema]:
    rows = (
        await db.scalars(
            select(AnswerLibraryEntry)
            .where(AnswerLibraryEntry.candidate_profile_id == candidate_profile_id)
            .order_by(AnswerLibraryEntry.question_key, AnswerLibraryEntry.version)
        )
    ).all()
    return [AnswerSchema.model_validate(row) for row in rows]


@router.post("", response_model=AnswerSchema, status_code=201)
async def create_answer(
    body: AnswerCreateSchema, db: AsyncSession = Depends(get_db)
) -> AnswerSchema:
    profile_exists = await db.scalar(
        select(CandidateProfile.row_id).where(CandidateProfile.id == body.candidate_profile_id)
    )
    if profile_exists is None:
        raise HTTPException(status_code=404, detail="Candidate profile not found")
    try:
        answer = validate_answer(body.answer)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    for _ in range(3):
        latest = await db.scalar(
            select(func.max(AnswerLibraryEntry.version)).where(
                AnswerLibraryEntry.candidate_profile_id == body.candidate_profile_id,
                AnswerLibraryEntry.question_key == body.question_key,
            )
        )
        row = AnswerLibraryEntry(
            id=str(uuid.uuid4()),
            candidate_profile_id=body.candidate_profile_id,
            question_key=body.question_key,
            question=body.question.strip(),
            answer=answer,
            version=(latest or 0) + 1,
            reviewed=body.reviewed,
        )
        try:
            async with db.begin_nested():
                db.add(row)
                await db.flush()
            return AnswerSchema.model_validate(row)
        except IntegrityError:
            continue
    raise HTTPException(status_code=409, detail="Concurrent answer version conflict; retry the request")
