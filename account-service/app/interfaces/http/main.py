"""HTTP entry — FastAPI routes call AuthService only."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.application.auth_service import AuthService
from app.domain import AccountError
from app.infrastructure.config import default_port
from app.infrastructure.db import init_db, make_engine, make_session_factory
from app.infrastructure.repositories import SqlIdentityLinkRepository, SqlUserRepository
from app.infrastructure.token_signer import HmacTokenSigner

app = FastAPI(
    title="Agent Account Service",
    version="1.0.1",
    description="独立账号权限服务：登录、用户、账号映射。DDD 分层，智能体调度不在本服务。",
)

_engine = make_engine()
init_db(_engine)
_sessions = make_session_factory(_engine)
_service = AuthService(
    users=SqlUserRepository(_sessions),
    links=SqlIdentityLinkRepository(_sessions),
    tokens=HmacTokenSigner(),
)


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    username: str
    old_password: str
    new_password: str = Field(min_length=8)


class CreateUserRequest(BaseModel):
    username: str
    password: str = Field(min_length=8)
    tenant_id: str
    principal_id: str | None = None
    display_name: str | None = None
    workspace_roles: list[str] = Field(default_factory=list)
    group_ids: list[str] = Field(default_factory=list)
    principal_type: str = "user"


class IdentityLinkRequest(BaseModel):
    external_system: str
    external_user_id: str
    tenant_id: str
    principal_id: str
    display_name: str | None = None


def _http(exc: AccountError) -> HTTPException:
    mapping = {
        "INVALID_CREDENTIALS": 401,
        "UNAUTHORIZED": 401,
        "FORBIDDEN": 403,
        "USER_ALREADY_EXISTS": 400,
        "PASSWORD_UNCHANGED": 400,
        "PASSWORD_INVALID": 400,
        "NOT_CONFIGURED": 503,
    }
    return HTTPException(
        status_code=mapping.get(exc.code, 400),
        detail={"code": exc.code, "message": exc.message},
    )


def get_principal(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    token = authorization.split(" ", 1)[1].strip()
    try:
        return _service.parse_token(token)
    except AccountError as exc:
        raise _http(exc) from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "account"}


@app.post("/auth/login")
def login(request: LoginRequest) -> dict[str, Any]:
    try:
        return _service.login(request.username, request.password)
    except AccountError as exc:
        raise _http(exc) from exc


@app.post("/auth/change-password")
def change_password(request: ChangePasswordRequest) -> dict[str, str]:
    try:
        _service.change_password(
            username=request.username,
            old_password=request.old_password,
            new_password=request.new_password,
        )
    except AccountError as exc:
        raise _http(exc) from exc
    return {"status": "ok", "message": "密码已更新"}


@app.get("/auth/me")
def me(principal: dict[str, Any] = Depends(get_principal)) -> dict[str, Any]:
    return principal


@app.get("/auth/users")
def list_users(principal: dict[str, Any] = Depends(get_principal)) -> list[dict[str, Any]]:
    try:
        return _service.list_users_for(principal)
    except AccountError as exc:
        raise _http(exc) from exc


@app.post("/auth/users", status_code=201)
def create_user(
    request: CreateUserRequest,
    principal: dict[str, Any] = Depends(get_principal),
) -> dict[str, Any]:
    try:
        return _service.create_user(
            actor=principal,
            username=request.username,
            password=request.password,
            tenant_id=request.tenant_id,
            principal_id=request.principal_id,
            display_name=request.display_name,
            workspace_roles=request.workspace_roles,
            group_ids=request.group_ids,
            principal_type=request.principal_type,
        )
    except AccountError as exc:
        raise _http(exc) from exc


@app.post("/auth/identity-links")
def upsert_link(
    request: IdentityLinkRequest,
    principal: dict[str, Any] = Depends(get_principal),
) -> dict[str, Any]:
    try:
        return _service.upsert_link(
            actor=principal,
            external_system=request.external_system,
            external_user_id=request.external_user_id,
            tenant_id=request.tenant_id,
            principal_id=request.principal_id,
            display_name=request.display_name,
        )
    except AccountError as exc:
        raise _http(exc) from exc


def run() -> None:
    import uvicorn

    uvicorn.run("app.interfaces.http.main:app", host="127.0.0.1", port=default_port(), reload=False)


if __name__ == "__main__":
    run()
