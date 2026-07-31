from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass

from fastapi import WebSocket


@dataclass
class Connection:
    websocket: WebSocket
    user_id: int
    user_name: str


class WorkspaceHub:
    def __init__(self) -> None:
        self._rooms: dict[int, list[Connection]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def connect(self, workspace_id: int, conn: Connection) -> None:
        await conn.websocket.accept()
        async with self._lock:
            self._rooms[workspace_id].append(conn)
        await self.broadcast(
            workspace_id,
            {
                "type": "presence.join",
                "user_id": conn.user_id,
                "user_name": conn.user_name,
                "online": self.online_users(workspace_id),
            },
            exclude_user_id=None,
        )

    async def disconnect(self, workspace_id: int, conn: Connection) -> None:
        async with self._lock:
            room = self._rooms.get(workspace_id, [])
            self._rooms[workspace_id] = [c for c in room if c.websocket is not conn.websocket]
        await self.broadcast(
            workspace_id,
            {
                "type": "presence.leave",
                "user_id": conn.user_id,
                "user_name": conn.user_name,
                "online": self.online_users(workspace_id),
            },
        )

    def online_users(self, workspace_id: int) -> list[dict]:
        seen: dict[int, str] = {}
        for conn in self._rooms.get(workspace_id, []):
            seen[conn.user_id] = conn.user_name
        return [{"user_id": uid, "user_name": name} for uid, name in seen.items()]

    async def broadcast(
        self,
        workspace_id: int,
        event: dict,
        exclude_user_id: int | None = None,
    ) -> None:
        payload = json.dumps(event, default=str)
        dead: list[Connection] = []
        for conn in list(self._rooms.get(workspace_id, [])):
            if exclude_user_id is not None and conn.user_id == exclude_user_id:
                continue
            try:
                await conn.websocket.send_text(payload)
            except Exception:
                dead.append(conn)
        if dead:
            async with self._lock:
                room = self._rooms.get(workspace_id, [])
                self._rooms[workspace_id] = [c for c in room if c not in dead]


hub = WorkspaceHub()
