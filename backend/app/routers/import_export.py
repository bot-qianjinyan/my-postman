from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_membership, require_editor
from app.models import Collection, User
from app.schemas import CollectionOut, OpenAPIImportIn, OpenAPIImportOut
from app.services.docs import export_env_json, export_postman_collection
from app.services.openapi_import import import_openapi
from app.ws_manager import hub

router = APIRouter(tags=["import-export"])


@router.post("/import/openapi", response_model=OpenAPIImportOut)
async def import_openapi_spec(
    payload: OpenAPIImportIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OpenAPIImportOut:
    membership = get_membership(payload.workspace_id, user, db)
    require_editor(membership)
    try:
        col, count = import_openapi(
            db,
            workspace_id=payload.workspace_id,
            content=payload.content,
            collection_name=payload.collection_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    out = CollectionOut.model_validate(col)
    await hub.broadcast(
        payload.workspace_id,
        {"type": "collection.created", "collection": out.model_dump()},
        exclude_user_id=user.id,
    )
    return OpenAPIImportOut(collection=out, imported_count=count)


@router.get("/export/collections/{collection_id}/postman")
def export_collection_postman(
    collection_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    col = db.get(Collection, collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    get_membership(col.workspace_id, user, db)
    data = export_postman_collection(db, collection_id)
    return JSONResponse(data)


@router.get("/export/environments/{environment_id}/postman")
def export_environment_postman(
    environment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    from app.models import Environment

    env = db.get(Environment, environment_id)
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")
    get_membership(env.workspace_id, user, db)
    return JSONResponse(export_env_json(db, environment_id))
