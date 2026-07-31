#!/usr/bin/env python3
"""Newman-compatible CLI for MyPostman collections.

Examples:
  python -m cli run collection.json -e env.json
  python -m cli run --collection-id 1 --token <jwt> --api http://127.0.0.1:8001
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click
import httpx


def _load_json(path: str | None) -> dict[str, Any] | list[Any] | None:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _env_map(env_doc: dict[str, Any] | None) -> dict[str, str]:
    if not env_doc:
        return {}
    values = env_doc.get("values") or []
    out: dict[str, str] = {}
    for item in values:
        if item.get("enabled", True) and item.get("key"):
            out[str(item["key"])] = str(item.get("value") or "")
    return out


def _interpolate(text: str, variables: dict[str, str]) -> str:
    import re

    def repl(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return variables.get(key, match.group(0))

    return re.sub(r"\{\{\s*([^{}]+?)\s*\}\}", repl, text or "")


@click.group()
def main() -> None:
    """MyPostman CLI (Newman-compatible collection runner)."""


@main.command("run")
@click.argument("collection_file", required=False)
@click.option("-e", "--environment", "env_file", default=None, help="Postman environment JSON")
@click.option("--collection-id", type=int, default=None, help="Run via API by collection id")
@click.option("--workspace-id", type=int, default=None)
@click.option("--token", default=None, help="Bearer token for API mode")
@click.option("--api", default="http://127.0.0.1:8001", help="API base URL")
@click.option("--bail", is_flag=True, help="Stop on first failure")
def run_cmd(
    collection_file: str | None,
    env_file: str | None,
    collection_id: int | None,
    workspace_id: int | None,
    token: str | None,
    api: str,
    bail: bool,
) -> None:
    """Run a Postman Collection v2.1 file or a server-side collection."""
    if collection_id is not None:
        if not token or workspace_id is None:
            raise click.ClickException("API mode requires --token and --workspace-id")
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{api.rstrip('/')}/api/runner/run",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "workspace_id": workspace_id,
                    "collection_id": collection_id,
                    "stop_on_failure": bail,
                },
            )
            if resp.status_code >= 400:
                raise click.ClickException(resp.text)
            data = resp.json()
            click.echo(
                f"{data['status'].upper()}: {data['passed']}/{data['total']} passed (run_id={data['run_id']})"
            )
            for item in data.get("items") or []:
                mark = "✓" if item.get("passed") else "✗"
                click.echo(
                    f"  {mark} {item.get('name')} [{item.get('status_code')}] {item.get('duration_ms')}ms"
                )
            sys.exit(0 if data.get("status") == "pass" else 1)

    if not collection_file:
        raise click.ClickException("Provide collection JSON file or --collection-id")

    collection = _load_json(collection_file)
    if not isinstance(collection, dict):
        raise click.ClickException("Invalid collection JSON")
    env_vars = _env_map(_load_json(env_file) if env_file else None)

    items = collection.get("item") or []
    passed = failed = 0
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        for item in items:
            name = item.get("name") or "request"
            req = item.get("request") or {}
            method = (req.get("method") or "GET").upper()
            url = req.get("url")
            if isinstance(url, dict):
                url = url.get("raw") or ""
            url = _interpolate(str(url), env_vars)
            headers = {
                h.get("key"): _interpolate(str(h.get("value") or ""), env_vars)
                for h in (req.get("header") or [])
                if h.get("key")
            }
            body_obj = req.get("body") or {}
            content = _interpolate(str(body_obj.get("raw") or ""), env_vars) or None
            try:
                resp = client.request(method, url, headers=headers, content=content)
                ok = 200 <= resp.status_code < 400
                mark = "✓" if ok else "✗"
                click.echo(f"{mark} {name} [{resp.status_code}]")
                if ok:
                    passed += 1
                else:
                    failed += 1
                    if bail:
                        break
            except Exception as exc:
                failed += 1
                click.echo(f"✗ {name} error: {exc}")
                if bail:
                    break

    total = passed + failed
    status = "pass" if failed == 0 else "fail"
    click.echo(f"\n{status.upper()}: {passed}/{total} passed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
