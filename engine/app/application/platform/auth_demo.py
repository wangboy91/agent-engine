"""Demo auth for 1.0.1 testing. Not for production (plain passwords, dev tokens)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

from app.domain.platform import Principal

# Shared secret only signs demo tokens; rotate freely in local env.
_DEV_TOKEN_SECRET = b"agent-engine-1.0.1-demo"


class DemoUser:
    def __init__(
        self,
        username: str,
        password: str,
        *,
        tenant_id: str,
        principal_id: str,
        display_name: str,
        workspace_roles: list[str],
        group_ids: list[str] | None = None,
        principal_type: str = "user",
        description: str = "",
    ) -> None:
        self.username = username
        self.password = password
        self.tenant_id = tenant_id
        self.principal_id = principal_id
        self.display_name = display_name
        self.workspace_roles = workspace_roles
        self.group_ids = group_ids or []
        self.principal_type = principal_type
        self.description = description

    def to_principal(self) -> Principal:
        return Principal(
            tenant_id=self.tenant_id,
            principal_id=self.principal_id,
            principal_type=self.principal_type,  # type: ignore[arg-type]
            display_name=self.display_name,
            workspace_roles=list(self.workspace_roles),
            group_ids=list(self.group_ids),
        )

    def public_profile(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "tenant_id": self.tenant_id,
            "principal_id": self.principal_id,
            "display_name": self.display_name,
            "workspace_roles": self.workspace_roles,
            "group_ids": self.group_ids,
            "principal_type": self.principal_type,
            "description": self.description,
        }


DEMO_USERS: list[DemoUser] = [
    DemoUser(
        "platform.admin",
        "Platform@123",
        tenant_id="t-demo",
        principal_id="u_platform_admin",
        display_name="韩启",
        workspace_roles=["platform_admin"],
        principal_type="platform_operator",
        description="平台管理员：租户/全局治理，默认不读用户正文",
    ),
    DemoUser(
        "tenant.admin",
        "Tenant@123",
        tenant_id="t-demo",
        principal_id="u_tenant_admin",
        display_name="沈舟",
        workspace_roles=["tenant_admin", "ws_admin"],
        description="企业管理员：成员、审计、定制开关",
    ),
    DemoUser(
        "ws.admin",
        "WsAdmin@123",
        tenant_id="t-demo",
        principal_id="u_ws_admin",
        display_name="赵安",
        workspace_roles=["ws_admin"],
        description="空间管理员：Identity 配置、发布、授权、审批",
    ),
    DemoUser(
        "dev.lin",
        "Dev@12345",
        tenant_id="t-demo",
        principal_id="u_dev",
        display_name="林晓晴",
        workspace_roles=["developer"],
        description="智能体开发者：草稿与调试，无正式发布权",
    ),
    DemoUser(
        "ops.li",
        "Ops@12345",
        tenant_id="t-demo",
        principal_id="u_ops",
        display_name="李衡",
        workspace_roles=["operator"],
        group_ids=["all-staff"],
        description="业务运营：运行摘要与审批",
    ),
    DemoUser(
        "audit.zhou",
        "Audit@123",
        tenant_id="t-demo",
        principal_id="u_auditor",
        display_name="周谨",
        workspace_roles=["auditor"],
        description="审计员：只读变更与访问审计",
    ),
    DemoUser(
        "user.gu",
        "User@123",
        tenant_id="t-demo",
        principal_id="u_alice",
        display_name="顾南",
        workspace_roles=["end_user"],
        group_ids=["all-staff"],
        description="企业员工：仅本人会话/任务/产物",
    ),
    DemoUser(
        "user.ye",
        "User@123",
        tenant_id="t-demo",
        principal_id="u_bob",
        display_name="叶清",
        workspace_roles=["end_user"],
        group_ids=["all-staff"],
        description="另一名员工：用于双用户串线测试",
    ),
]

_USERS_BY_NAME = {u.username: u for u in DEMO_USERS}


def find_demo_user(username: str) -> DemoUser | None:
    return _USERS_BY_NAME.get(username)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _sign(payload: bytes) -> str:
    return _b64url(hmac.new(_DEV_TOKEN_SECRET, payload, hashlib.sha256).digest())


def issue_dev_token(principal: Principal) -> str:
    payload = _b64url(principal.model_dump_json().encode("utf-8"))
    return f"dev.{payload}.{_sign(payload.encode('ascii'))}"


def parse_dev_token(token: str) -> Principal | None:
    if not token.startswith("dev."):
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    _, payload, sig = parts
    expected = _sign(payload.encode("ascii"))
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        raw = _b64url_decode(payload)
        return Principal.model_validate(json.loads(raw.decode("utf-8")))
    except Exception:  # noqa: BLE001
        return None


def authenticate(username: str, password: str) -> DemoUser | None:
    user = find_demo_user(username)
    if user is None:
        return None
    if not hmac.compare_digest(user.password, password):
        return None
    return user
