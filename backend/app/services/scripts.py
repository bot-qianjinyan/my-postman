from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from app.schemas import AssertionResult


@dataclass
class ScriptResponse:
    code: int | None
    headers: dict[str, str]
    body: str
    json_data: Any = None

    def json(self) -> Any:
        if self.json_data is not None:
            return self.json_data
        try:
            return json.loads(self.body or "null")
        except Exception:
            return None


@dataclass
class ScriptEnv:
    values: dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: str = "") -> str:
        return self.values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.values[key] = str(value)

    def unset(self, key: str) -> None:
        self.values.pop(key, None)


@dataclass
class Expectation:
    actual: Any

    def to_equal(self, expected: Any) -> None:
        if self.actual != expected:
            raise AssertionError(f"expected {expected!r}, got {self.actual!r}")

    def to_be_truthy(self) -> None:
        if not self.actual:
            raise AssertionError(f"expected truthy, got {self.actual!r}")

    def to_include(self, expected: Any) -> None:
        if expected not in self.actual:
            raise AssertionError(f"expected {self.actual!r} to include {expected!r}")


class PM:
    def __init__(self, env: ScriptEnv, response: ScriptResponse | None = None) -> None:
        self.environment = env
        self.response = response or ScriptResponse(code=None, headers={}, body="")
        self.assertions: list[AssertionResult] = []

    def test(self, name: str, fn: Callable[[], Any]) -> None:
        try:
            fn()
            self.assertions.append(AssertionResult(name=name, passed=True))
        except Exception as exc:
            self.assertions.append(AssertionResult(name=name, passed=False, error=str(exc)))

    def expect(self, actual: Any) -> Expectation:
        return Expectation(actual)


def run_script(
    script: str,
    env: ScriptEnv,
    response: ScriptResponse | None = None,
) -> tuple[ScriptEnv, list[AssertionResult]]:
    if not (script or "").strip():
        return env, []

    pm = PM(env=env, response=response)
    # Python sandbox with Postman-like pm API
    safe_globals = {
        "__builtins__": {
            "True": True,
            "False": False,
            "None": None,
            "str": str,
            "int": int,
            "float": float,
            "len": len,
            "print": print,
            "json": json,
            "dict": dict,
            "list": list,
            "range": range,
            "isinstance": isinstance,
            "Exception": Exception,
            "AssertionError": AssertionError,
        },
        "pm": pm,
        "json": json,
    }
    try:
        exec(script, safe_globals, {})  # noqa: S102 - intentional sandbox for user scripts
    except Exception as exc:
        pm.assertions.append(
            AssertionResult(name="script_error", passed=False, error=str(exc))
        )
    return env, pm.assertions
