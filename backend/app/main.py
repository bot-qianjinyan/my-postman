from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import auth, collections, environments, proxy, workspaces, ws

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)
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
app.include_router(ws.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "app": settings.app_name}
