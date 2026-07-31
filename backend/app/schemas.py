from __future__ import annotations

from datetime import datetime

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


class CollectionOut(BaseModel):
    id: int
    workspace_id: int
    name: str

    model_config = {"from_attributes": True}


class KeyValue(BaseModel):
    key: str = ""
    value: str = ""
    enabled: bool = True


class RequestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    method: str = "GET"
    url: str = ""


class RequestUpdate(BaseModel):
    name: str | None = None
    method: str | None = None
    url: str | None = None
    headers: list[KeyValue] | None = None
    params: list[KeyValue] | None = None
    body_type: str | None = None
    body: str | None = None
    auth_type: str | None = None
    auth: dict | None = None
    version: int | None = None


class RequestOut(BaseModel):
    id: int
    collection_id: int
    name: str
    method: str
    url: str
    headers: list[KeyValue]
    params: list[KeyValue]
    body_type: str
    body: str
    auth_type: str
    auth: dict
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
    method: str = "GET"
    url: str
    headers: list[KeyValue] = Field(default_factory=list)
    params: list[KeyValue] = Field(default_factory=list)
    body: str | None = None
    body_type: str = "none"
    timeout: float = 30.0


class ProxySendOut(BaseModel):
    status_code: int | None
    headers: dict[str, str]
    body: str
    duration_ms: int
    error: str | None = None
