from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_membership, require_editor
from app.models import Collection, Monitor, User
from app.schemas import MonitorCreate, MonitorOut, MonitorUpdate, RunnerIn, RunnerOut
from app.services.runner import run_collection

router = APIRouter(tags=["monitors"])


def _to_out(m: Monitor) -> MonitorOut:
    return MonitorOut(
        id=m.id,
        workspace_id=m.workspace_id,
        collection_id=m.collection_id,
        environment_id=m.environment_id,
        name=m.name,
        interval_minutes=m.interval_minutes,
        is_enabled=m.is_enabled,
        last_run_at=m.last_run_at,
        last_status=m.last_status,
        last_summary=m.last_summary,
    )


@router.get("/workspaces/{workspace_id}/monitors", response_model=list[MonitorOut])
def list_monitors(
    workspace_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MonitorOut]:
    get_membership(workspace_id, user, db)
    rows = (
        db.query(Monitor)
        .filter(Monitor.workspace_id == workspace_id)
        .order_by(Monitor.id.desc())
        .all()
    )
    return [_to_out(m) for m in rows]


@router.post("/workspaces/{workspace_id}/monitors", response_model=MonitorOut)
def create_monitor(
    workspace_id: int,
    payload: MonitorCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonitorOut:
    membership = get_membership(workspace_id, user, db)
    require_editor(membership)
    col = db.get(Collection, payload.collection_id)
    if not col or col.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Collection not found")
    monitor = Monitor(
        workspace_id=workspace_id,
        collection_id=payload.collection_id,
        environment_id=payload.environment_id,
        name=payload.name.strip(),
        interval_minutes=max(1, payload.interval_minutes),
    )
    db.add(monitor)
    db.commit()
    db.refresh(monitor)
    return _to_out(monitor)


@router.put("/monitors/{monitor_id}", response_model=MonitorOut)
def update_monitor(
    monitor_id: int,
    payload: MonitorUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonitorOut:
    monitor = db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    membership = get_membership(monitor.workspace_id, user, db)
    require_editor(membership)
    if payload.name is not None:
        monitor.name = payload.name.strip()
    if payload.interval_minutes is not None:
        monitor.interval_minutes = max(1, payload.interval_minutes)
    if payload.is_enabled is not None:
        monitor.is_enabled = payload.is_enabled
    if payload.environment_id is not None:
        monitor.environment_id = payload.environment_id
    db.commit()
    db.refresh(monitor)
    return _to_out(monitor)


@router.post("/monitors/{monitor_id}/run", response_model=RunnerOut)
async def run_monitor_now(
    monitor_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RunnerOut:
    monitor = db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    membership = get_membership(monitor.workspace_id, user, db)
    require_editor(membership)
    result = await run_collection(
        db,
        RunnerIn(
            workspace_id=monitor.workspace_id,
            collection_id=monitor.collection_id,
            environment_id=monitor.environment_id,
            stop_on_failure=False,
        ),
        user_id=user.id,
        source="monitor",
        monitor_id=monitor.id,
    )
    monitor.last_run_at = datetime.utcnow()
    monitor.last_status = result.status
    monitor.last_summary = f"{result.passed}/{result.total} passed"
    db.commit()
    return result


@router.delete("/monitors/{monitor_id}")
def delete_monitor(
    monitor_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    monitor = db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    membership = get_membership(monitor.workspace_id, user, db)
    require_editor(membership)
    db.delete(monitor)
    db.commit()
    return {"ok": True}
