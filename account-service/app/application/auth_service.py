"""Auth use cases — depend only on ports + domain."""

from __future__ import annotations

from typing import Any

from app.application.ports import IdentityLinkRepositoryPort, TokenSignerPort, UserRepositoryPort
from app.domain import (
    AccountError,
    IdentityLink,
    User,
    can_manage_users,
    list_tenant_scope,
    new_link_id,
    new_user_id,
    utc_now,
)
from app.domain.passwords import hash_password, needs_rehash, verify_password


class AuthService:
    def __init__(
        self,
        users: UserRepositoryPort,
        links: IdentityLinkRepositoryPort | None = None,
        tokens: TokenSignerPort | None = None,
    ) -> None:
        self._users = users
        self._links = links
        self._tokens = tokens

    def login(self, username: str, password: str) -> dict[str, Any]:
        user = self._users.get_by_username(username)
        if user is None or not user.is_active:
            raise AccountError("INVALID_CREDENTIALS", "用户名或密码错误")
        if not verify_password(password, user.password_hash):
            raise AccountError("INVALID_CREDENTIALS", "用户名或密码错误")
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
            user.updated_at = utc_now()
            self._users.save_user(user)
        principal = user.to_principal()
        token = self._tokens.issue(principal) if self._tokens else ""
        return {
            "token_type": "Bearer",
            "access_token": token,
            "principal": principal,
            "profile": user.public_profile(),
        }

    def change_password(
        self, *, username: str, old_password: str, new_password: str
    ) -> None:
        user = self._users.get_by_username(username)
        if user is None or not user.is_active:
            raise AccountError("INVALID_CREDENTIALS", "用户名或密码错误")
        if not verify_password(old_password, user.password_hash):
            raise AccountError("INVALID_CREDENTIALS", "原密码不正确")
        if verify_password(new_password, user.password_hash):
            raise AccountError("PASSWORD_UNCHANGED", "新密码不能与当前密码相同")
        try:
            user.password_hash = hash_password(new_password)
        except ValueError as exc:
            raise AccountError("PASSWORD_INVALID", str(exc)) from exc
        now = utc_now()
        user.password_updated_at = now
        user.updated_at = now
        self._users.save_user(user)

    def list_users_for(self, principal: dict[str, Any]) -> list[dict[str, Any]]:
        tenant = list_tenant_scope(principal)
        return [u.public_profile() for u in self._users.list_users(tenant)]

    def create_user(
        self,
        *,
        actor: dict[str, Any],
        username: str,
        password: str,
        tenant_id: str,
        principal_id: str | None = None,
        display_name: str | None = None,
        workspace_roles: list[str] | None = None,
        group_ids: list[str] | None = None,
        principal_type: str = "user",
    ) -> dict[str, Any]:
        if not can_manage_users(actor):
            raise AccountError("FORBIDDEN", "Not allowed to create users")
        try:
            password_hash = hash_password(password)
        except ValueError as exc:
            raise AccountError("PASSWORD_INVALID", str(exc)) from exc
        if self._users.get_by_username(username) is not None:
            raise AccountError("USER_ALREADY_EXISTS", f"Username already exists: {username}")
        user = User(
            user_id=principal_id or new_user_id(),
            username=username,
            password_hash=password_hash,
            tenant_id=tenant_id,
            display_name=display_name or username,
            workspace_roles=workspace_roles or [],
            group_ids=group_ids or [],
            principal_type=principal_type,  # type: ignore[arg-type]
        )
        saved = self._users.create_user(user)
        return saved.public_profile()

    def upsert_link(
        self,
        *,
        actor: dict[str, Any],
        external_system: str,
        external_user_id: str,
        tenant_id: str,
        principal_id: str,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        if not can_manage_users(actor):
            raise AccountError("FORBIDDEN", "Not allowed")
        if self._links is None:
            raise AccountError("NOT_CONFIGURED", "identity links repository missing")
        link = IdentityLink(
            link_id=new_link_id(),
            external_system=external_system,
            external_user_id=external_user_id,
            tenant_id=tenant_id,
            principal_id=principal_id,
            display_name=display_name,
        )
        saved = self._links.upsert(link)
        return {
            "link_id": saved.link_id,
            "external_system": saved.external_system,
            "external_user_id": saved.external_user_id,
            "tenant_id": saved.tenant_id,
            "principal_id": saved.principal_id,
            "display_name": saved.display_name,
            "is_active": saved.is_active,
        }

    def parse_token(self, token: str) -> dict[str, Any]:
        if self._tokens is None:
            raise AccountError("NOT_CONFIGURED", "token signer missing")
        principal = self._tokens.parse(token)
        if principal is None:
            raise AccountError("UNAUTHORIZED", "Invalid token")
        return principal
