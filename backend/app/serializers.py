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


def _loads_str_list(raw: str) -> list[str]:
    try:
        data = json.loads(raw or "[]")
        return [str(x) for x in data] if isinstance(data, list) else []
    except Exception:
        return []


def request_to_out(req: ApiRequest) -> RequestOut:
    return RequestOut(
        id=req.id,
        collection_id=req.collection_id,
        name=req.name,
        description=getattr(req, "description", "") or "",
        protocol=getattr(req, "protocol", "http") or "http",
        method=req.method,
        url=req.url,
        headers=_loads_list(req.headers_json),
        params=_loads_list(req.params_json),
        body_type=req.body_type,
        body=req.body or "",
        auth_type=req.auth_type,
        auth=_loads_dict(req.auth_json),
        pre_request_script=getattr(req, "pre_request_script", "") or "",
        test_script=getattr(req, "test_script", "") or "",
        graphql_query=getattr(req, "graphql_query", "") or "",
        graphql_variables=getattr(req, "graphql_variables", "{}") or "{}",
        grpc_service=getattr(req, "grpc_service", "") or "",
        grpc_method=getattr(req, "grpc_method", "") or "",
        grpc_message=getattr(req, "grpc_message", "{}") or "{}",
        ws_messages=_loads_str_list(getattr(req, "ws_messages_json", "[]") or "[]"),
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
