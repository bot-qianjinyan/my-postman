from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_membership, require_editor
from app.models import ApiRequest, Collection, User
from app.schemas import CollectionCreate, CollectionOut, RequestCreate, RequestOut, RequestUpdate
from app.serializers import dumps_kv, request_to_out
from app.ws_manager import hub

router = APIRouter(tags=["collections"])


@router.get("/workspaces/{workspace_id}/collections", response_model=list[CollectionOut])
def list_collections(
    workspace_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CollectionOut]:
    get_membership(workspace_id, user, db)
    rows = (
        db.query(Collection)
        .filter(Collection.workspace_id == workspace_id)
        .order_by(Collection.id.asc())
        .all()
    )
    return [CollectionOut.model_validate(c) for c in rows]


@router.post("/workspaces/{workspace_id}/collections", response_model=CollectionOut)
async def create_collection(
    workspace_id: int,
    payload: CollectionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CollectionOut:
    membership = get_membership(workspace_id, user, db)
    require_editor(membership)
    col = Collection(workspace_id=workspace_id, name=payload.name.strip())
    db.add(col)
    db.commit()
    db.refresh(col)
    await hub.broadcast(
        workspace_id,
        {"type": "collection.created", "collection": CollectionOut.model_validate(col).model_dump()},
        exclude_user_id=user.id,
    )
    return CollectionOut.model_validate(col)


@router.get("/collections/{collection_id}/requests", response_model=list[RequestOut])
def list_requests(
    collection_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RequestOut]:
    col = db.get(Collection, collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    get_membership(col.workspace_id, user, db)
    rows = (
        db.query(ApiRequest)
        .filter(ApiRequest.collection_id == collection_id)
        .order_by(ApiRequest.id.asc())
        .all()
    )
    return [request_to_out(r) for r in rows]


@router.post("/collections/{collection_id}/requests", response_model=RequestOut)
async def create_request(
    collection_id: int,
    payload: RequestCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RequestOut:
    col = db.get(Collection, collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    membership = get_membership(col.workspace_id, user, db)
    require_editor(membership)
    req = ApiRequest(
        collection_id=collection_id,
        name=payload.name.strip(),
        method=payload.method.upper(),
        url=payload.url,
        updated_by=user.id,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    out = request_to_out(req)
    await hub.broadcast(
        col.workspace_id,
        {"type": "request.created", "request": out.model_dump()},
        exclude_user_id=user.id,
    )
    return out


@router.put("/requests/{request_id}", response_model=RequestOut)
async def update_request(
    request_id: int,
    payload: RequestUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RequestOut:
    req = db.get(ApiRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    col = db.get(Collection, req.collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    membership = get_membership(col.workspace_id, user, db)
    require_editor(membership)

    if payload.version is not None and payload.version != req.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Version conflict", "current": request_to_out(req).model_dump()},
        )

    if payload.name is not None:
        req.name = payload.name.strip()
    if payload.method is not None:
        req.method = payload.method.upper()
    if payload.url is not None:
        req.url = payload.url
    if payload.headers is not None:
        req.headers_json = dumps_kv(payload.headers)
    if payload.params is not None:
        req.params_json = dumps_kv(payload.params)
    if payload.body_type is not None:
        req.body_type = payload.body_type
    if payload.body is not None:
        req.body = payload.body
    if payload.auth_type is not None:
        req.auth_type = payload.auth_type
    if payload.auth is not None:
        req.auth_json = json.dumps(payload.auth)

    req.version += 1
    req.updated_by = user.id
    db.commit()
    db.refresh(req)
    out = request_to_out(req)
    await hub.broadcast(
        col.workspace_id,
        {
            "type": "request.updated",
            "request": out.model_dump(),
            "updated_by": user.id,
            "updated_by_name": user.name,
        },
        exclude_user_id=user.id,
    )
    return out


@router.delete("/requests/{request_id}")
async def delete_request(
    request_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    req = db.get(ApiRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    col = db.get(Collection, req.collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    membership = get_membership(col.workspace_id, user, db)
    require_editor(membership)
    rid = req.id
    cid = req.collection_id
    wid = col.workspace_id
    db.delete(req)
    db.commit()
    await hub.broadcast(
        wid,
        {"type": "request.deleted", "request_id": rid, "collection_id": cid},
        exclude_user_id=user.id,
    )
    return {"ok": True}
