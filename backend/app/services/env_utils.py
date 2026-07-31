from __future__ import annotations

import json
import re

from app.schemas import KeyValue


def kv_to_map(items: list[KeyValue]) -> dict[str, str]:
    return {i.key: i.value for i in items if i.enabled and i.key}


def map_to_kv(data: dict[str, str]) -> list[KeyValue]:
    return [KeyValue(key=k, value=v, enabled=True) for k, v in data.items()]


def interpolate(text: str, variables: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return variables.get(key, match.group(0))

    return re.sub(r"\{\{\s*([^{}]+?)\s*\}\}", repl, text or "")


def loads_kv(raw: str) -> list[KeyValue]:
    try:
        data = json.loads(raw or "[]")
        return [KeyValue(**item) for item in data]
    except Exception:
        return []


def dumps_kv(items: list[KeyValue] | None) -> str:
    if items is None:
        return "[]"
    return json.dumps([i.model_dump() for i in items])
