"""Platform SaaS domain: tenant, workspace instance, identity versions, grants, artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.common import JsonObject

TenantStatus = Literal["active", "suspended"]
WorkspaceEnv = Literal["dev", "staging", "production"]
ResourceStatus = Literal["draft", "review", "published", "archived"]
GranteeType = Literal["user", "group"]
PrincipalType = Literal["user", "service_account", "platform_operator"]


def utc_now() -> datetime:
    return datetime.now(UTC)


class TenantFeatures(BaseModel):
    workspace_customization: bool = False


class Tenant(BaseModel):
    tenant_id: str
    name: str
    status: TenantStatus = "active"
    features: TenantFeatures = Field(default_factory=TenantFeatures)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class WorkspaceBlueprint(BaseModel):
    blueprint_id: str
    key: str
    name: str
    description: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class WorkspaceBlueprintVersion(BaseModel):
    version_id: str
    blueprint_id: str
    version: str
    status: ResourceStatus = "published"
    manifest: JsonObject = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    published_at: datetime | None = None


class TenantWorkspace(BaseModel):
    tenant_workspace_id: str
    tenant_id: str
    workspace_key: str
    name: str
    blueprint_version_id: str | None = None
    environment: WorkspaceEnv = "dev"
    status: TenantStatus = "active"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SkillBinding(BaseModel):
    skill_id: str
    version: str | None = None
    priority: int = 100


class ToolBinding(BaseModel):
    tool_id: str
    effect: Literal["allow", "ask", "deny"] = "allow"
    reason: str = ""


class IdentityDefinition(BaseModel):
    definition_id: str
    tenant_id: str
    tenant_workspace_id: str
    key: str
    name: str
    description: str | None = None
    status: TenantStatus = "active"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class IdentityVersion(BaseModel):
    version_id: str
    definition_id: str
    tenant_id: str
    tenant_workspace_id: str
    version: str
    status: ResourceStatus = "draft"
    model_profile: str = "mock"
    system_prompt: str = ""
    skill_bindings: list[SkillBinding] = Field(default_factory=list)
    tool_bindings: list[ToolBinding] = Field(default_factory=list)
    conversation_policy: JsonObject = Field(default_factory=dict)
    routing_policy: JsonObject = Field(default_factory=dict)
    resource_snapshot: JsonObject = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    published_at: datetime | None = None


class IdentityGrant(BaseModel):
    grant_id: str
    tenant_id: str
    tenant_workspace_id: str
    identity_version_id: str
    grantee_type: GranteeType
    grantee_id: str
    granted_by: str
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None


class Principal(BaseModel):
    tenant_id: str
    principal_id: str
    principal_type: PrincipalType = "user"
    display_name: str | None = None
    workspace_roles: list[str] = Field(default_factory=list)
    group_ids: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)
    auth_session_id: str | None = None

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes or "platform.*" in self.scopes


class ArtifactMeta(BaseModel):
    artifact_id: str
    tenant_id: str
    tenant_workspace_id: str
    owner_principal_id: str
    run_id: str | None = None
    session_id: str | None = None
    identity_key: str | None = None
    logical_path: str
    object_key: str
    media_type: str = "application/octet-stream"
    size_bytes: int = 0
    checksum: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None


class ArtifactElevation(BaseModel):
    elevation_id: str
    tenant_id: str
    tenant_workspace_id: str
    actor_principal_id: str
    owner_principal_id: str
    path_prefix: str
    reason: str
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime


class AuditEvent(BaseModel):
    event_id: str
    tenant_id: str
    actor_principal_id: str
    action: str
    target: str
    reason: str | None = None
    result: str = "ok"
    data: JsonObject = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


def build_owner_artifact_path(
    tenant_id: str,
    tenant_workspace_id: str,
    owner_principal_id: str,
    logical_path: str,
) -> str:
    cleaned = logical_path.strip().strip("/")
    return (
        f"tenants/{tenant_id}/workspaces/{tenant_workspace_id}"
        f"/users/{owner_principal_id}/{cleaned}"
    )


def normalize_logical_path(path: str) -> str:
    return path.strip().strip("/")


def build_artifact_meta(
    *,
    tenant_id: str,
    tenant_workspace_id: str,
    owner_principal_id: str,
    logical_path: str,
    run_id: str | None = None,
    session_id: str | None = None,
    identity_key: str | None = None,
    media_type: str = "application/octet-stream",
    size_bytes: int = 0,
    object_key: str | None = None,
) -> ArtifactMeta:
    from uuid import uuid4

    path = normalize_logical_path(logical_path)
    return ArtifactMeta(
        artifact_id=str(uuid4()),
        tenant_id=tenant_id,
        tenant_workspace_id=tenant_workspace_id,
        owner_principal_id=owner_principal_id,
        run_id=run_id,
        session_id=session_id,
        identity_key=identity_key,
        logical_path=path,
        object_key=object_key
        or build_owner_artifact_path(
            tenant_id, tenant_workspace_id, owner_principal_id, path
        ),
        media_type=media_type,
        size_bytes=size_bytes,
    )


def can_grant_version(version: IdentityVersion) -> bool:
    return version.status == "published"


def ensure_version_mutable(version: IdentityVersion) -> None:
    from app.domain.errors import AgentEngineError

    if version.status != "draft":
        raise AgentEngineError(
            "IDENTITY_VERSION_IMMUTABLE",
            f"Identity version is {version.status}; create a new draft to edit",
            {"version_id": version.version_id, "status": version.status},
        )


__all__ = [
    "ArtifactElevation",
    "ArtifactMeta",
    "AuditEvent",
    "IdentityDefinition",
    "IdentityGrant",
    "IdentityVersion",
    "Principal",
    "PrincipalType",
    "ResourceStatus",
    "SkillBinding",
    "Tenant",
    "TenantFeatures",
    "TenantWorkspace",
    "ToolBinding",
    "WorkspaceBlueprint",
    "WorkspaceBlueprintVersion",
    "build_owner_artifact_path",
    "can_grant_version",
    "ensure_version_mutable",
    "normalize_logical_path",
    "utc_now",
]
