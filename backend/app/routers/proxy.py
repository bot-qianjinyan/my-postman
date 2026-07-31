from __future__ import annotations

import time

import certifi
import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_membership
from app.models import RequestHistory, User
from app.schemas import ProxySendIn, ProxySendOut

router = APIRouter(prefix="/proxy", tags=["proxy"])


@router.post("/send", response_model=ProxySendOut)
async def send_request(
    payload: ProxySendIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProxySendOut:
    get_membership(payload.workspace_id, user, db)

    headers = {
        item.key: item.value
        for item in payload.headers
        if item.enabled and item.key.strip()
    }
    params = {
        item.key: item.value
        for item in payload.params
        if item.enabled and item.key.strip()
    }

    content = None
    if payload.body_type != "none" and payload.body:
        content = payload.body
        if payload.body_type == "json" and "content-type" not in {k.lower() for k in headers}:
            headers["Content-Type"] = "application/json"

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=payload.timeout,
            verify=certifi.where(),
        ) as client:
            resp = await client.request(
                method=payload.method.upper(),
                url=payload.url,
                headers=headers,
                params=params,
                content=content,
            )
        duration_ms = int((time.perf_counter() - started) * 1000)
        body_text = resp.text
        result = ProxySendOut(
            status_code=resp.status_code,
            headers={k: v for k, v in resp.headers.items()},
            body=body_text,
            duration_ms=duration_ms,
        )
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        result = ProxySendOut(
            status_code=None,
            headers={},
            body="",
            duration_ms=duration_ms,
            error=str(exc),
        )

    db.add(
        RequestHistory(
            workspace_id=payload.workspace_id,
            request_id=payload.request_id,
            user_id=user.id,
            method=payload.method.upper(),
            url=payload.url,
            status_code=result.status_code,
            duration_ms=result.duration_ms,
        )
    )
    db.commit()
    return result
