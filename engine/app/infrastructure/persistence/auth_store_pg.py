"""PostgreSQL user store with hashed passwords."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, Text, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.application.platform.passwords import hash_password, needs_rehash, verify_password
from app.domain.errors import AgentEngineError
from app.domain.platform import Principal
from app.infrastructure.config.database import (
    create_engine_from_url,
    primary_database_url,
)


class AuthBase(DeclarativeBase):
    pass


class AuthUserRow(AuthBase):
    __tablename__ = "auth_users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    principal_type: Mapped[str] = mapped_column(String(32), default="user")
    display_name: Mapped[str] = mapped_column(String(128))
    workspace_roles: Mapped[list[str]] = mapped_column(JSONB, default=list)
    group_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    password_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _utc_now() -> datetime:
    return datetime.now(UTC)


class PostgresAuthStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        AuthBase.metadata.create_all(self.engine)
        self._factory = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)

    def _session(self) -> Session:
        return self._factory()

    def create_user(
        self,
        *,
        username: str,
        password: str,
        tenant_id: str,
        principal_id: str | None = None,
        display_name: str | None = None,
        workspace_roles: list[str] | None = None,
        group_ids: list[str] | None = None,
        principal_type: str = "user",
    ) -> dict[str, object]:
        password_hash = hash_password(password)
        now = _utc_now()
        user_id = principal_id or f"u_{uuid4().hex[:12]}"
        with self._session() as db:
            existing = db.scalar(
                select(AuthUserRow).where(AuthUserRow.username == username)
            )
            if existing is not None:
                raise AgentEngineError(
                    "USER_ALREADY_EXISTS", f"Username already exists: {username}"
                )
            row = AuthUserRow(
                user_id=user_id,
                username=username,
                password_hash=password_hash,
                tenant_id=tenant_id,
                principal_type=principal_type,
                display_name=display_name or username,
                workspace_roles=workspace_roles or [],
                group_ids=group_ids or [],
                is_active=True,
                password_updated_at=now,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.commit()
            return self._profile(row)

    def authenticate(self, username: str, password: str) -> dict[str, object]:
        with self._session() as db:
            row = db.scalar(select(AuthUserRow).where(AuthUserRow.username == username))
            if row is None or not row.is_active:
                raise AgentEngineError("INVALID_CREDENTIALS", "用户名或密码错误")
            if not verify_password(password, row.password_hash):
                raise AgentEngineError("INVALID_CREDENTIALS", "用户名或密码错误")
            if needs_rehash(row.password_hash):
                row.password_hash = hash_password(password)
                row.updated_at = _utc_now()
                db.commit()
            return self._profile(row)

    def get_by_username(self, username: str) -> dict[str, object] | None:
        with self._session() as db:
            row = db.scalar(select(AuthUserRow).where(AuthUserRow.username == username))
            return None if row is None else self._profile(row)

    def get_by_user_id(self, user_id: str) -> dict[str, object] | None:
        with self._session() as db:
            row = db.get(AuthUserRow, user_id)
            return None if row is None else self._profile(row)

    def list_users(self, tenant_id: str | None = None) -> list[dict[str, object]]:
        with self._session() as db:
            stmt = select(AuthUserRow)
            if tenant_id:
                stmt = stmt.where(AuthUserRow.tenant_id == tenant_id)
            rows = db.scalars(stmt).all()
            return [self._profile(r) for r in rows]

    def change_password(
        self,
        *,
        username: str,
        old_password: str,
        new_password: str,
    ) -> None:
        with self._session() as db:
            row = db.scalar(select(AuthUserRow).where(AuthUserRow.username == username))
            if row is None or not row.is_active:
                raise AgentEngineError("INVALID_CREDENTIALS", "用户名或密码错误")
            if not verify_password(old_password, row.password_hash):
                raise AgentEngineError("INVALID_CREDENTIALS", "原密码不正确")
            if verify_password(new_password, row.password_hash):
                raise AgentEngineError(
                    "PASSWORD_UNCHANGED", "新密码不能与当前密码相同"
                )
            try:
                row.password_hash = hash_password(new_password)
            except ValueError as exc:
                raise AgentEngineError("PASSWORD_INVALID", str(exc)) from exc
            now = _utc_now()
            row.password_updated_at = now
            row.updated_at = now
            db.commit()

    def set_active(self, username: str, active: bool) -> None:
        with self._session() as db:
            row = db.scalar(select(AuthUserRow).where(AuthUserRow.username == username))
            if row is None:
                raise AgentEngineError("USER_NOT_FOUND", f"User not found: {username}")
            row.is_active = active
            row.updated_at = _utc_now()
            db.commit()

    def to_principal(self, profile: dict[str, object]) -> Principal:
        roles = profile.get("workspace_roles") or []
        groups = profile.get("group_ids") or []
        return Principal(
            tenant_id=str(profile["tenant_id"]),
            principal_id=str(profile["user_id"]),
            principal_type=str(profile.get("principal_type") or "user"),  # type: ignore[arg-type]
            display_name=str(profile.get("display_name") or ""),
            workspace_roles=[str(r) for r in roles] if isinstance(roles, list) else [],
            group_ids=[str(g) for g in groups] if isinstance(groups, list) else [],
        )

    @staticmethod
    def _profile(row: AuthUserRow) -> dict[str, object]:
        return {
            "user_id": row.user_id,
            "username": row.username,
            "tenant_id": row.tenant_id,
            "principal_type": row.principal_type,
            "display_name": row.display_name,
            "workspace_roles": list(row.workspace_roles or []),
            "group_ids": list(row.group_ids or []),
            "is_active": row.is_active,
            "password_updated_at": row.password_updated_at.isoformat(),
            "created_at": row.created_at.isoformat(),
        }


def create_auth_store(database_url: str | None = None) -> PostgresAuthStore | None:
    url = database_url or primary_database_url()
    if not url:
        return None
    return PostgresAuthStore(create_engine_from_url(url))
