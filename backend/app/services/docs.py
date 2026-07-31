from __future__ import annotations

import html

from sqlalchemy.orm import Session

from app.models import Collection, Workspace
from app.serializers import request_to_out


def build_workspace_docs(db: Session, workspace_id: int) -> tuple[str, str, str]:
    ws = db.get(Workspace, workspace_id)
    if not ws:
        raise ValueError("Workspace not found")
    collections = (
        db.query(Collection)
        .filter(Collection.workspace_id == workspace_id)
        .order_by(Collection.id.asc())
        .all()
    )
    lines = [f"# {ws.name}", "", f"Auto-generated API documentation for workspace `{ws.name}`.", ""]
    for col in collections:
        lines.append(f"## {col.name}")
        if col.description:
            lines.append(col.description)
        lines.append("")
        for req in sorted(col.requests, key=lambda r: (r.sort_order, r.id)):
            out = request_to_out(req)
            lines.append(f"### {out.method} {out.name}")
            if out.description:
                lines.append(out.description)
            lines.append("")
            lines.append(f"- **Protocol**: `{out.protocol}`")
            lines.append(f"- **URL**: `{out.url}`")
            if out.headers:
                lines.append("- **Headers**:")
                for h in out.headers:
                    if h.key:
                        lines.append(f"  - `{h.key}`: `{h.value}`")
            if out.protocol == "graphql" and out.graphql_query:
                lines.append("- **GraphQL Query**:")
                lines.append("```graphql")
                lines.append(out.graphql_query)
                lines.append("```")
            elif out.body and out.body_type != "none":
                lines.append("- **Body**:")
                lines.append("```json" if out.body_type == "json" else "```")
                lines.append(out.body)
                lines.append("```")
            if out.test_script:
                lines.append("- **Tests**: enabled")
            lines.append("")
    markdown = "\n".join(lines)
    html_doc = _markdown_to_simple_html(ws.name, markdown)
    return ws.name, markdown, html_doc


def _markdown_to_simple_html(title: str, markdown: str) -> str:
    # Minimal converter for headings/code/lists
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        f"<title>{html.escape(title)}</title>",
        "<style>body{font-family:IBM Plex Sans,system-ui;max-width:900px;margin:2rem auto;padding:0 1rem;line-height:1.5}"
        "code,pre{font-family:IBM Plex Mono,ui-monospace,monospace;background:#f4f6fa}"
        "pre{padding:0.75rem;overflow:auto;border-radius:8px} h1,h2,h3{margin-top:1.4em}</style>",
        "</head><body>",
    ]
    in_code = False
    for line in markdown.splitlines():
        if line.startswith("```"):
            if in_code:
                parts.append("</pre>")
                in_code = False
            else:
                parts.append("<pre>")
                in_code = True
            continue
        if in_code:
            parts.append(html.escape(line))
            continue
        if line.startswith("# "):
            parts.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            parts.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            parts.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            parts.append(f"<li>{html.escape(line[2:])}</li>")
        elif line.strip() == "":
            parts.append("<br/>")
        else:
            parts.append(f"<p>{html.escape(line)}</p>")
    parts.append("</body></html>")
    return "\n".join(parts)


def export_postman_collection(db: Session, collection_id: int) -> dict:
    col = db.get(Collection, collection_id)
    if not col:
        raise ValueError("Collection not found")
    items = []
    for req in sorted(col.requests, key=lambda r: (r.sort_order, r.id)):
        out = request_to_out(req)
        item = {
            "name": out.name,
            "event": [],
            "request": {
                "method": out.method,
                "header": [{"key": h.key, "value": h.value} for h in out.headers if h.key],
                "url": out.url,
                "body": {
                    "mode": "raw" if out.body_type != "none" else "raw",
                    "raw": out.body or "",
                },
            },
        }
        if out.pre_request_script:
            item["event"].append(
                {
                    "listen": "prerequest",
                    "script": {"type": "text/plain", "exec": out.pre_request_script.splitlines()},
                }
            )
        if out.test_script:
            item["event"].append(
                {
                    "listen": "test",
                    "script": {"type": "text/plain", "exec": out.test_script.splitlines()},
                }
            )
        items.append(item)
    return {
        "info": {
            "name": col.name,
            "description": col.description,
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": items,
    }


def export_env_json(db: Session, environment_id: int) -> dict:
    from app.models import Environment
    from app.serializers import env_to_out

    env = db.get(Environment, environment_id)
    if not env:
        raise ValueError("Environment not found")
    out = env_to_out(env)
    return {
        "id": str(env.id),
        "name": out.name,
        "values": [
            {"key": v.key, "value": v.value, "enabled": v.enabled} for v in out.variables
        ],
        "_postman_variable_scope": "environment",
    }
