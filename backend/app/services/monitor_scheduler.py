from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import Monitor
from app.schemas import RunnerIn
from app.services.runner import run_collection

logger = logging.getLogger("mypostman.monitor")


class MonitorScheduler:
    def __init__(self, interval_seconds: int = 30) -> None:
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task | None = None
        self._stopping = False

    def start(self) -> None:
        if self._task is None:
            self._stopping = False
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stopping = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass
            self._task = None

    async def _loop(self) -> None:
        while not self._stopping:
            try:
                await self._tick()
            except Exception:
                logger.exception("monitor tick failed")
            await asyncio.sleep(self.interval_seconds)

    async def _tick(self) -> None:
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            monitors = db.query(Monitor).filter(Monitor.is_enabled.is_(True)).all()
            for monitor in monitors:
                due = False
                if monitor.last_run_at is None:
                    due = True
                else:
                    due = monitor.last_run_at <= now - timedelta(minutes=monitor.interval_minutes)
                if not due:
                    continue
                try:
                    result = await run_collection(
                        db,
                        RunnerIn(
                            workspace_id=monitor.workspace_id,
                            collection_id=monitor.collection_id,
                            environment_id=monitor.environment_id,
                        ),
                        user_id=None,
                        source="monitor",
                        monitor_id=monitor.id,
                    )
                    monitor.last_run_at = datetime.utcnow()
                    monitor.last_status = result.status
                    monitor.last_summary = f"{result.passed}/{result.total} passed"
                    db.commit()
                except Exception as exc:
                    monitor.last_run_at = datetime.utcnow()
                    monitor.last_status = "fail"
                    monitor.last_summary = str(exc)
                    db.commit()
        finally:
            db.close()


scheduler = MonitorScheduler()
