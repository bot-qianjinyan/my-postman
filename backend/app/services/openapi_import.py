from __future__ import annotations

import json
from typing import Any

import yaml
from sqlalchemy.orm import Session

from app.models import ApiRequest, Collection


def _load_spec(content: str) -> dict[str, Any]:
    text = content.strip()
    if not text:
        raise ValueError("Empty OpenAPI content")
    try:
        if text.startswith("{"):
            data = json.loads(text)
        else:
            data = yaml.safe_load(text)
    except Exception as exc:
        raise ValueError(f"Invalid OpenAPI document: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("OpenAPI root must be an object")
    return data


def _resolve_server(spec: dict[str, Any]) -> str:
    servers = spec.get("servers") or []
    if servers and isinstance(servers, list) and isinstance(servers[0], dict):
        return str(servers[0].get("url") or "").rstrip("/")
    return ""


def import_openapi(
    db: Session,
    workspace_id: int,
    content: str,
    collection_name: str | None = None,
) -> tuple[Collection, int]:
    spec = _load_spec(content)
    title = collection_name or (spec.get("info") or {}).get("title") or "OpenAPI Import"
    base = _resolve_server(spec)
    paths = spec.get("paths") or {}
    if not isinstance(paths, dict):
        raise ValueError("OpenAPI paths must be an object")

    col = Collection(
        workspace_id=workspace_id,
        name=str(title)[:200],
        description=str((spec.get("info") or {}).get("description") or "")[:2000],
    )
    db.add(col)
    db.flush()

    count = 0
    order = 0
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.lower() not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "head",
                "options",
            }:
                continue
            op = op or {}
            name = op.get("operationId") or op.get("summary") or f"{method.upper()} {path}"
            url = f"{base}{path}" if base else path
            body = ""
            body_type = "none"
            if method.lower() in {"post", "put", "patch"}:
                body_type = "json"
                body = "{}"
            req = ApiRequest(
                collection_id=col.id,
                name=str(name)[:200],
                description=str(op.get("description") or "")[:2000],
                protocol="http",
                method=method.upper(),
                url=url,
                body_type=body_type,
                body=body,
                sort_order=order,
                test_script=(
                    "pm.test('Status code is 2xx', lambda: "
                    "pm.expect(pm.response.code is not None and 200 <= pm.response.code < 300)"
                    ".to_be_truthy())"
                ),
            )
            db.add(req)
            order += 1
            count += 1

    db.commit()
    db.refresh(col)
    return col, count
