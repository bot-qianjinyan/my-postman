from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.migrate import ensure_schema
from app.routers import (
    auth,
    collections,
    comments,
    docs,
    environments,
    import_export,
    mock,
    monitors,
    proxy,
    runner,
    workspaces,
    ws,
)
from app.services.monitor_scheduler import scheduler

ensure_schema()


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler.start()
    yield
    await scheduler.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(workspaces.router, prefix="/api")
app.include_router(collections.router, prefix="/api")
app.include_router(environments.router, prefix="/api")
app.include_router(proxy.router, prefix="/api")
app.include_router(runner.router, prefix="/api")
app.include_router(import_export.router, prefix="/api")
app.include_router(mock.router, prefix="/api")
app.include_router(comments.router, prefix="/api")
app.include_router(docs.router, prefix="/api")
app.include_router(monitors.router, prefix="/api")
app.include_router(ws.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "app": settings.app_name, "features": ["v2", "v3", "v4"]}
