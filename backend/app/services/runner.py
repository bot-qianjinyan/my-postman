from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models import ApiRequest, Collection, Environment, RequestHistory, RunResult
from app.schemas import (
    KeyValue,
    ProxySendIn,
    RunnerIn,
    RunnerItemOut,
    RunnerOut,
)
from app.services.env_utils import dumps_kv, loads_kv
from app.services.executor import assertions_passed, execute_request
from app.serializers import request_to_out


async def run_collection(
    db: Session,
    payload: RunnerIn,
    user_id: int | None,
    source: str = "runner",
    monitor_id: int | None = None,
) -> RunnerOut:
    col = db.get(Collection, payload.collection_id)
    if not col or col.workspace_id != payload.workspace_id:
        raise ValueError("Collection not found in workspace")

    env_vars: list[KeyValue] = []
    env: Environment | None = None
    if payload.environment_id:
        env = db.get(Environment, payload.environment_id)
        if env and env.workspace_id == payload.workspace_id:
            env_vars = loads_kv(env.variables_json)
    else:
        env = (
            db.query(Environment)
            .filter(
                Environment.workspace_id == payload.workspace_id,
                Environment.is_active.is_(True),
            )
            .first()
        )
        if env:
            env_vars = loads_kv(env.variables_json)

    requests = (
        db.query(ApiRequest)
        .filter(ApiRequest.collection_id == col.id)
        .order_by(ApiRequest.sort_order.asc(), ApiRequest.id.asc())
        .all()
    )

    items: list[RunnerItemOut] = []
    passed = 0
    failed = 0

    for req in requests:
        out = request_to_out(req)
        send_in = ProxySendIn(
            workspace_id=payload.workspace_id,
            request_id=req.id,
            protocol=out.protocol,
            method=out.method,
            url=out.url,
            headers=out.headers,
            params=out.params,
            body=out.body,
            body_type=out.body_type,
            pre_request_script=out.pre_request_script,
            test_script=out.test_script,
            graphql_query=out.graphql_query,
            graphql_variables=out.graphql_variables,
            grpc_service=out.grpc_service,
            grpc_method=out.grpc_method,
            grpc_message=out.grpc_message,
            ws_messages=out.ws_messages,
            environment_id=payload.environment_id,
        )
        result = await execute_request(send_in, env_vars)
        if result.env_updates:
            env_vars = result.env_updates
            if env:
                env.variables_json = dumps_kv(env_vars)

        ok = result.error is None and assertions_passed(result.assertions)
        if result.status_code is not None and result.status_code >= 400 and not result.assertions:
            ok = False
        if ok:
            passed += 1
        else:
            failed += 1

        if user_id is not None:
            db.add(
                RequestHistory(
                    workspace_id=payload.workspace_id,
                    request_id=req.id,
                    user_id=user_id,
                    method=out.method,
                    url=out.url,
                    status_code=result.status_code,
                    duration_ms=result.duration_ms,
                    assertions_json=json.dumps([a.model_dump() for a in result.assertions]),
                    source=source,
                )
            )

        items.append(
            RunnerItemOut(
                request_id=req.id,
                name=out.name,
                status_code=result.status_code,
                duration_ms=result.duration_ms,
                error=result.error,
                assertions=result.assertions,
                passed=ok,
            )
        )
        if not ok and payload.stop_on_failure:
            break

    status = "pass" if failed == 0 else "fail"
    run = RunResult(
        workspace_id=payload.workspace_id,
        collection_id=col.id,
        monitor_id=monitor_id,
        user_id=user_id,
        source=source,
        status=status,
        summary_json=json.dumps(
            {
                "total": len(items),
                "passed": passed,
                "failed": failed,
                "items": [i.model_dump() for i in items],
            }
        ),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return RunnerOut(
        run_id=run.id,
        status=status,
        total=len(items),
        passed=passed,
        failed=failed,
        items=items,
    )
