"""Platform registry: tenants, workspaces, identity versions, grants, artifact catalog."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError

from app.domain.errors import AgentEngineError
from app.domain.platform import (
    ArtifactElevation,
    ArtifactMeta,
    AuditEvent,
    IdentityDefinition,
    IdentityGrant,
    IdentityVersion,
    Tenant,
    TenantWorkspace,
    can_grant_version,
    ensure_version_mutable,
    normalize_logical_path,
)


class PlatformDocument(BaseModel):
    version: int = 1
    tenants: dict[str, Tenant] = Field(default_factory=dict)
    workspaces: dict[str, TenantWorkspace] = Field(default_factory=dict)
    definitions: dict[str, IdentityDefinition] = Field(default_factory=dict)
    versions: dict[str, IdentityVersion] = Field(default_factory=dict)
    grants: dict[str, IdentityGrant] = Field(default_factory=dict)
    artifacts: dict[str, ArtifactMeta] = Field(default_factory=dict)
    elevations: dict[str, ArtifactElevation] = Field(default_factory=dict)
    audits: dict[str, AuditEvent] = Field(default_factory=dict)


class InMemoryPlatformRegistryStore:
    def __init__(self) -> None:
        self._tenants: dict[str, Tenant] = {}
        self._workspaces: dict[str, TenantWorkspace] = {}
        self._definitions: dict[str, IdentityDefinition] = {}
        self._versions: dict[str, IdentityVersion] = {}
        self._grants: dict[str, IdentityGrant] = {}
        self._artifacts: dict[str, ArtifactMeta] = {}
        self._elevations: dict[str, ArtifactElevation] = {}
        self._audits: dict[str, AuditEvent] = {}

    # --- tenants ---
    def create_tenant(self, tenant_id: str, name: str) -> Tenant:
        if tenant_id in self._tenants:
            raise AgentEngineError("TENANT_ALREADY_EXISTS", f"Tenant already exists: {tenant_id}")
        tenant = Tenant(tenant_id=tenant_id, name=name)
        self._tenants[tenant_id] = tenant
        return tenant

    def get_tenant(self, tenant_id: str) -> Tenant:
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            raise AgentEngineError("TENANT_NOT_FOUND", f"Tenant not found: {tenant_id}")
        return tenant

    def list_tenants(self) -> list[Tenant]:
        return list(self._tenants.values())

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
        for ws in self._workspaces.values():
            if ws.tenant_id == tenant_id and ws.workspace_key == workspace_key:
                raise AgentEngineError(
                    "TENANT_WORKSPACE_ALREADY_EXISTS",
                    f"Workspace key already exists in tenant: {workspace_key}",
                    {"tenant_id": tenant_id, "workspace_key": workspace_key},
                )
        workspace = TenantWorkspace(
            tenant_workspace_id=str(uuid4()),
            tenant_id=tenant_id,
            workspace_key=workspace_key,
            name=name,
            environment=environment,  # type: ignore[arg-type]
            blueprint_version_id=blueprint_version_id,
        )
        self._workspaces[workspace.tenant_workspace_id] = workspace
        return workspace

    def get_workspace(self, tenant_id: str, tenant_workspace_id: str) -> TenantWorkspace:
        workspace = self._workspaces.get(tenant_workspace_id)
        if workspace is None or workspace.tenant_id != tenant_id:
            raise AgentEngineError(
                "TENANT_WORKSPACE_NOT_FOUND",
                f"Tenant workspace not found: {tenant_workspace_id}",
            )
        return workspace

    def list_workspaces(self, tenant_id: str) -> list[TenantWorkspace]:
        return [ws for ws in self._workspaces.values() if ws.tenant_id == tenant_id]

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
        for definition in self._definitions.values():
            if (
                definition.tenant_id == tenant_id
                and definition.tenant_workspace_id == tenant_workspace_id
                and definition.key == key
            ):
                raise AgentEngineError(
                    "IDENTITY_ALREADY_EXISTS",
                    f"Identity key already exists: {key}",
                )
        definition = IdentityDefinition(
            definition_id=str(uuid4()),
            tenant_id=tenant_id,
            tenant_workspace_id=tenant_workspace_id,
            key=key,
            name=name,
            description=description,
        )
        self._definitions[definition.definition_id] = definition
        return definition

    def get_identity(self, tenant_id: str, definition_id: str) -> IdentityDefinition:
        definition = self._definitions.get(definition_id)
        if definition is None or definition.tenant_id != tenant_id:
            raise AgentEngineError("IDENTITY_NOT_FOUND", f"Identity not found: {definition_id}")
        return definition

    def list_identities(self, tenant_id: str, tenant_workspace_id: str) -> list[IdentityDefinition]:
        return [
            d
            for d in self._definitions.values()
            if d.tenant_id == tenant_id and d.tenant_workspace_id == tenant_workspace_id
        ]

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
        for existing in self._versions.values():
            if existing.definition_id == definition_id and existing.version == version:
                raise AgentEngineError(
                    "IDENTITY_VERSION_ALREADY_EXISTS",
                    f"Version already exists: {version}",
                )
        identity_version = IdentityVersion(
            version_id=str(uuid4()),
            definition_id=definition_id,
            tenant_id=definition.tenant_id,
            tenant_workspace_id=definition.tenant_workspace_id,
            version=version,
            model_profile=model_profile,
            system_prompt=system_prompt,
            skill_bindings=skill_bindings or [],  # type: ignore[arg-type]
            tool_bindings=tool_bindings or [],  # type: ignore[arg-type]
            resource_snapshot={
                "definition_key": definition.key,
                "model_profile": model_profile,
            },
        )
        self._versions[identity_version.version_id] = identity_version
        return identity_version

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
        updates: dict[str, object] = {}
        if system_prompt is not None:
            updates["system_prompt"] = system_prompt
        if model_profile is not None:
            updates["model_profile"] = model_profile
        if skill_bindings is not None:
            updates["skill_bindings"] = skill_bindings
        if tool_bindings is not None:
            updates["tool_bindings"] = tool_bindings
        updated = version.model_copy(update=updates)
        self._versions[version_id] = updated
        return updated

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
        published = version.model_copy(
            update={"status": "published", "published_at": datetime.now(UTC)}
        )
        self._versions[version_id] = published
        return published

    def get_identity_version(self, tenant_id: str, version_id: str) -> IdentityVersion:
        version = self._versions.get(version_id)
        if version is None or version.tenant_id != tenant_id:
            raise AgentEngineError(
                "IDENTITY_VERSION_NOT_FOUND",
                f"Identity version not found: {version_id}",
            )
        return version

    def list_identity_versions(self, tenant_id: str, definition_id: str) -> list[IdentityVersion]:
        return [
            v
            for v in self._versions.values()
            if v.tenant_id == tenant_id and v.definition_id == definition_id
        ]

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
        grant = IdentityGrant(
            grant_id=str(uuid4()),
            tenant_id=tenant_id,
            tenant_workspace_id=tenant_workspace_id,
            identity_version_id=identity_version_id,
            grantee_type=grantee_type,  # type: ignore[arg-type]
            grantee_id=grantee_id,
            granted_by=granted_by,
            expires_at=expires_at,
        )
        self._grants[grant.grant_id] = grant
        return grant

    def list_grants_for_principal(
        self,
        tenant_id: str,
        principal_id: str,
        group_ids: list[str] | None = None,
        tenant_workspace_id: str | None = None,
    ) -> list[IdentityGrant]:
        now = datetime.now(UTC)
        groups = set(group_ids or [])
        result: list[IdentityGrant] = []
        for grant in self._grants.values():
            if grant.tenant_id != tenant_id:
                continue
            if tenant_workspace_id is not None and grant.tenant_workspace_id != tenant_workspace_id:
                continue
            if grant.expires_at is not None and grant.expires_at <= now:
                continue
            if grant.grantee_type == "user" and grant.grantee_id == principal_id:
                result.append(grant)
            elif grant.grantee_type == "group" and grant.grantee_id in groups:
                result.append(grant)
        return result

    def list_grants_in_workspace(
        self,
        tenant_id: str,
        tenant_workspace_id: str,
    ) -> list[IdentityGrant]:
        return [
            grant
            for grant in self._grants.values()
            if grant.tenant_id == tenant_id and grant.tenant_workspace_id == tenant_workspace_id
        ]

    def delete_grant(self, tenant_id: str, grant_id: str) -> None:
        grant = self._grants.get(grant_id)
        if grant is None or grant.tenant_id != tenant_id:
            raise AgentEngineError("GRANT_NOT_FOUND", f"Grant not found: {grant_id}")
        del self._grants[grant_id]

    # --- artifacts ---
    def register_artifact(self, meta: ArtifactMeta) -> ArtifactMeta:
        self.get_workspace(meta.tenant_id, meta.tenant_workspace_id)
        for existing in self._artifacts.values():
            if (
                existing.tenant_id == meta.tenant_id
                and existing.tenant_workspace_id == meta.tenant_workspace_id
                and existing.owner_principal_id == meta.owner_principal_id
                and existing.logical_path == meta.logical_path
            ):
                raise AgentEngineError(
                    "ARTIFACT_PATH_ALREADY_EXISTS",
                    f"Artifact path already exists: {meta.logical_path}",
                )
        self._artifacts[meta.artifact_id] = meta
        return meta

    def get_artifact_for_owner(
        self,
        artifact_id: str,
        *,
        tenant_id: str,
        owner_principal_id: str,
        tenant_workspace_id: str | None = None,
    ) -> ArtifactMeta:
        meta = self._artifacts.get(artifact_id)
        if meta is None:
            raise AgentEngineError("ARTIFACT_NOT_FOUND", f"Artifact not found: {artifact_id}")
        if meta.tenant_id != tenant_id:
            raise AgentEngineError("ARTIFACT_NOT_FOUND", f"Artifact not found: {artifact_id}")
        if tenant_workspace_id is not None and meta.tenant_workspace_id != tenant_workspace_id:
            raise AgentEngineError("ARTIFACT_NOT_FOUND", f"Artifact not found: {artifact_id}")
        if meta.owner_principal_id != owner_principal_id:
            raise AgentEngineError("ARTIFACT_NOT_FOUND", f"Artifact not found: {artifact_id}")
        return meta

    def list_artifacts_for_owner(
        self,
        *,
        tenant_id: str,
        owner_principal_id: str,
        tenant_workspace_id: str | None = None,
        path_prefix: str | None = None,
    ) -> list[ArtifactMeta]:
        prefix = normalize_logical_path(path_prefix) if path_prefix else ""
        items: list[ArtifactMeta] = []
        for meta in self._artifacts.values():
            if meta.tenant_id != tenant_id:
                continue
            if tenant_workspace_id is not None and meta.tenant_workspace_id != tenant_workspace_id:
                continue
            if meta.owner_principal_id != owner_principal_id:
                continue
            if prefix and not (
                meta.logical_path == prefix or meta.logical_path.startswith(prefix + "/")
            ):
                continue
            items.append(meta)
        items.sort(key=lambda item: item.logical_path)
        return items

    def list_artifacts_admin(
        self,
        *,
        tenant_id: str,
        tenant_workspace_id: str,
        owner_principal_id: str | None = None,
    ) -> list[ArtifactMeta]:
        items = [
            meta
            for meta in self._artifacts.values()
            if meta.tenant_id == tenant_id and meta.tenant_workspace_id == tenant_workspace_id
        ]
        if owner_principal_id is not None:
            items = [meta for meta in items if meta.owner_principal_id == owner_principal_id]
        items.sort(key=lambda item: item.logical_path)
        return items

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
        elevation = ArtifactElevation(
            elevation_id=str(uuid4()),
            tenant_id=tenant_id,
            tenant_workspace_id=tenant_workspace_id,
            actor_principal_id=actor_principal_id,
            owner_principal_id=owner_principal_id,
            path_prefix=normalize_logical_path(path_prefix),
            reason=reason.strip(),
            expires_at=datetime.now(UTC) + timedelta(minutes=ttl_minutes),
        )
        self._elevations[elevation.elevation_id] = elevation
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
        now = datetime.now(UTC)
        path = normalize_logical_path(logical_path)
        for elevation in self._elevations.values():
            if elevation.tenant_id != tenant_id:
                continue
            if elevation.actor_principal_id != actor_principal_id:
                continue
            if elevation.owner_principal_id != owner_principal_id:
                continue
            if elevation.expires_at <= now:
                continue
            if elevation.path_prefix and not (
                path == elevation.path_prefix or path.startswith(elevation.path_prefix + "/")
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
        self._audits[event.event_id] = event
        return event

    def list_audits(self, tenant_id: str) -> list[AuditEvent]:
        events = [a for a in self._audits.values() if a.tenant_id == tenant_id]
        events.sort(key=lambda item: item.created_at, reverse=True)
        return events


class JsonPlatformRegistryStore(InMemoryPlatformRegistryStore):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        super().__init__()
        self._load_into_memory()

    def _load_into_memory(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            document = PlatformDocument.model_validate(raw)
        except json.JSONDecodeError as exc:
            raise AgentEngineError(
                "PLATFORM_STORE_INVALID",
                f"Invalid platform store JSON: {self.path}",
            ) from exc
        except ValidationError as exc:
            raise AgentEngineError(
                "PLATFORM_STORE_INVALID",
                f"Invalid platform store shape: {self.path}",
            ) from exc
        self._tenants = dict(document.tenants)
        self._workspaces = dict(document.workspaces)
        self._definitions = dict(document.definitions)
        self._versions = dict(document.versions)
        self._grants = dict(document.grants)
        self._artifacts = dict(document.artifacts)
        self._elevations = dict(document.elevations)
        self._audits = dict(document.audits)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        document = PlatformDocument(
            tenants=dict(self._tenants),
            workspaces=dict(self._workspaces),
            definitions=dict(self._definitions),
            versions=dict(self._versions),
            grants=dict(self._grants),
            artifacts=dict(self._artifacts),
            elevations=dict(self._elevations),
            audits=dict(self._audits),
        )
        self.path.write_text(
            json.dumps(document.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def create_tenant(self, tenant_id: str, name: str) -> Tenant:
        tenant = super().create_tenant(tenant_id, name)
        self._save()
        return tenant

    def create_workspace(
        self,
        tenant_id: str,
        workspace_key: str,
        name: str,
        environment: str = "dev",
        blueprint_version_id: str | None = None,
    ) -> TenantWorkspace:
        workspace = super().create_workspace(
            tenant_id,
            workspace_key,
            name,
            environment=environment,
            blueprint_version_id=blueprint_version_id,
        )
        self._save()
        return workspace

    def create_identity(
        self,
        tenant_id: str,
        tenant_workspace_id: str,
        key: str,
        name: str,
        description: str | None = None,
    ) -> IdentityDefinition:
        definition = super().create_identity(
            tenant_id, tenant_workspace_id, key, name, description
        )
        self._save()
        return definition

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
        identity_version = super().create_identity_version(
            tenant_id,
            definition_id,
            version,
            model_profile=model_profile,
            system_prompt=system_prompt,
            skill_bindings=skill_bindings,
            tool_bindings=tool_bindings,
        )
        self._save()
        return identity_version

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
        updated = super().update_identity_version_draft(
            tenant_id,
            version_id,
            system_prompt=system_prompt,
            model_profile=model_profile,
            skill_bindings=skill_bindings,
            tool_bindings=tool_bindings,
        )
        self._save()
        return updated

    def publish_identity_version(self, tenant_id: str, version_id: str) -> IdentityVersion:
        published = super().publish_identity_version(tenant_id, version_id)
        self._save()
        return published

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
        grant = super().create_grant(
            tenant_id,
            tenant_workspace_id,
            identity_version_id,
            grantee_type,
            grantee_id,
            granted_by,
            expires_at=expires_at,
        )
        self._save()
        return grant

    def delete_grant(self, tenant_id: str, grant_id: str) -> None:
        super().delete_grant(tenant_id, grant_id)
        self._save()

    def register_artifact(self, meta: ArtifactMeta) -> ArtifactMeta:
        saved = super().register_artifact(meta)
        self._save()
        return saved

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
        elevation = super().create_elevation(
            tenant_id=tenant_id,
            tenant_workspace_id=tenant_workspace_id,
            actor_principal_id=actor_principal_id,
            owner_principal_id=owner_principal_id,
            path_prefix=path_prefix,
            reason=reason,
            ttl_minutes=ttl_minutes,
        )
        self._save()
        return elevation

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
        event = super().append_audit(
            tenant_id=tenant_id,
            actor_principal_id=actor_principal_id,
            action=action,
            target=target,
            reason=reason,
            result=result,
        )
        self._save()
        return event


# Re-export domain helper for existing imports.
__all_extra__ = ("build_artifact_meta",)


def list_directory_nodes(items: list[ArtifactMeta], path: str) -> dict[str, object]:
    """Group artifact metas into folder/file nodes under a logical path."""
    prefix = normalize_logical_path(path)
    folders: set[str] = set()
    files: list[dict[str, object]] = []
    for meta in items:
        rel = meta.logical_path
        if prefix:
            if not rel.startswith(prefix + "/"):
                continue
            rel = rel[len(prefix) + 1 :]
        if not rel:
            continue
        if "/" in rel:
            folders.add(rel.split("/", 1)[0])
        else:
            files.append(
                {
                    "name": rel,
                    "type": "file",
                    "artifact_id": meta.artifact_id,
                    "media_type": meta.media_type,
                    "size_bytes": meta.size_bytes,
                    "created_at": meta.created_at.isoformat(),
                    "run_id": meta.run_id,
                }
            )
    return {
        "path": prefix,
        "folders": sorted(folders),
        "files": sorted(files, key=lambda item: str(item["name"])),
    }
