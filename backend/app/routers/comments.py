from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_membership
from app.models import Comment, Membership, User
from app.schemas import CommentCreate, CommentOut
from app.ws_manager import hub

router = APIRouter(tags=["comments"])


def _extract_mentions(body: str, members: list[User]) -> list[int]:
    names = {u.name.lower(): u.id for u in members}
    found: list[int] = []
    for match in re.finditer(r"@([A-Za-z0-9_\-.\u4e00-\u9fff]+)", body):
        token = match.group(1).lower()
        if token in names and names[token] not in found:
            found.append(names[token])
    return found


def _to_out(comment: Comment, user_name: str) -> CommentOut:
    try:
        mentions = json.loads(comment.mentions_json or "[]")
    except Exception:
        mentions = []
    return CommentOut(
        id=comment.id,
        workspace_id=comment.workspace_id,
        request_id=comment.request_id,
        user_id=comment.user_id,
        user_name=user_name,
        body=comment.body,
        mentions=mentions if isinstance(mentions, list) else [],
        created_at=comment.created_at,
    )


@router.get("/workspaces/{workspace_id}/comments", response_model=list[CommentOut])
def list_comments(
    workspace_id: int,
    request_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CommentOut]:
    get_membership(workspace_id, user, db)
    q = db.query(Comment, User).join(User, User.id == Comment.user_id).filter(
        Comment.workspace_id == workspace_id
    )
    if request_id is not None:
        q = q.filter(Comment.request_id == request_id)
    rows = q.order_by(Comment.created_at.desc()).limit(200).all()
    return [_to_out(c, u.name) for c, u in rows]


@router.post("/workspaces/{workspace_id}/comments", response_model=CommentOut)
async def create_comment(
    workspace_id: int,
    payload: CommentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentOut:
    get_membership(workspace_id, user, db)
    members = (
        db.query(User)
        .join(Membership, Membership.user_id == User.id)
        .filter(Membership.workspace_id == workspace_id)
        .all()
    )
    mentions = _extract_mentions(payload.body, members)
    comment = Comment(
        workspace_id=workspace_id,
        request_id=payload.request_id,
        user_id=user.id,
        body=payload.body.strip(),
        mentions_json=json.dumps(mentions),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    out = _to_out(comment, user.name)
    await hub.broadcast(
        workspace_id,
        {"type": "comment.created", "comment": out.model_dump()},
    )
    return out


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    comment = db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    get_membership(comment.workspace_id, user, db)
    if comment.user_id != user.id:
        raise HTTPException(status_code=403, detail="Only author can delete")
    wid = comment.workspace_id
    db.delete(comment)
    db.commit()
    await hub.broadcast(wid, {"type": "comment.deleted", "comment_id": comment_id})
    return {"ok": True}
