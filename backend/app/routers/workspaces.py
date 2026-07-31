from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_membership
from app.models import Collection, Environment, Membership, User, Workspace
from app.schemas import (
    MemberOut,
    WorkspaceCreate,
    WorkspaceJoin,
    WorkspaceOut,
)
from app.ws_manager import hub

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _workspace_out(ws: Workspace, role: str) -> WorkspaceOut:
    return WorkspaceOut(
        id=ws.id,
        name=ws.name,
        invite_code=ws.invite_code,
        role=role,
        created_at=ws.created_at,
    )


@router.get("", response_model=list[WorkspaceOut])
def list_workspaces(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WorkspaceOut]:
    rows = (
        db.query(Workspace, Membership)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .filter(Membership.user_id == user.id)
        .order_by(Workspace.created_at.desc())
        .all()
    )
    return [_workspace_out(ws, m.role) for ws, m in rows]


@router.post("", response_model=WorkspaceOut)
async def create_workspace(
    payload: WorkspaceCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceOut:
    ws = Workspace(name=payload.name.strip(), invite_code=secrets.token_urlsafe(8)[:12])
    db.add(ws)
    db.flush()
    db.add(Membership(workspace_id=ws.id, user_id=user.id, role="owner"))
    db.add(Collection(workspace_id=ws.id, name="Default"))
    db.add(
        Environment(
            workspace_id=ws.id,
            name="Local",
            variables_json='[{"key":"baseUrl","value":"https://jsonplaceholder.typicode.com","enabled":true}]',
            is_active=True,
        )
    )
    db.commit()
    db.refresh(ws)
    return _workspace_out(ws, "owner")


@router.post("/join", response_model=WorkspaceOut)
async def join_workspace(
    payload: WorkspaceJoin,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceOut:
    ws = db.query(Workspace).filter(Workspace.invite_code == payload.invite_code.strip()).first()
    if not ws:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite code")
    existing = (
        db.query(Membership)
        .filter(Membership.workspace_id == ws.id, Membership.user_id == user.id)
        .first()
    )
    if existing:
        return _workspace_out(ws, existing.role)
    membership = Membership(workspace_id=ws.id, user_id=user.id, role="editor")
    db.add(membership)
    db.commit()
    await hub.broadcast(
        ws.id,
        {
            "type": "member.joined",
            "user_id": user.id,
            "user_name": user.name,
            "role": "editor",
        },
    )
    return _workspace_out(ws, "editor")


@router.get("/{workspace_id}/members", response_model=list[MemberOut])
def list_members(
    workspace_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MemberOut]:
    get_membership(workspace_id, user, db)
    rows = (
        db.query(Membership, User)
        .join(User, User.id == Membership.user_id)
        .filter(Membership.workspace_id == workspace_id)
        .all()
    )
    return [
        MemberOut(user_id=u.id, name=u.name, email=u.email, role=m.role)
        for m, u in rows
    ]
