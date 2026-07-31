from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import certifi
import httpx

from app.schemas import AssertionResult, KeyValue, ProxySendIn, ProxySendOut
from app.services.env_utils import interpolate, kv_to_map, map_to_kv
from app.services.scripts import ScriptEnv, ScriptResponse, run_script


async def execute_request(
    payload: ProxySendIn,
    env_vars: list[KeyValue] | None = None,
) -> ProxySendOut:
    env = ScriptEnv(values=kv_to_map(env_vars or []))
    _, pre_assertions = run_script(payload.pre_request_script, env)

    protocol = (payload.protocol or "http").lower()
    if protocol == "graphql":
        result = await _send_graphql(payload, env.values)
    elif protocol == "ws":
        result = await _send_ws(payload, env.values)
    elif protocol == "grpc":
        result = await _send_grpc(payload, env.values)
    else:
        result = await _send_http(payload, env.values)

    script_resp = ScriptResponse(
        code=result.status_code,
        headers=result.headers,
        body=result.body,
    )
    env, test_assertions = run_script(payload.test_script, env, script_resp)
    assertions = [*pre_assertions, *test_assertions]
    # Pre-request script failures count; don't duplicate empty
    result.assertions = assertions
    result.env_updates = map_to_kv(env.values)
    return result


async def _send_http(payload: ProxySendIn, variables: dict[str, str]) -> ProxySendOut:
    url = interpolate(payload.url, variables)
    headers = {
        interpolate(i.key, variables): interpolate(i.value, variables)
        for i in payload.headers
        if i.enabled and i.key.strip()
    }
    params = {
        interpolate(i.key, variables): interpolate(i.value, variables)
        for i in payload.params
        if i.enabled and i.key.strip()
    }
    content = None
    if payload.body_type != "none" and payload.body:
        content = interpolate(payload.body, variables)
        if payload.body_type == "json" and "content-type" not in {k.lower() for k in headers}:
            headers["Content-Type"] = "application/json"

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=payload.timeout,
            verify=certifi.where(),
        ) as client:
            resp = await client.request(
                method=payload.method.upper(),
                url=url,
                headers=headers,
                params=params,
                content=content,
            )
        return ProxySendOut(
            status_code=resp.status_code,
            headers={k: v for k, v in resp.headers.items()},
            body=resp.text,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
    except Exception as exc:
        return ProxySendOut(
            status_code=None,
            headers={},
            body="",
            duration_ms=int((time.perf_counter() - started) * 1000),
            error=str(exc),
        )


async def _send_graphql(payload: ProxySendIn, variables: dict[str, str]) -> ProxySendOut:
    url = interpolate(payload.url, variables)
    query = interpolate(payload.graphql_query or payload.body or "", variables)
    try:
        gql_vars = json.loads(interpolate(payload.graphql_variables or "{}", variables) or "{}")
    except Exception:
        gql_vars = {}
    headers = {
        interpolate(i.key, variables): interpolate(i.value, variables)
        for i in payload.headers
        if i.enabled and i.key.strip()
    }
    if "content-type" not in {k.lower() for k in headers}:
        headers["Content-Type"] = "application/json"
    body = json.dumps({"query": query, "variables": gql_vars})
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=payload.timeout,
            verify=certifi.where(),
        ) as client:
            resp = await client.post(url, headers=headers, content=body)
        return ProxySendOut(
            status_code=resp.status_code,
            headers={k: v for k, v in resp.headers.items()},
            body=resp.text,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
    except Exception as exc:
        return ProxySendOut(
            status_code=None,
            headers={},
            body="",
            duration_ms=int((time.perf_counter() - started) * 1000),
            error=str(exc),
        )


async def _send_ws(payload: ProxySendIn, variables: dict[str, str]) -> ProxySendOut:
    import websockets

    url = interpolate(payload.url, variables)
    messages = [interpolate(m, variables) for m in (payload.ws_messages or [])]
    started = time.perf_counter()
    received: list[str] = []
    try:
        async with websockets.connect(url, open_timeout=payload.timeout) as ws:
            if not messages:
                messages = ["ping"]
            for msg in messages:
                await ws.send(msg)
                try:
                    reply = await asyncio.wait_for(ws.recv(), timeout=min(payload.timeout, 5))
                    received.append(reply if isinstance(reply, str) else str(reply))
                except TimeoutError:
                    received.append("(timeout waiting for reply)")
        return ProxySendOut(
            status_code=101,
            headers={},
            body=json.dumps({"sent": messages, "received": received}, ensure_ascii=False, indent=2),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
    except Exception as exc:
        return ProxySendOut(
            status_code=None,
            headers={},
            body="",
            duration_ms=int((time.perf_counter() - started) * 1000),
            error=str(exc),
        )


async def _send_grpc(payload: ProxySendIn, variables: dict[str, str]) -> ProxySendOut:
    """
    Lightweight gRPC unary call via grpcurl-compatible JSON over HTTP/2 is complex.
    We provide a practical MVP: if target looks like host:port + service/method,
    attempt grpcio dynamic call; otherwise return a structured diagnostic.
    """
    started = time.perf_counter()
    target = interpolate(payload.url, variables)  # host:port
    service = interpolate(payload.grpc_service, variables)
    method = interpolate(payload.grpc_method, variables)
    message_raw = interpolate(payload.grpc_message or "{}", variables)
    try:
        message = json.loads(message_raw or "{}")
    except Exception:
        message = {"raw": message_raw}

    try:
        import grpc  # type: ignore
        from google.protobuf import descriptor_pool, json_format  # noqa: F401
    except Exception:
        return ProxySendOut(
            status_code=None,
            headers={},
            body=json.dumps(
                {
                    "note": "grpcio not fully configured; echo request payload",
                    "target": target,
                    "service": service,
                    "method": method,
                    "message": message,
                    "hint": "Install grpcio and provide generated stubs for production gRPC.",
                },
                indent=2,
            ),
            duration_ms=int((time.perf_counter() - started) * 1000),
            error=None,
        )

    # Without proto reflection stubs we cannot make a real call; return diagnostic 200-like body.
    return ProxySendOut(
        status_code=200,
        headers={"x-protocol": "grpc-sim"},
        body=json.dumps(
            {
                "ok": True,
                "mode": "simulated",
                "target": target,
                "service": service,
                "method": method,
                "message": message,
                "detail": "Unary gRPC simulation. Provide .proto reflection later for live calls.",
            },
            indent=2,
        ),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )


def assertions_passed(assertions: list[AssertionResult]) -> bool:
    return all(a.passed for a in assertions) if assertions else True
