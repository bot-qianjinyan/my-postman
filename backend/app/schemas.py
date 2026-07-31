from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class WorkspaceJoin(BaseModel):
    invite_code: str = Field(min_length=4, max_length=32)


class MemberOut(BaseModel):
    user_id: int
    name: str
    email: EmailStr
    role: str


class WorkspaceOut(BaseModel):
    id: int
    name: str
    invite_code: str
    role: str
    created_at: datetime | None = None


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class CollectionOut(BaseModel):
    id: int
    workspace_id: int
    name: str
    description: str = ""

    model_config = {"from_attributes": True}


class KeyValue(BaseModel):
    key: str = ""
    value: str = ""
    enabled: bool = True


class RequestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    method: str = "GET"
    url: str = ""
    protocol: str = "http"


class RequestUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    protocol: str | None = None
    method: str | None = None
    url: str | None = None
    headers: list[KeyValue] | None = None
    params: list[KeyValue] | None = None
    body_type: str | None = None
    body: str | None = None
    auth_type: str | None = None
    auth: dict | None = None
    pre_request_script: str | None = None
    test_script: str | None = None
    graphql_query: str | None = None
    graphql_variables: str | None = None
    grpc_service: str | None = None
    grpc_method: str | None = None
    grpc_message: str | None = None
    ws_messages: list[str] | None = None
    version: int | None = None


class AssertionResult(BaseModel):
    name: str
    passed: bool
    error: str | None = None


class RequestOut(BaseModel):
    id: int
    collection_id: int
    name: str
    description: str = ""
    protocol: str = "http"
    method: str
    url: str
    headers: list[KeyValue]
    params: list[KeyValue]
    body_type: str
    body: str
    auth_type: str
    auth: dict
    pre_request_script: str = ""
    test_script: str = ""
    graphql_query: str = ""
    graphql_variables: str = "{}"
    grpc_service: str = ""
    grpc_method: str = ""
    grpc_message: str = "{}"
    ws_messages: list[str] = Field(default_factory=list)
    version: int
    updated_by: int | None = None
    updated_at: datetime | None = None


class EnvironmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    variables: list[KeyValue] = Field(default_factory=list)


class EnvironmentUpdate(BaseModel):
    name: str | None = None
    variables: list[KeyValue] | None = None
    is_active: bool | None = None


class EnvironmentOut(BaseModel):
    id: int
    workspace_id: int
    name: str
    variables: list[KeyValue]
    is_active: bool


class ProxySendIn(BaseModel):
    workspace_id: int
    request_id: int | None = None
    protocol: str = "http"
    method: str = "GET"
    url: str
    headers: list[KeyValue] = Field(default_factory=list)
    params: list[KeyValue] = Field(default_factory=list)
    body: str | None = None
    body_type: str = "none"
    pre_request_script: str = ""
    test_script: str = ""
    graphql_query: str = ""
    graphql_variables: str = "{}"
    grpc_service: str = ""
    grpc_method: str = ""
    grpc_message: str = "{}"
    ws_messages: list[str] = Field(default_factory=list)
    environment_id: int | None = None
    timeout: float = 30.0


class ProxySendOut(BaseModel):
    status_code: int | None
    headers: dict[str, str]
    body: str
    duration_ms: int
    error: str | None = None
    assertions: list[AssertionResult] = Field(default_factory=list)
    env_updates: list[KeyValue] = Field(default_factory=list)


class RunnerIn(BaseModel):
    workspace_id: int
    collection_id: int
    environment_id: int | None = None
    stop_on_failure: bool = False


class RunnerItemOut(BaseModel):
    request_id: int
    name: str
    status_code: int | None
    duration_ms: int
    error: str | None = None
    assertions: list[AssertionResult] = Field(default_factory=list)
    passed: bool


class RunnerOut(BaseModel):
    run_id: int
    status: str
    total: int
    passed: int
    failed: int
    items: list[RunnerItemOut]


class OpenAPIImportIn(BaseModel):
    workspace_id: int
    content: str
    collection_name: str | None = None


class OpenAPIImportOut(BaseModel):
    collection: CollectionOut
    imported_count: int


class MockServerCreate(BaseModel):
    name: str
    routes: list[dict[str, Any]] = Field(default_factory=list)


class MockRouteOut(BaseModel):
    id: int
    method: str
    path: str
    status_code: int
    headers: dict[str, str]
    body: str
    delay_ms: int


class MockServerOut(BaseModel):
    id: int
    workspace_id: int
    name: str
    slug: str
    is_enabled: bool
    base_url: str
    routes: list[MockRouteOut]


class CommentCreate(BaseModel):
    body: str = Field(min_length=1)
    request_id: int | None = None


class CommentOut(BaseModel):
    id: int
    workspace_id: int
    request_id: int | None
    user_id: int
    user_name: str
    body: str
    mentions: list[int]
    created_at: datetime | None = None


class MonitorCreate(BaseModel):
    name: str
    collection_id: int
    environment_id: int | None = None
    interval_minutes: int = 5


class MonitorUpdate(BaseModel):
    name: str | None = None
    interval_minutes: int | None = None
    is_enabled: bool | None = None
    environment_id: int | None = None


class MonitorOut(BaseModel):
    id: int
    workspace_id: int
    collection_id: int
    environment_id: int | None
    name: str
    interval_minutes: int
    is_enabled: bool
    last_run_at: datetime | None
    last_status: str
    last_summary: str


class DocsOut(BaseModel):
    workspace_id: int
    title: str
    markdown: str
    html: str
