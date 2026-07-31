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
    col = Collection(
        workspace_id=workspace_id,
        name=payload.name.strip(),
        description=payload.description or "",
    )
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
        .order_by(ApiRequest.sort_order.asc(), ApiRequest.id.asc())
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
        protocol=payload.protocol or "http",
        updated_by=user.id,
        test_script=(
            "pm.test('Status is set', lambda: pm.expect(pm.response.code is not None).to_be_truthy())"
        ),
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

    fields = {
        "name": lambda v: setattr(req, "name", v.strip()),
        "description": lambda v: setattr(req, "description", v),
        "protocol": lambda v: setattr(req, "protocol", v),
        "method": lambda v: setattr(req, "method", v.upper()),
        "url": lambda v: setattr(req, "url", v),
        "body_type": lambda v: setattr(req, "body_type", v),
        "body": lambda v: setattr(req, "body", v),
        "auth_type": lambda v: setattr(req, "auth_type", v),
        "pre_request_script": lambda v: setattr(req, "pre_request_script", v),
        "test_script": lambda v: setattr(req, "test_script", v),
        "graphql_query": lambda v: setattr(req, "graphql_query", v),
        "graphql_variables": lambda v: setattr(req, "graphql_variables", v),
        "grpc_service": lambda v: setattr(req, "grpc_service", v),
        "grpc_method": lambda v: setattr(req, "grpc_method", v),
        "grpc_message": lambda v: setattr(req, "grpc_message", v),
    }
    data = payload.model_dump(exclude_unset=True)
    for key, apply in fields.items():
        if key in data and data[key] is not None:
            apply(data[key])
    if payload.headers is not None:
        req.headers_json = dumps_kv(payload.headers)
    if payload.params is not None:
        req.params_json = dumps_kv(payload.params)
    if payload.auth is not None:
        req.auth_json = json.dumps(payload.auth)
    if payload.ws_messages is not None:
        req.ws_messages_json = json.dumps(payload.ws_messages)

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
