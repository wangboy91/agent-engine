"""1.0.1 platform API: tenants, identity registry, /me isolation, artifact catalog."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.domain.errors import AgentEngineError
from app.domain.platform import (
    ArtifactElevation,
    ArtifactMeta,
    AuditEvent,
    IdentityDefinition,
    IdentityGrant,
    IdentityVersion,
    Principal,
    Tenant,
    TenantWorkspace,
    build_artifact_meta,
)
from app.engine import SkillEngine
from app.infrastructure.persistence.platform_registry import (
    list_directory_nodes,
)

router = APIRouter(prefix="/api/v1")


class PrincipalHeaders(BaseModel):
    tenant_id: str
    principal_id: str
    principal_type: str = "user"
    display_name: str | None = None
    workspace_roles: list[str] = Field(default_factory=list)
    group_ids: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def get_engine(request: Request) -> SkillEngine:
    return cast(SkillEngine, request.app.state.engine)


def get_principal(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_principal_id: str | None = Header(default=None, alias="X-Principal-Id"),
    x_principal_type: str | None = Header(default=None, alias="X-Principal-Type"),
    x_display_name: str | None = Header(default=None, alias="X-Display-Name"),
    x_workspace_roles: str | None = Header(default=None, alias="X-Workspace-Roles"),
    x_group_ids: str | None = Header(default=None, alias="X-Group-Ids"),
    x_scopes: str | None = Header(default=None, alias="X-Scopes"),
) -> Principal:
    # 1) Prefer Bearer dev token from POST /api/v1/auth/login
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        from app.application.platform.auth_demo import parse_dev_token

        principal = parse_dev_token(token)
        if principal is not None:
            return principal

    # 2) Dev header principal provider (tests / curl). Production OIDC replaces this.
    if x_tenant_id and x_principal_id:
        return Principal(
            tenant_id=x_tenant_id,
            principal_id=x_principal_id,
            principal_type=(x_principal_type or "user"),  # type: ignore[arg-type]
            display_name=x_display_name,
            workspace_roles=_split_csv(x_workspace_roles),
            group_ids=_split_csv(x_group_ids),
            scopes=_split_csv(x_scopes),
        )
    raise HTTPException(status_code=401, detail="Principal required (login or headers)")


class CreateTenantRequest(BaseModel):
    tenant_id: str
    name: str


class CreateWorkspaceRequest(BaseModel):
    workspace_key: str
    name: str
    environment: str = "dev"
    blueprint_version_id: str | None = None


class CreateIdentityRequest(BaseModel):
    key: str
    name: str
    description: str | None = None


class CreateVersionRequest(BaseModel):
    version: str
    model_profile: str = "mock"
    system_prompt: str = ""
    skill_bindings: list[dict[str, Any]] = Field(default_factory=list)
    tool_bindings: list[dict[str, Any]] = Field(default_factory=list)


class CreateGrantRequest(BaseModel):
    identity_version_id: str
    grantee_type: str
    grantee_id: str


class ElevateArtifactRequest(BaseModel):
    owner_principal_id: str
    reason: str
    path_prefix: str = ""


class CreateSessionRequest(BaseModel):
    session_id: str | None = None


class RegisterArtifactRequest(BaseModel):
    logical_path: str
    media_type: str = "application/octet-stream"
    size_bytes: int = 0
    run_id: str | None = None
    session_id: str | None = None
    identity_key: str | None = None
    object_key: str | None = None


def _handle(exc: AgentEngineError) -> HTTPException:
    code = exc.code
    status = 400
    if code.endswith("NOT_FOUND"):
        status = 404
    if code in {"IDENTITY_VERSION_IMMUTABLE", "IDENTITY_VERSION_ALREADY_PUBLISHED"}:
        status = 409
    return HTTPException(status_code=status, detail={"code": code, "message": exc.message})


# --- admin: tenants / workspaces / identities ---


@router.post("/tenants", response_model=Tenant)
def create_tenant(
    request: CreateTenantRequest,
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> dict[str, Any]:
    allowed = (
        principal.principal_type == "platform_operator"
        or principal.has_scope("platform.tenant.create")
        or "platform_admin" in principal.workspace_roles
        or (
            "tenant_admin" in principal.workspace_roles
            and principal.tenant_id == request.tenant_id
        )
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="platform tenant create not allowed")
    try:
        tenant = engine.platform_registry.create_tenant(request.tenant_id, request.name)
        return tenant.model_dump(mode="json")
    except AgentEngineError as exc:
        raise _handle(exc) from exc


@router.get("/tenants", response_model=list[Tenant])
def list_tenants(
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> list[dict[str, Any]]:
    if (
        principal.principal_type != "platform_operator"
        and "platform_admin" not in principal.workspace_roles
    ):
        # tenant admins only see own tenant
        try:
            tenant = engine.platform_registry.get_tenant(principal.tenant_id)
            return [tenant.model_dump(mode="json")]
        except AgentEngineError:
            return []
    return [t.model_dump(mode="json") for t in engine.platform_registry.list_tenants()]


@router.post("/tenants/{tenant_id}/workspaces", response_model=TenantWorkspace)
def create_workspace(
    tenant_id: str,
    request: CreateWorkspaceRequest,
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> dict[str, Any]:
    if principal.tenant_id != tenant_id and principal.principal_type != "platform_operator":
        raise HTTPException(status_code=403, detail="cross-tenant access denied")
    try:
        workspace = engine.platform_registry.create_workspace(
            tenant_id=tenant_id,
            workspace_key=request.workspace_key,
            name=request.name,
            environment=request.environment,
            blueprint_version_id=request.blueprint_version_id,
        )
        return workspace.model_dump(mode="json")
    except AgentEngineError as exc:
        raise _handle(exc) from exc


@router.get("/tenants/{tenant_id}/workspaces", response_model=list[TenantWorkspace])
def list_workspaces(
    tenant_id: str,
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> list[dict[str, Any]]:
    if principal.tenant_id != tenant_id and principal.principal_type != "platform_operator":
        raise HTTPException(status_code=403, detail="cross-tenant access denied")
    return [
        ws.model_dump(mode="json")
        for ws in engine.platform_registry.list_workspaces(tenant_id)
    ]


@router.post(
    "/tenants/{tenant_id}/workspaces/{workspace_id}/identities",
    response_model=IdentityDefinition,
)
def create_identity(
    tenant_id: str,
    workspace_id: str,
    request: CreateIdentityRequest,
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> dict[str, Any]:
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="cross-tenant access denied")
    try:
        definition = engine.platform_registry.create_identity(
            tenant_id=tenant_id,
            tenant_workspace_id=workspace_id,
            key=request.key,
            name=request.name,
            description=request.description,
        )
        return definition.model_dump(mode="json")
    except AgentEngineError as exc:
        raise _handle(exc) from exc


@router.get(
    "/tenants/{tenant_id}/workspaces/{workspace_id}/identities",
    response_model=list[IdentityDefinition],
)
def list_identities(
    tenant_id: str,
    workspace_id: str,
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> list[dict[str, Any]]:
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="cross-tenant access denied")
    return [
        d.model_dump(mode="json")
        for d in engine.platform_registry.list_identities(tenant_id, workspace_id)
    ]


@router.post(
    "/tenants/{tenant_id}/workspaces/{workspace_id}/identities/{definition_id}/versions",
    response_model=IdentityVersion,
)
def create_identity_version(
    tenant_id: str,
    workspace_id: str,
    definition_id: str,
    request: CreateVersionRequest,
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> dict[str, Any]:
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="cross-tenant access denied")
    try:
        version = engine.platform_registry.create_identity_version(
            tenant_id=tenant_id,
            definition_id=definition_id,
            version=request.version,
            model_profile=request.model_profile,
            system_prompt=request.system_prompt,
            skill_bindings=request.skill_bindings,
            tool_bindings=request.tool_bindings,
        )
        return version.model_dump(mode="json")
    except AgentEngineError as exc:
        raise _handle(exc) from exc


@router.post(
    "/tenants/{tenant_id}/workspaces/{workspace_id}/identity-versions/{version_id}/publish",
    response_model=IdentityVersion,
)
def publish_identity_version(
    tenant_id: str,
    workspace_id: str,
    version_id: str,
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> dict[str, Any]:
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="cross-tenant access denied")
    try:
        version = engine.platform_registry.publish_identity_version(tenant_id, version_id)
        engine.platform_registry.append_audit(
            tenant_id=tenant_id,
            actor_principal_id=principal.principal_id,
            action="identity_publish",
            target=version_id,
        )
        return version.model_dump(mode="json")
    except AgentEngineError as exc:
        raise _handle(exc) from exc


@router.post("/tenants/{tenant_id}/workspaces/{workspace_id}/grants", response_model=IdentityGrant)
def create_grant(
    tenant_id: str,
    workspace_id: str,
    request: CreateGrantRequest,
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> dict[str, Any]:
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="cross-tenant access denied")
    try:
        grant = engine.platform_registry.create_grant(
            tenant_id=tenant_id,
            tenant_workspace_id=workspace_id,
            identity_version_id=request.identity_version_id,
            grantee_type=request.grantee_type,
            grantee_id=request.grantee_id,
            granted_by=principal.principal_id,
        )
        engine.platform_registry.append_audit(
            tenant_id=tenant_id,
            actor_principal_id=principal.principal_id,
            action="grant_create",
            target=grant.grant_id,
        )
        return grant.model_dump(mode="json")
    except AgentEngineError as exc:
        raise _handle(exc) from exc


@router.get(
    "/tenants/{tenant_id}/workspaces/{workspace_id}/grants",
    response_model=list[IdentityGrant],
)
def list_grants(
    tenant_id: str,
    workspace_id: str,
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> list[dict[str, Any]]:
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="cross-tenant access denied")
    # Admin listing: all grants in workspace (metadata)
    grants = engine.platform_registry.list_grants_in_workspace(
        tenant_id=tenant_id,
        tenant_workspace_id=workspace_id,
    )
    return [g.model_dump(mode="json") for g in grants]


# --- me ---


@router.get("/me/identities")
def list_my_identities(
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> list[dict[str, Any]]:
    grants = engine.platform_registry.list_grants_for_principal(
        tenant_id=principal.tenant_id,
        principal_id=principal.principal_id,
        group_ids=principal.group_ids,
    )
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for grant in grants:
        try:
            version = engine.platform_registry.get_identity_version(
                principal.tenant_id, grant.identity_version_id
            )
            definition = engine.platform_registry.get_identity(
                principal.tenant_id, version.definition_id
            )
        except AgentEngineError:
            continue
        if version.version_id in seen:
            continue
        seen.add(version.version_id)
        result.append(
            {
                "definition_id": definition.definition_id,
                "key": definition.key,
                "name": definition.name,
                "description": definition.description,
                "identity_version_id": version.version_id,
                "version": version.version,
                "tenant_workspace_id": version.tenant_workspace_id,
            }
        )
    return result


@router.post("/me/identities/{identity_version_id}/sessions")
def create_my_session(
    identity_version_id: str,
    request: CreateSessionRequest | None = None,
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> dict[str, Any]:
    version_id = identity_version_id
    grants = engine.platform_registry.list_grants_for_principal(
        tenant_id=principal.tenant_id,
        principal_id=principal.principal_id,
        group_ids=principal.group_ids,
    )
    if not any(g.identity_version_id == version_id for g in grants):
        raise HTTPException(status_code=403, detail="identity not granted")
    try:
        version = engine.platform_registry.get_identity_version(principal.tenant_id, version_id)
    except AgentEngineError as exc:
        raise _handle(exc) from exc
    session_id = (
        (request.session_id if request else None)
        or f"sess-{version_id}-{principal.principal_id}"
    )
    session = engine.session_store.ensure_session(
        session_id=session_id,
        tenant_id=principal.tenant_id,
        tenant_workspace_id=version.tenant_workspace_id,
        owner_principal_id=principal.principal_id,
        user_id=principal.principal_id,
        identity_id=version.definition_id,
        identity_version_id=version.version_id,
    )
    return session.model_dump(mode="json")


@router.get("/me/sessions")
def list_my_sessions(
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> list[dict[str, Any]]:
    sessions = engine.session_store.list_for_owner(
        owner_principal_id=principal.principal_id,
        tenant_id=principal.tenant_id,
    )
    return [s.model_dump(mode="json") for s in sessions]


@router.get("/me/sessions/{session_id}")
def get_my_session(
    session_id: str,
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> dict[str, Any]:
    try:
        session = engine.session_store.get_for_owner(
            session_id,
            tenant_id=principal.tenant_id,
            owner_principal_id=principal.principal_id,
        )
        return session.model_dump(mode="json")
    except AgentEngineError as exc:
        raise _handle(exc) from exc


@router.get("/me/runs")
def list_my_runs(
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> list[dict[str, Any]]:
    store = engine.run_store
    if hasattr(store, "list_for_owner"):
        runs = store.list_for_owner(
            owner_principal_id=principal.principal_id,
            tenant_id=principal.tenant_id,
        )
    else:
        runs = []
        for run in store.list_runs():
            ctx = run.context
            if ctx is None:
                continue
            owner = ctx.owner_principal_id or ctx.user_id
            if owner != principal.principal_id:
                continue
            if ctx.tenant_id not in (None, principal.tenant_id):
                continue
            runs.append(run)
    return [run.model_dump(mode="json") for run in runs]


@router.get("/me/runs/{run_id}")
def get_my_run(
    run_id: str,
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> dict[str, Any]:
    try:
        run = engine.run_store.get(run_id)
    except AgentEngineError as exc:
        raise _handle(exc) from exc
    ctx = run.context
    owner = (ctx.owner_principal_id or ctx.user_id) if ctx else None
    tenant = ctx.tenant_id if ctx else None
    if owner != principal.principal_id or (tenant not in (None, principal.tenant_id)):
        raise HTTPException(
            status_code=404,
            detail={"code": "RUN_NOT_FOUND", "message": "Run not found"},
        )
    return run.model_dump(mode="json")


@router.get("/me/artifacts")
def list_my_artifacts(
    path: str = Query(default=""),
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> dict[str, Any]:
    items = engine.platform_registry.list_artifacts_for_owner(
        tenant_id=principal.tenant_id,
        owner_principal_id=principal.principal_id,
        path_prefix=path,
    )
    # When path is empty, list top-level identity folders from full owner tree.
    all_items = engine.platform_registry.list_artifacts_for_owner(
        tenant_id=principal.tenant_id,
        owner_principal_id=principal.principal_id,
    )
    node = list_directory_nodes(all_items if not path else items, path)
    return node


@router.get("/me/artifacts/{artifact_id}", response_model=ArtifactMeta)
def get_my_artifact(
    artifact_id: str,
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> dict[str, Any]:
    try:
        meta = engine.platform_registry.get_artifact_for_owner(
            artifact_id,
            tenant_id=principal.tenant_id,
            owner_principal_id=principal.principal_id,
        )
        return meta.model_dump(mode="json")
    except AgentEngineError as exc:
        raise _handle(exc) from exc


@router.get("/me/artifacts/{artifact_id}/download")
def download_my_artifact(
    artifact_id: str,
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> dict[str, Any]:
    try:
        meta = engine.platform_registry.get_artifact_for_owner(
            artifact_id,
            tenant_id=principal.tenant_id,
            owner_principal_id=principal.principal_id,
        )
        # Return metadata + object key as signed-url placeholder for 1.0.1.
        return {
            "artifact_id": meta.artifact_id,
            "object_key": meta.object_key,
            "media_type": meta.media_type,
            "download_token": f"local:{meta.artifact_id}",
        }
    except AgentEngineError as exc:
        raise _handle(exc) from exc


# --- admin artifacts ---


@router.get(
    "/tenants/{tenant_id}/workspaces/{workspace_id}/artifacts",
    response_model=list[ArtifactMeta],
)
def list_admin_artifacts(
    tenant_id: str,
    workspace_id: str,
    owner: str | None = Query(default=None),
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> list[dict[str, Any]]:
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="cross-tenant access denied")
    items = engine.platform_registry.list_artifacts_admin(
        tenant_id=tenant_id,
        tenant_workspace_id=workspace_id,
        owner_principal_id=owner,
    )
    return [item.model_dump(mode="json") for item in items]


@router.post(
    "/tenants/{tenant_id}/workspaces/{workspace_id}/artifact-elevations",
    response_model=ArtifactElevation,
)
def elevate_artifact(
    tenant_id: str,
    workspace_id: str,
    request: ElevateArtifactRequest,
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> dict[str, Any]:
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="cross-tenant access denied")
    if request.owner_principal_id == principal.principal_id:
        raise HTTPException(status_code=400, detail="elevation not needed for own artifacts")
    try:
        elevation = engine.platform_registry.create_elevation(
            tenant_id=tenant_id,
            tenant_workspace_id=workspace_id,
            actor_principal_id=principal.principal_id,
            owner_principal_id=request.owner_principal_id,
            path_prefix=request.path_prefix,
            reason=request.reason,
        )
        return elevation.model_dump(mode="json")
    except AgentEngineError as exc:
        raise _handle(exc) from exc


@router.get("/tenants/{tenant_id}/audit-events", response_model=list[AuditEvent])
def list_audit_events(
    tenant_id: str,
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> list[dict[str, Any]]:
    if principal.tenant_id != tenant_id and principal.principal_type != "platform_operator":
        raise HTTPException(status_code=403, detail="cross-tenant access denied")
    return [a.model_dump(mode="json") for a in engine.platform_registry.list_audits(tenant_id)]


# helper for tests / tooling to register artifacts
@router.post("/tenants/{tenant_id}/workspaces/{workspace_id}/artifacts")
def register_admin_artifact(
    tenant_id: str,
    workspace_id: str,
    request: RegisterArtifactRequest,
    principal: Principal = Depends(get_principal),
    engine: SkillEngine = Depends(get_engine),
) -> dict[str, Any]:
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="cross-tenant access denied")
    try:
        meta = build_artifact_meta(
            tenant_id=tenant_id,
            tenant_workspace_id=workspace_id,
            owner_principal_id=principal.principal_id,
            logical_path=request.logical_path,
            run_id=request.run_id,
            session_id=request.session_id,
            identity_key=request.identity_key,
            media_type=request.media_type,
            size_bytes=request.size_bytes,
            object_key=request.object_key,
        )
        engine.platform_registry.register_artifact(meta)
        return meta.model_dump(mode="json")
    except AgentEngineError as exc:
        raise _handle(exc) from exc
