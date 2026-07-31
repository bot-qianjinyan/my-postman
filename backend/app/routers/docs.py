from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_membership
from app.models import User
from app.schemas import DocsOut
from app.services.docs import build_workspace_docs

router = APIRouter(tags=["docs"])


@router.get("/workspaces/{workspace_id}/docs", response_model=DocsOut)
def get_docs(
    workspace_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocsOut:
    get_membership(workspace_id, user, db)
    try:
        title, markdown, html_doc = build_workspace_docs(db, workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DocsOut(workspace_id=workspace_id, title=title, markdown=markdown, html=html_doc)


@router.get("/workspaces/{workspace_id}/docs.html", response_class=HTMLResponse)
def get_docs_html(
    workspace_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    get_membership(workspace_id, user, db)
    try:
        _, _, html_doc = build_workspace_docs(db, workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return HTMLResponse(html_doc)
