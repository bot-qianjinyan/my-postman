from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.auth import decode_access_token
from app.database import get_db
from app.models import Membership, User
from app.ws_manager import Connection, hub

router = APIRouter(tags=["ws"])


@router.websocket("/ws/workspaces/{workspace_id}")
async def workspace_ws(
    websocket: WebSocket,
    workspace_id: int,
    token: str,
    db: Session = Depends(get_db),
) -> None:
    user_id = decode_access_token(token)
    if not user_id:
        await websocket.close(code=4401)
        return
    user = db.get(User, int(user_id))
    if not user:
        await websocket.close(code=4401)
        return
    membership = (
        db.query(Membership)
        .filter(Membership.workspace_id == workspace_id, Membership.user_id == user.id)
        .first()
    )
    if not membership:
        await websocket.close(code=4403)
        return

    conn = Connection(websocket=websocket, user_id=user.id, user_name=user.name)
    await hub.connect(workspace_id, conn)
    try:
        while True:
            message = await websocket.receive_text()
            # Client can ping; ignore content for MVP
            if message == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        await hub.disconnect(workspace_id, conn)
    except Exception:
        await hub.disconnect(workspace_id, conn)
