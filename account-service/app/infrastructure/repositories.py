"""SQLAlchemy repositories implementing application ports."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.domain import IdentityLink, User, utc_now
from app.infrastructure.models import AuthUserRow, IdentityLinkRow


def _user_from_row(row: AuthUserRow) -> User:
    return User(
        user_id=row.user_id,
        username=row.username,
        password_hash=row.password_hash,
        tenant_id=row.tenant_id,
        display_name=row.display_name,
        workspace_roles=list(row.workspace_roles or []),
        group_ids=list(row.group_ids or []),
        principal_type=row.principal_type,  # type: ignore[arg-type]
        is_active=row.is_active,
        password_updated_at=row.password_updated_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _row_from_user(user: User) -> AuthUserRow:
    return AuthUserRow(
        user_id=user.user_id,
        username=user.username,
        password_hash=user.password_hash,
        tenant_id=user.tenant_id,
        principal_type=user.principal_type,
        display_name=user.display_name,
        workspace_roles=user.workspace_roles,
        group_ids=user.group_ids,
        is_active=user.is_active,
        password_updated_at=user.password_updated_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


class SqlUserRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def create_user(self, user: User) -> User:
        with self._session() as db:
            db.add(_row_from_user(user))
            db.commit()
            return user

    def get_by_username(self, username: str) -> User | None:
        with self._session() as db:
            row = db.scalar(select(AuthUserRow).where(AuthUserRow.username == username))
            return None if row is None else _user_from_row(row)

    def list_users(self, tenant_id: str | None = None) -> list[User]:
        with self._session() as db:
            stmt = select(AuthUserRow)
            if tenant_id:
                stmt = stmt.where(AuthUserRow.tenant_id == tenant_id)
            return [_user_from_row(r) for r in db.scalars(stmt).all()]

    def save_user(self, user: User) -> User:
        with self._session() as db:
            row = db.get(AuthUserRow, user.user_id)
            if row is None:
                db.add(_row_from_user(user))
            else:
                row.password_hash = user.password_hash
                row.display_name = user.display_name
                row.workspace_roles = user.workspace_roles
                row.group_ids = user.group_ids
                row.is_active = user.is_active
                row.password_updated_at = user.password_updated_at
                row.updated_at = user.updated_at
            db.commit()
            return user

    def _session(self):
        return self._sessions()


class SqlIdentityLinkRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def upsert(self, link: IdentityLink) -> IdentityLink:
        with self._sessions() as db:
            row = db.scalar(
                select(IdentityLinkRow).where(
                    IdentityLinkRow.external_system == link.external_system,
                    IdentityLinkRow.external_user_id == link.external_user_id,
                    IdentityLinkRow.tenant_id == link.tenant_id,
                )
            )
            now = utc_now()
            if row is None:
                row = IdentityLinkRow(
                    link_id=link.link_id,
                    external_system=link.external_system,
                    external_user_id=link.external_user_id,
                    tenant_id=link.tenant_id,
                    principal_id=link.principal_id,
                    display_name=link.display_name,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
                db.add(row)
            else:
                row.principal_id = link.principal_id
                if link.display_name is not None:
                    row.display_name = link.display_name
                row.updated_at = now
            db.commit()
            link.link_id = row.link_id
            link.updated_at = row.updated_at
            return link
