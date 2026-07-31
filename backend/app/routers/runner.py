from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_membership, require_editor
from app.models import User
from app.schemas import RunnerIn, RunnerOut
from app.services.runner import run_collection

router = APIRouter(prefix="/runner", tags=["runner"])


@router.post("/run", response_model=RunnerOut)
async def run(
    payload: RunnerIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RunnerOut:
    membership = get_membership(payload.workspace_id, user, db)
    require_editor(membership)
    try:
        return await run_collection(db, payload, user_id=user.id, source="runner")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
