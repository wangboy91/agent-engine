"""PostgreSQL adapter for the platform registry (1.0.1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.domain.errors import AgentEngineError
from app.domain.platform import (
    ArtifactElevation,
    ArtifactMeta,
    AuditEvent,
    IdentityDefinition,
    IdentityGrant,
    IdentityVersion,
    Tenant,
    TenantFeatures,
    TenantWorkspace,
    can_grant_version,
    ensure_version_mutable,
    normalize_logical_path,
)


class Base(DeclarativeBase):
    pass


class TenantRow(Base):
    __tablename__ = "platform_tenants"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active")
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkspaceRow(Base):
    __tablename__ = "platform_tenant_workspaces"

    tenant_workspace_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("platform_tenants.tenant_id"), index=True
    )
    workspace_key: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(255))
    blueprint_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    environment: Mapped[str] = mapped_column(String(32), default="dev")
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IdentityDefinitionRow(Base):
    __tablename__ = "platform_identity_definitions"

    definition_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    tenant_workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    key: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IdentityVersionRow(Base):
    __tablename__ = "platform_identity_versions"

    version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    definition_id: Mapped[str] = mapped_column(String(64), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    tenant_workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IdentityGrantRow(Base):
    __tablename__ = "platform_identity_grants"

    grant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    tenant_workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    identity_version_id: Mapped[str] = mapped_column(String(64), index=True)
    grantee_type: Mapped[str] = mapped_column(String(32))
    grantee_id: Mapped[str] = mapped_column(String(128), index=True)
    granted_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ArtifactRow(Base):
    __tablename__ = "platform_artifacts"

    artifact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    tenant_workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    owner_principal_id: Mapped[str] = mapped_column(String(128), index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    identity_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    logical_path: Mapped[str] = mapped_column(Text)
    object_key: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ElevationRow(Base):
    __tablename__ = "platform_artifact_elevations"

    elevation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    tenant_workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    actor_principal_id: Mapped[str] = mapped_column(String(128), index=True)
    owner_principal_id: Mapped[str] = mapped_column(String(128), index=True)
    path_prefix: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditRow(Base):
    __tablename__ = "platform_audit_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    actor_principal_id: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(128))
    target: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str] = mapped_column(String(32), default="ok")
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _utc_now() -> datetime:
    return datetime.now(UTC)


def default_database_url() -> str | None:
    from app.infrastructure.config.database import primary_database_url

    return primary_database_url()


def create_db_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True, future=True)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def _session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


class PostgresPlatformRegistryStore:
    """PostgreSQL-backed platform registry with the same semantics as the in-memory store."""

    def __init__(self, database_url: str | Engine) -> None:
        if isinstance(database_url, Engine):
            self.engine = database_url
        else:
            self.engine = create_db_engine(database_url)
        init_db(self.engine)
        self._sessions = _session_factory(self.engine)

    def _session(self) -> Session:
        return self._sessions()

    # --- tenants ---
    def create_tenant(self, tenant_id: str, name: str) -> Tenant:
        with self._session() as session:
            existing = session.get(TenantRow, tenant_id)
            if existing is not None:
                raise AgentEngineError(
                    "TENANT_ALREADY_EXISTS", f"Tenant already exists: {tenant_id}"
                )
            now = _utc_now()
            row = TenantRow(
                tenant_id=tenant_id,
                name=name,
                status="active",
                features={"workspace_customization": False},
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.commit()
            return Tenant(
                tenant_id=tenant_id,
                name=name,
                status="active",
                features=TenantFeatures(workspace_customization=False),
                created_at=now,
                updated_at=now,
            )

    def get_tenant(self, tenant_id: str) -> Tenant:
        with self._session() as session:
            row = session.get(TenantRow, tenant_id)
            if row is None:
                raise AgentEngineError("TENANT_NOT_FOUND", f"Tenant not found: {tenant_id}")
            return Tenant(
                tenant_id=row.tenant_id,
                name=row.name,
                status=row.status,  # type: ignore[arg-type]
                features=TenantFeatures(**(row.features or {})),
                created_at=row.created_at,
                updated_at=row.updated_at,
            )

    def list_tenants(self) -> list[Tenant]:
        with self._session() as session:
            rows = session.scalars(select(TenantRow)).all()
            return [
                Tenant(
                    tenant_id=row.tenant_id,
                    name=row.name,
                    status=row.status,  # type: ignore[arg-type]
                    features=TenantFeatures(**(row.features or {})),
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                for row in rows
            ]

    # --- workspaces ---
    def create_workspace(
        self,
        tenant_id: str,
        workspace_key: str,
        name: str,
        environment: str = "dev",
        blueprint_version_id: str | None = None,
    ) -> TenantWorkspace:
        self.get_tenant(tenant_id)
        with self._session() as session:
            existing = session.scalars(
                select(WorkspaceRow).where(
                    WorkspaceRow.tenant_id == tenant_id,
                    WorkspaceRow.workspace_key == workspace_key,
                )
            ).first()
            if existing is not None:
                raise AgentEngineError(
                    "TENANT_WORKSPACE_ALREADY_EXISTS",
                    f"Workspace key already exists in tenant: {workspace_key}",
                    {"tenant_id": tenant_id, "workspace_key": workspace_key},
                )
            now = _utc_now()
            ws_id = str(uuid4())
            row = WorkspaceRow(
                tenant_workspace_id=ws_id,
                tenant_id=tenant_id,
                workspace_key=workspace_key,
                name=name,
                blueprint_version_id=blueprint_version_id,
                environment=environment,
                status="active",
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.commit()
            return TenantWorkspace(
                tenant_workspace_id=ws_id,
                tenant_id=tenant_id,
                workspace_key=workspace_key,
                name=name,
                blueprint_version_id=blueprint_version_id,
                environment=environment,  # type: ignore[arg-type]
                status="active",
                created_at=now,
                updated_at=now,
            )

    def get_workspace(self, tenant_id: str, tenant_workspace_id: str) -> TenantWorkspace:
        with self._session() as session:
            row = session.get(WorkspaceRow, tenant_workspace_id)
            if row is None or row.tenant_id != tenant_id:
                raise AgentEngineError(
                    "TENANT_WORKSPACE_NOT_FOUND",
                    f"Tenant workspace not found: {tenant_workspace_id}",
                )
            return TenantWorkspace(
                tenant_workspace_id=row.tenant_workspace_id,
                tenant_id=row.tenant_id,
                workspace_key=row.workspace_key,
                name=row.name,
                blueprint_version_id=row.blueprint_version_id,
                environment=row.environment,  # type: ignore[arg-type]
                status=row.status,  # type: ignore[arg-type]
                created_at=row.created_at,
                updated_at=row.updated_at,
            )

    def list_workspaces(self, tenant_id: str) -> list[TenantWorkspace]:
        with self._session() as session:
            rows = session.scalars(
                select(WorkspaceRow).where(WorkspaceRow.tenant_id == tenant_id)
            ).all()
            return [
                TenantWorkspace(
                    tenant_workspace_id=row.tenant_workspace_id,
                    tenant_id=row.tenant_id,
                    workspace_key=row.workspace_key,
                    name=row.name,
                    blueprint_version_id=row.blueprint_version_id,
                    environment=row.environment,  # type: ignore[arg-type]
                    status=row.status,  # type: ignore[arg-type]
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                for row in rows
            ]

    # --- identity ---
    def create_identity(
        self,
        tenant_id: str,
        tenant_workspace_id: str,
        key: str,
        name: str,
        description: str | None = None,
    ) -> IdentityDefinition:
        self.get_workspace(tenant_id, tenant_workspace_id)
        with self._session() as session:
            existing = session.scalars(
                select(IdentityDefinitionRow).where(
                    IdentityDefinitionRow.tenant_id == tenant_id,
                    IdentityDefinitionRow.tenant_workspace_id == tenant_workspace_id,
                    IdentityDefinitionRow.key == key,
                )
            ).first()
            if existing is not None:
                raise AgentEngineError(
                    "IDENTITY_ALREADY_EXISTS", f"Identity key already exists: {key}"
                )
            now = _utc_now()
            definition_id = str(uuid4())
            row = IdentityDefinitionRow(
                definition_id=definition_id,
                tenant_id=tenant_id,
                tenant_workspace_id=tenant_workspace_id,
                key=key,
                name=name,
                description=description,
                status="active",
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.commit()
            return IdentityDefinition(
                definition_id=definition_id,
                tenant_id=tenant_id,
                tenant_workspace_id=tenant_workspace_id,
                key=key,
                name=name,
                description=description,
                created_at=now,
                updated_at=now,
            )

    def get_identity(self, tenant_id: str, definition_id: str) -> IdentityDefinition:
        with self._session() as session:
            row = session.get(IdentityDefinitionRow, definition_id)
            if row is None or row.tenant_id != tenant_id:
                raise AgentEngineError(
                    "IDENTITY_NOT_FOUND", f"Identity not found: {definition_id}"
                )
            return IdentityDefinition(
                definition_id=row.definition_id,
                tenant_id=row.tenant_id,
                tenant_workspace_id=row.tenant_workspace_id,
                key=row.key,
                name=row.name,
                description=row.description,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )

    def list_identities(self, tenant_id: str, tenant_workspace_id: str) -> list[IdentityDefinition]:
        with self._session() as session:
            rows = session.scalars(
                select(IdentityDefinitionRow).where(
                    IdentityDefinitionRow.tenant_id == tenant_id,
                    IdentityDefinitionRow.tenant_workspace_id == tenant_workspace_id,
                )
            ).all()
            return [
                IdentityDefinition(
                    definition_id=row.definition_id,
                    tenant_id=row.tenant_id,
                    tenant_workspace_id=row.tenant_workspace_id,
                    key=row.key,
                    name=row.name,
                    description=row.description,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                for row in rows
            ]

    def _version_from_row(self, row: IdentityVersionRow) -> IdentityVersion:
        payload = dict(row.payload or {})
        return IdentityVersion(
            version_id=row.version_id,
            definition_id=row.definition_id,
            tenant_id=row.tenant_id,
            tenant_workspace_id=row.tenant_workspace_id,
            version=row.version,
            status=row.status,  # type: ignore[arg-type]
            model_profile=str(payload.get("model_profile", "mock")),
            system_prompt=str(payload.get("system_prompt", "")),
            skill_bindings=payload.get("skill_bindings") or [],
            tool_bindings=payload.get("tool_bindings") or [],
            conversation_policy=payload.get("conversation_policy") or {},
            routing_policy=payload.get("routing_policy") or {},
            resource_snapshot=payload.get("resource_snapshot") or {},
            created_at=row.created_at,
            published_at=row.published_at,
        )

    def create_identity_version(
        self,
        tenant_id: str,
        definition_id: str,
        version: str,
        model_profile: str = "mock",
        system_prompt: str = "",
        skill_bindings: list[dict[str, object]] | None = None,
        tool_bindings: list[dict[str, object]] | None = None,
    ) -> IdentityVersion:
        definition = self.get_identity(tenant_id, definition_id)
        with self._session() as session:
            existing = session.scalars(
                select(IdentityVersionRow).where(
                    IdentityVersionRow.definition_id == definition_id,
                    IdentityVersionRow.version == version,
                )
            ).first()
            if existing is not None:
                raise AgentEngineError(
                    "IDENTITY_VERSION_ALREADY_EXISTS",
                    f"Version already exists: {version}",
                )
            now = _utc_now()
            version_id = str(uuid4())
            payload = {
                "model_profile": model_profile,
                "system_prompt": system_prompt,
                "skill_bindings": skill_bindings or [],
                "tool_bindings": tool_bindings or [],
                "resource_snapshot": {
                    "definition_key": definition.key,
                    "model_profile": model_profile,
                },
            }
            row = IdentityVersionRow(
                version_id=version_id,
                definition_id=definition_id,
                tenant_id=definition.tenant_id,
                tenant_workspace_id=definition.tenant_workspace_id,
                version=version,
                status="draft",
                payload=payload,
                created_at=now,
                published_at=None,
            )
            session.add(row)
            session.commit()
            return self._version_from_row(row)

    def update_identity_version_draft(
        self,
        tenant_id: str,
        version_id: str,
        *,
        system_prompt: str | None = None,
        model_profile: str | None = None,
        skill_bindings: list[dict[str, object]] | None = None,
        tool_bindings: list[dict[str, object]] | None = None,
    ) -> IdentityVersion:
        version = self.get_identity_version(tenant_id, version_id)
        ensure_version_mutable(version)
        payload = {
            "model_profile": model_profile
            if model_profile is not None
            else version.model_profile,
            "system_prompt": system_prompt
            if system_prompt is not None
            else version.system_prompt,
            "skill_bindings": skill_bindings
            if skill_bindings is not None
            else [b.model_dump() for b in version.skill_bindings],
            "tool_bindings": tool_bindings
            if tool_bindings is not None
            else [b.model_dump() for b in version.tool_bindings],
            "conversation_policy": version.conversation_policy,
            "routing_policy": version.routing_policy,
            "resource_snapshot": version.resource_snapshot,
        }
        with self._session() as session:
            row = session.get(IdentityVersionRow, version_id)
            if row is None or row.tenant_id != tenant_id:
                raise AgentEngineError(
                    "IDENTITY_VERSION_NOT_FOUND",
                    f"Identity version not found: {version_id}",
                )
            row.payload = payload
            session.commit()
            return self._version_from_row(row)

    def publish_identity_version(self, tenant_id: str, version_id: str) -> IdentityVersion:
        version = self.get_identity_version(tenant_id, version_id)
        if version.status == "published":
            raise AgentEngineError(
                "IDENTITY_VERSION_ALREADY_PUBLISHED",
                f"Version already published: {version_id}",
            )
        if version.status != "draft":
            raise AgentEngineError(
                "IDENTITY_VERSION_NOT_DRAFT",
                f"Only draft versions can be published, got {version.status}",
            )
        with self._session() as session:
            row = session.get(IdentityVersionRow, version_id)
            if row is None or row.tenant_id != tenant_id:
                raise AgentEngineError(
                    "IDENTITY_VERSION_NOT_FOUND",
                    f"Identity version not found: {version_id}",
                )
            row.status = "published"
            row.published_at = _utc_now()
            session.commit()
            return self._version_from_row(row)

    def get_identity_version(self, tenant_id: str, version_id: str) -> IdentityVersion:
        with self._session() as session:
            row = session.get(IdentityVersionRow, version_id)
            if row is None or row.tenant_id != tenant_id:
                raise AgentEngineError(
                    "IDENTITY_VERSION_NOT_FOUND",
                    f"Identity version not found: {version_id}",
                )
            return self._version_from_row(row)

    def list_identity_versions(self, tenant_id: str, definition_id: str) -> list[IdentityVersion]:
        with self._session() as session:
            rows = session.scalars(
                select(IdentityVersionRow).where(
                    IdentityVersionRow.tenant_id == tenant_id,
                    IdentityVersionRow.definition_id == definition_id,
                )
            ).all()
            return [self._version_from_row(row) for row in rows]

    # --- grants ---
    def create_grant(
        self,
        tenant_id: str,
        tenant_workspace_id: str,
        identity_version_id: str,
        grantee_type: str,
        grantee_id: str,
        granted_by: str,
        expires_at: datetime | None = None,
    ) -> IdentityGrant:
        version = self.get_identity_version(tenant_id, identity_version_id)
        if version.tenant_workspace_id != tenant_workspace_id:
            raise AgentEngineError(
                "GRANT_WORKSPACE_MISMATCH",
                "Identity version does not belong to workspace",
            )
        if not can_grant_version(version):
            raise AgentEngineError(
                "GRANT_REQUIRES_PUBLISHED_VERSION",
                "Only published identity versions can be granted",
                {"version_id": identity_version_id, "status": version.status},
            )
        with self._session() as session:
            grant_id = str(uuid4())
            now = _utc_now()
            row = IdentityGrantRow(
                grant_id=grant_id,
                tenant_id=tenant_id,
                tenant_workspace_id=tenant_workspace_id,
                identity_version_id=identity_version_id,
                grantee_type=grantee_type,
                grantee_id=grantee_id,
                granted_by=granted_by,
                created_at=now,
                expires_at=expires_at,
            )
            session.add(row)
            session.commit()
            return IdentityGrant(
                grant_id=grant_id,
                tenant_id=tenant_id,
                tenant_workspace_id=tenant_workspace_id,
                identity_version_id=identity_version_id,
                grantee_type=grantee_type,  # type: ignore[arg-type]
                grantee_id=grantee_id,
                granted_by=granted_by,
                created_at=now,
                expires_at=expires_at,
            )

    def list_grants_for_principal(
        self,
        tenant_id: str,
        principal_id: str,
        group_ids: list[str] | None = None,
        tenant_workspace_id: str | None = None,
    ) -> list[IdentityGrant]:
        now = _utc_now()
        groups = set(group_ids or [])
        with self._session() as session:
            stmt = select(IdentityGrantRow).where(IdentityGrantRow.tenant_id == tenant_id)
            if tenant_workspace_id is not None:
                stmt = stmt.where(IdentityGrantRow.tenant_workspace_id == tenant_workspace_id)
            rows = session.scalars(stmt).all()
            result: list[IdentityGrant] = []
            for row in rows:
                if row.expires_at is not None and row.expires_at <= now:
                    continue
                matched = (
                    row.grantee_type == "user" and row.grantee_id == principal_id
                ) or (row.grantee_type == "group" and row.grantee_id in groups)
                if not matched:
                    continue
                result.append(
                    IdentityGrant(
                        grant_id=row.grant_id,
                        tenant_id=row.tenant_id,
                        tenant_workspace_id=row.tenant_workspace_id,
                        identity_version_id=row.identity_version_id,
                        grantee_type=row.grantee_type,  # type: ignore[arg-type]
                        grantee_id=row.grantee_id,
                        granted_by=row.granted_by,
                        created_at=row.created_at,
                        expires_at=row.expires_at,
                    )
                )
            return result

    def list_grants_in_workspace(
        self, tenant_id: str, tenant_workspace_id: str
    ) -> list[IdentityGrant]:
        with self._session() as session:
            rows = session.scalars(
                select(IdentityGrantRow).where(
                    IdentityGrantRow.tenant_id == tenant_id,
                    IdentityGrantRow.tenant_workspace_id == tenant_workspace_id,
                )
            ).all()
            return [
                IdentityGrant(
                    grant_id=row.grant_id,
                    tenant_id=row.tenant_id,
                    tenant_workspace_id=row.tenant_workspace_id,
                    identity_version_id=row.identity_version_id,
                    grantee_type=row.grantee_type,  # type: ignore[arg-type]
                    grantee_id=row.grantee_id,
                    granted_by=row.granted_by,
                    created_at=row.created_at,
                    expires_at=row.expires_at,
                )
                for row in rows
            ]

    def delete_grant(self, tenant_id: str, grant_id: str) -> None:
        with self._session() as session:
            row = session.get(IdentityGrantRow, grant_id)
            if row is None or row.tenant_id != tenant_id:
                raise AgentEngineError("GRANT_NOT_FOUND", f"Grant not found: {grant_id}")
            session.delete(row)
            session.commit()

    # --- artifacts ---
    def _artifact_from_row(self, row: ArtifactRow) -> ArtifactMeta:
        return ArtifactMeta(
            artifact_id=row.artifact_id,
            tenant_id=row.tenant_id,
            tenant_workspace_id=row.tenant_workspace_id,
            owner_principal_id=row.owner_principal_id,
            run_id=row.run_id,
            session_id=row.session_id,
            identity_key=row.identity_key,
            logical_path=row.logical_path,
            object_key=row.object_key,
            media_type=row.media_type,
            size_bytes=row.size_bytes,
            checksum=row.checksum,
            created_at=row.created_at,
            expires_at=row.expires_at,
        )

    def register_artifact(self, meta: ArtifactMeta) -> ArtifactMeta:
        self.get_workspace(meta.tenant_id, meta.tenant_workspace_id)
        with self._session() as session:
            existing = session.scalars(
                select(ArtifactRow).where(
                    ArtifactRow.tenant_id == meta.tenant_id,
                    ArtifactRow.tenant_workspace_id == meta.tenant_workspace_id,
                    ArtifactRow.owner_principal_id == meta.owner_principal_id,
                    ArtifactRow.logical_path == meta.logical_path,
                )
            ).first()
            if existing is not None:
                raise AgentEngineError(
                    "ARTIFACT_PATH_ALREADY_EXISTS",
                    f"Artifact path already exists: {meta.logical_path}",
                )
            row = ArtifactRow(
                artifact_id=meta.artifact_id,
                tenant_id=meta.tenant_id,
                tenant_workspace_id=meta.tenant_workspace_id,
                owner_principal_id=meta.owner_principal_id,
                run_id=meta.run_id,
                session_id=meta.session_id,
                identity_key=meta.identity_key,
                logical_path=meta.logical_path,
                object_key=meta.object_key,
                media_type=meta.media_type,
                size_bytes=meta.size_bytes,
                checksum=meta.checksum,
                created_at=meta.created_at,
                expires_at=meta.expires_at,
            )
            session.add(row)
            session.commit()
            return meta

    def get_artifact_for_owner(
        self,
        artifact_id: str,
        *,
        tenant_id: str,
        owner_principal_id: str,
        tenant_workspace_id: str | None = None,
    ) -> ArtifactMeta:
        with self._session() as session:
            row = session.get(ArtifactRow, artifact_id)
            if row is None or row.tenant_id != tenant_id:
                raise AgentEngineError(
                    "ARTIFACT_NOT_FOUND", f"Artifact not found: {artifact_id}"
                )
            if (
                tenant_workspace_id is not None
                and row.tenant_workspace_id != tenant_workspace_id
            ):
                raise AgentEngineError(
                    "ARTIFACT_NOT_FOUND", f"Artifact not found: {artifact_id}"
                )
            if row.owner_principal_id != owner_principal_id:
                raise AgentEngineError(
                    "ARTIFACT_NOT_FOUND", f"Artifact not found: {artifact_id}"
                )
            return self._artifact_from_row(row)

    def list_artifacts_for_owner(
        self,
        *,
        tenant_id: str,
        owner_principal_id: str,
        tenant_workspace_id: str | None = None,
        path_prefix: str | None = None,
    ) -> list[ArtifactMeta]:
        prefix = normalize_logical_path(path_prefix) if path_prefix else ""
        with self._session() as session:
            stmt = select(ArtifactRow).where(
                ArtifactRow.tenant_id == tenant_id,
                ArtifactRow.owner_principal_id == owner_principal_id,
            )
            if tenant_workspace_id is not None:
                stmt = stmt.where(ArtifactRow.tenant_workspace_id == tenant_workspace_id)
            rows = session.scalars(stmt).all()
            items = [self._artifact_from_row(row) for row in rows]
            if prefix:
                items = [
                    item
                    for item in items
                    if item.logical_path == prefix
                    or item.logical_path.startswith(prefix + "/")
                ]
            items.sort(key=lambda item: item.logical_path)
            return items

    def list_artifacts_admin(
        self,
        *,
        tenant_id: str,
        tenant_workspace_id: str,
        owner_principal_id: str | None = None,
    ) -> list[ArtifactMeta]:
        with self._session() as session:
            stmt = select(ArtifactRow).where(
                ArtifactRow.tenant_id == tenant_id,
                ArtifactRow.tenant_workspace_id == tenant_workspace_id,
            )
            if owner_principal_id is not None:
                stmt = stmt.where(ArtifactRow.owner_principal_id == owner_principal_id)
            rows = session.scalars(stmt).all()
            items = [self._artifact_from_row(row) for row in rows]
            items.sort(key=lambda item: item.logical_path)
            return items

    # --- elevations / audit ---
    def create_elevation(
        self,
        *,
        tenant_id: str,
        tenant_workspace_id: str,
        actor_principal_id: str,
        owner_principal_id: str,
        path_prefix: str,
        reason: str,
        ttl_minutes: int = 15,
    ) -> ArtifactElevation:
        if not reason.strip():
            raise AgentEngineError("ELEVATION_REASON_REQUIRED", "reason is required")
        now = _utc_now()
        elevation = ArtifactElevation(
            elevation_id=str(uuid4()),
            tenant_id=tenant_id,
            tenant_workspace_id=tenant_workspace_id,
            actor_principal_id=actor_principal_id,
            owner_principal_id=owner_principal_id,
            path_prefix=normalize_logical_path(path_prefix),
            reason=reason.strip(),
            created_at=now,
            expires_at=now + timedelta(minutes=ttl_minutes),
        )
        with self._session() as session:
            session.add(
                ElevationRow(
                    elevation_id=elevation.elevation_id,
                    tenant_id=elevation.tenant_id,
                    tenant_workspace_id=elevation.tenant_workspace_id,
                    actor_principal_id=elevation.actor_principal_id,
                    owner_principal_id=elevation.owner_principal_id,
                    path_prefix=elevation.path_prefix,
                    reason=elevation.reason,
                    created_at=elevation.created_at,
                    expires_at=elevation.expires_at,
                )
            )
            session.commit()
        self.append_audit(
            tenant_id=tenant_id,
            actor_principal_id=actor_principal_id,
            action="elevate_artifact_read",
            target=f"owner={owner_principal_id};prefix={elevation.path_prefix}",
            reason=elevation.reason,
        )
        return elevation

    def has_active_elevation(
        self,
        *,
        tenant_id: str,
        actor_principal_id: str,
        owner_principal_id: str,
        logical_path: str,
    ) -> bool:
        now = _utc_now()
        path = normalize_logical_path(logical_path)
        with self._session() as session:
            rows = session.scalars(
                select(ElevationRow).where(
                    ElevationRow.tenant_id == tenant_id,
                    ElevationRow.actor_principal_id == actor_principal_id,
                    ElevationRow.owner_principal_id == owner_principal_id,
                )
            ).all()
            for row in rows:
                if row.expires_at <= now:
                    continue
                if row.path_prefix and not (
                    path == row.path_prefix or path.startswith(row.path_prefix + "/")
                ):
                    continue
                return True
            return False

    def append_audit(
        self,
        *,
        tenant_id: str,
        actor_principal_id: str,
        action: str,
        target: str,
        reason: str | None = None,
        result: str = "ok",
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid4()),
            tenant_id=tenant_id,
            actor_principal_id=actor_principal_id,
            action=action,
            target=target,
            reason=reason,
            result=result,
        )
        with self._session() as session:
            session.add(
                AuditRow(
                    event_id=event.event_id,
                    tenant_id=event.tenant_id,
                    actor_principal_id=event.actor_principal_id,
                    action=event.action,
                    target=event.target,
                    reason=event.reason,
                    result=event.result,
                    data={},
                    created_at=event.created_at,
                )
            )
            session.commit()
        return event

    def list_audits(self, tenant_id: str) -> list[AuditEvent]:
        with self._session() as session:
            rows = session.scalars(
                select(AuditRow).where(AuditRow.tenant_id == tenant_id)
            ).all()
            events = [
                AuditEvent(
                    event_id=row.event_id,
                    tenant_id=row.tenant_id,
                    actor_principal_id=row.actor_principal_id,
                    action=row.action,
                    target=row.target,
                    reason=row.reason,
                    result=row.result,
                    data=row.data or {},
                    created_at=row.created_at,
                )
                for row in rows
            ]
            events.sort(key=lambda item: item.created_at, reverse=True)
            return events


def create_platform_registry_from_env(
    database_url: str | None = None,
) -> PostgresPlatformRegistryStore | None:
    url = database_url or default_database_url()
    if not url:
        return None
    return PostgresPlatformRegistryStore(url)
