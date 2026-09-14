"""Account domain: principals, errors, password policy (pure)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

PrincipalType = Literal["user", "service_account", "platform_operator"]


class AccountError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def utc_now() -> datetime:
    return datetime.now(UTC)


class User:
    """Domain user (no persistence details)."""

    def __init__(
        self,
        *,
        user_id: str,
        username: str,
        password_hash: str,
        tenant_id: str,
        display_name: str,
        workspace_roles: list[str],
        group_ids: list[str],
        principal_type: PrincipalType = "user",
        is_active: bool = True,
        password_updated_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.user_id = user_id
        self.username = username
        self.password_hash = password_hash
        self.tenant_id = tenant_id
        self.display_name = display_name
        self.workspace_roles = workspace_roles
        self.group_ids = group_ids
        self.principal_type = principal_type
        self.is_active = is_active
        self.password_updated_at = password_updated_at or utc_now()
        self.created_at = created_at or utc_now()
        self.updated_at = updated_at or utc_now()

    def to_principal(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "principal_id": self.user_id,
            "principal_type": self.principal_type,
            "display_name": self.display_name,
            "workspace_roles": list(self.workspace_roles),
            "group_ids": list(self.group_ids),
            "scopes": [],
            "auth_session_id": None,
        }

    def public_profile(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "tenant_id": self.tenant_id,
            "principal_type": self.principal_type,
            "display_name": self.display_name,
            "workspace_roles": list(self.workspace_roles),
            "group_ids": list(self.group_ids),
            "is_active": self.is_active,
            "password_updated_at": self.password_updated_at.isoformat(),
            "created_at": self.created_at.isoformat(),
        }


class IdentityLink:
    def __init__(
        self,
        *,
        link_id: str,
        external_system: str,
        external_user_id: str,
        tenant_id: str,
        principal_id: str,
        display_name: str | None = None,
        is_active: bool = True,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.link_id = link_id
        self.external_system = external_system
        self.external_user_id = external_user_id
        self.tenant_id = tenant_id
        self.principal_id = principal_id
        self.display_name = display_name
        self.is_active = is_active
        self.created_at = created_at or utc_now()
        self.updated_at = updated_at or utc_now()


def new_user_id() -> str:
    return f"u_{uuid4().hex[:12]}"


def new_link_id() -> str:
    return f"lnk_{uuid4().hex[:12]}"


def can_manage_users(principal: dict[str, Any]) -> bool:
    roles = principal.get("workspace_roles") or []
    return (
        principal.get("principal_type") == "platform_operator"
        or "platform_admin" in roles
        or "tenant_admin" in roles
    )


def list_tenant_scope(principal: dict[str, Any]) -> str | None:
    """None means all tenants (platform)."""
    roles = principal.get("workspace_roles") or []
    if principal.get("principal_type") == "platform_operator" or "platform_admin" in roles:
        return None
    return str(principal.get("tenant_id") or "")
