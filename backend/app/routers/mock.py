from __future__ import annotations

import asyncio
import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_membership, require_editor
from app.models import MockRoute, MockServer, User
from app.schemas import MockRouteOut, MockServerCreate, MockServerOut

router = APIRouter(tags=["mock"])


def _route_out(route: MockRoute) -> MockRouteOut:
    try:
        headers = json.loads(route.headers_json or "{}")
    except Exception:
        headers = {}
    return MockRouteOut(
        id=route.id,
        method=route.method,
        path=route.path,
        status_code=route.status_code,
        headers=headers if isinstance(headers, dict) else {},
        body=route.body,
        delay_ms=route.delay_ms,
    )


def _server_out(server: MockServer, request: Request | None = None) -> MockServerOut:
    base = f"/api/mock/{server.slug}"
    if request is not None:
        base = str(request.base_url).rstrip("/") + base
    return MockServerOut(
        id=server.id,
        workspace_id=server.workspace_id,
        name=server.name,
        slug=server.slug,
        is_enabled=server.is_enabled,
        base_url=base,
        routes=[_route_out(r) for r in server.routes],
    )


@router.get("/workspaces/{workspace_id}/mocks", response_model=list[MockServerOut])
def list_mocks(
    workspace_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MockServerOut]:
    get_membership(workspace_id, user, db)
    rows = db.query(MockServer).filter(MockServer.workspace_id == workspace_id).all()
    return [_server_out(s, request) for s in rows]


@router.post("/workspaces/{workspace_id}/mocks", response_model=MockServerOut)
def create_mock(
    workspace_id: int,
    payload: MockServerCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MockServerOut:
    membership = get_membership(workspace_id, user, db)
    require_editor(membership)
    server = MockServer(
        workspace_id=workspace_id,
        name=payload.name.strip(),
        slug=secrets.token_urlsafe(6),
    )
    db.add(server)
    db.flush()
    if payload.routes:
        for r in payload.routes:
            db.add(
                MockRoute(
                    mock_server_id=server.id,
                    method=str(r.get("method", "GET")).upper(),
                    path=str(r.get("path", "/")),
                    status_code=int(r.get("status_code", 200)),
                    headers_json=json.dumps(r.get("headers") or {}),
                    body=str(r.get("body", '{"ok":true}')),
                    delay_ms=int(r.get("delay_ms", 0)),
                )
            )
    else:
        db.add(
            MockRoute(
                mock_server_id=server.id,
                method="GET",
                path="/hello",
                status_code=200,
                body='{"message":"hello from mock"}',
            )
        )
    db.commit()
    db.refresh(server)
    return _server_out(server, request)


@router.delete("/mocks/{mock_id}")
def delete_mock(
    mock_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    server = db.get(MockServer, mock_id)
    if not server:
        raise HTTPException(status_code=404, detail="Mock not found")
    membership = get_membership(server.workspace_id, user, db)
    require_editor(membership)
    db.delete(server)
    db.commit()
    return {"ok": True}


@router.api_route("/mock/{slug}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def serve_mock(slug: str, path: str, request: Request, db: Session = Depends(get_db)) -> Response:
    server = db.query(MockServer).filter(MockServer.slug == slug, MockServer.is_enabled.is_(True)).first()
    if not server:
        raise HTTPException(status_code=404, detail="Mock server not found")
    full_path = "/" + path.lstrip("/")
    route = next(
        (
            r
            for r in server.routes
            if r.method.upper() == request.method.upper() and r.path.rstrip("/") == full_path.rstrip("/")
        ),
        None,
    )
    if not route:
        # fallback exact "/" match
        route = next(
            (
                r
                for r in server.routes
                if r.method.upper() == request.method.upper() and r.path in {full_path, "/" + path}
            ),
            None,
        )
    if not route:
        raise HTTPException(status_code=404, detail="Mock route not found")
    if route.delay_ms:
        await asyncio.sleep(route.delay_ms / 1000)
    try:
        headers = json.loads(route.headers_json or "{}")
    except Exception:
        headers = {}
    return Response(
        content=route.body,
        status_code=route.status_code,
        media_type="application/json",
        headers={str(k): str(v) for k, v in (headers or {}).items()},
    )
