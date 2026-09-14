"""Persistence models (SQLAlchemy)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AuthUserRow(Base):
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


class IdentityLinkRow(Base):
    __tablename__ = "identity_links"

    link_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    external_system: Mapped[str] = mapped_column(String(64), index=True)
    external_user_id: Mapped[str] = mapped_column(String(128), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    principal_id: Mapped[str] = mapped_column(String(64), index=True)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
