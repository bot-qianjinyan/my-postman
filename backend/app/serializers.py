from __future__ import annotations

import json

from app.models import ApiRequest, Environment
from app.schemas import EnvironmentOut, KeyValue, RequestOut


def _loads_list(raw: str) -> list[KeyValue]:
    try:
        data = json.loads(raw or "[]")
        return [KeyValue(**item) for item in data]
    except Exception:
        return []


def _loads_dict(raw: str) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def request_to_out(req: ApiRequest) -> RequestOut:
    return RequestOut(
        id=req.id,
        collection_id=req.collection_id,
        name=req.name,
        method=req.method,
        url=req.url,
        headers=_loads_list(req.headers_json),
        params=_loads_list(req.params_json),
        body_type=req.body_type,
        body=req.body or "",
        auth_type=req.auth_type,
        auth=_loads_dict(req.auth_json),
        version=req.version,
        updated_by=req.updated_by,
        updated_at=req.updated_at,
    )


def env_to_out(env: Environment) -> EnvironmentOut:
    return EnvironmentOut(
        id=env.id,
        workspace_id=env.workspace_id,
        name=env.name,
        variables=_loads_list(env.variables_json),
        is_active=env.is_active,
    )


def dumps_kv(items: list[KeyValue] | None) -> str:
    if items is None:
        return "[]"
    return json.dumps([item.model_dump() for item in items])
