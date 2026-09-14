"""Application ports."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain import IdentityLink, User


@runtime_checkable
class UserRepositoryPort(Protocol):
    def create_user(self, user: User) -> User:
        ...

    def get_by_username(self, username: str) -> User | None:
        ...

    def list_users(self, tenant_id: str | None = None) -> list[User]:
        ...

    def save_user(self, user: User) -> User:
        ...


@runtime_checkable
class IdentityLinkRepositoryPort(Protocol):
    def upsert(self, link: IdentityLink) -> IdentityLink:
        ...


@runtime_checkable
class TokenSignerPort(Protocol):
    def issue(self, principal: dict[str, object]) -> str:
        ...

    def parse(self, token: str) -> dict[str, object] | None:
        ...
