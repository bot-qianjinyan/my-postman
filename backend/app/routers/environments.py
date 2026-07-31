from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_membership, require_editor
from app.models import Environment, User
from app.schemas import EnvironmentCreate, EnvironmentOut, EnvironmentUpdate
from app.serializers import dumps_kv, env_to_out
from app.ws_manager import hub

router = APIRouter(tags=["environments"])


@router.get("/workspaces/{workspace_id}/environments", response_model=list[EnvironmentOut])
def list_environments(
    workspace_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EnvironmentOut]:
    get_membership(workspace_id, user, db)
    rows = (
        db.query(Environment)
        .filter(Environment.workspace_id == workspace_id)
        .order_by(Environment.id.asc())
        .all()
    )
    return [env_to_out(e) for e in rows]


@router.post("/workspaces/{workspace_id}/environments", response_model=EnvironmentOut)
async def create_environment(
    workspace_id: int,
    payload: EnvironmentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EnvironmentOut:
    membership = get_membership(workspace_id, user, db)
    require_editor(membership)
    env = Environment(
        workspace_id=workspace_id,
        name=payload.name.strip(),
        variables_json=dumps_kv(payload.variables),
        is_active=False,
    )
    db.add(env)
    db.commit()
    db.refresh(env)
    out = env_to_out(env)
    await hub.broadcast(
        workspace_id,
        {"type": "environment.updated", "environment": out.model_dump()},
        exclude_user_id=user.id,
    )
    return out


@router.put("/environments/{environment_id}", response_model=EnvironmentOut)
async def update_environment(
    environment_id: int,
    payload: EnvironmentUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EnvironmentOut:
    env = db.get(Environment, environment_id)
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")
    membership = get_membership(env.workspace_id, user, db)
    require_editor(membership)

    if payload.name is not None:
        env.name = payload.name.strip()
    if payload.variables is not None:
        env.variables_json = dumps_kv(payload.variables)
    if payload.is_active is True:
        db.query(Environment).filter(Environment.workspace_id == env.workspace_id).update(
            {"is_active": False}
        )
        env.is_active = True
    elif payload.is_active is False:
        env.is_active = False

    db.commit()
    db.refresh(env)
    out = env_to_out(env)
    await hub.broadcast(
        env.workspace_id,
        {"type": "environment.updated", "environment": out.model_dump()},
        exclude_user_id=user.id,
    )
    return out
