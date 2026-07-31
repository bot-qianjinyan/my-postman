from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_membership
from app.models import Environment, RequestHistory, User
from app.schemas import ProxySendIn, ProxySendOut
from app.services.env_utils import dumps_kv, loads_kv
from app.services.executor import execute_request

router = APIRouter(prefix="/proxy", tags=["proxy"])


@router.post("/send", response_model=ProxySendOut)
async def send_request(
    payload: ProxySendIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProxySendOut:
    get_membership(payload.workspace_id, user, db)

    env_vars = []
    env = None
    if payload.environment_id:
        env = db.get(Environment, payload.environment_id)
        if env and env.workspace_id == payload.workspace_id:
            env_vars = loads_kv(env.variables_json)
    else:
        env = (
            db.query(Environment)
            .filter(
                Environment.workspace_id == payload.workspace_id,
                Environment.is_active.is_(True),
            )
            .first()
        )
        if env:
            env_vars = loads_kv(env.variables_json)

    result = await execute_request(payload, env_vars)

    if env and result.env_updates:
        env.variables_json = dumps_kv(result.env_updates)

    db.add(
        RequestHistory(
            workspace_id=payload.workspace_id,
            request_id=payload.request_id,
            user_id=user.id,
            method=payload.method.upper(),
            url=payload.url,
            status_code=result.status_code,
            duration_ms=result.duration_ms,
            assertions_json=json.dumps([a.model_dump() for a in result.assertions]),
            source="manual",
        )
    )
    db.commit()
    return result
