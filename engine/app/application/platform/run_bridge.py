"""Bridge helpers: Principal → RunContext ownership, and Artifact → ArtifactMeta."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.domain.errors import AgentEngineError
from app.domain.execution import Artifact, RunContext, RunResult
from app.domain.platform import (
    Principal,
    build_artifact_meta,
    normalize_logical_path,
)


def enrich_context_with_principal(
    context: RunContext | None,
    principal: Principal | None,
    *,
    identity_version_id: str | None = None,
) -> RunContext | None:
    """Fill ownership fields on RunContext from Principal when missing.

    Never overwrites an explicit non-empty owner already set by the caller.
    """
    if principal is None:
        return context
    base = context or RunContext()
    updates: dict[str, Any] = {}
    if not base.tenant_id:
        updates["tenant_id"] = principal.tenant_id
    if not base.owner_principal_id:
        updates["owner_principal_id"] = principal.principal_id
    if not base.user_id:
        updates["user_id"] = principal.principal_id
    if identity_version_id and not base.identity_version_id:
        updates["identity_version_id"] = identity_version_id
    if not updates:
        return base
    return base.model_copy(update=updates)


def artifact_logical_path(run: RunResult, artifact: Artifact) -> str:
    """Map a run artifact into owner-relative logical path under identity/date/run."""
    identity = None
    date = (run.created_at.date().isoformat() if run.created_at else None) or "unknown"
    if run.context is not None:
        identity = run.context.identity_id or run.context.identity_version_id
    name = Path(artifact.uri).name if artifact.uri else artifact.id
    parts = [p for p in (identity or run.skill_id, date, run.run_id, name) if p]
    return normalize_logical_path("/".join(parts))


def register_run_artifacts_into_platform(
    platform_registry: Any,
    run: RunResult,
) -> list[str]:
    """Register run artifacts into platform catalog when ownership context exists.

    Returns list of created artifact_ids. No-op when tenant/owner missing or
    platform registry unavailable.
    """
    if platform_registry is None or run.context is None:
        return []
    ctx = run.context
    tenant_id = ctx.tenant_id
    tenant_workspace_id = ctx.tenant_workspace_id
    owner = ctx.owner_principal_id or ctx.user_id
    if not tenant_id or not owner or not tenant_workspace_id:
        return []
    if not run.artifacts:
        return []

    created: list[str] = []
    for artifact in run.artifacts:
        logical = artifact_logical_path(run, artifact)
        try:
            size_bytes = Path(artifact.uri).stat().st_size if artifact.uri else 0
        except OSError:
            size_bytes = 0
        meta = build_artifact_meta(
            tenant_id=tenant_id,
            tenant_workspace_id=tenant_workspace_id,
            owner_principal_id=owner,
            logical_path=logical,
            run_id=run.run_id,
            identity_key=ctx.identity_id,
            media_type=artifact.mime_type,
            size_bytes=size_bytes,
            object_key=artifact.uri,
        )
        try:
            platform_registry.register_artifact(meta)
            created.append(meta.artifact_id)
        except AgentEngineError as exc:
            # Duplicate path or missing workspace: skip without failing the run.
            if exc.code != "ARTIFACT_PATH_ALREADY_EXISTS":
                continue
    return created


def principal_from_headers(headers: Any) -> Principal | None:
    """Build Principal from HTTP headers when present (dev header auth)."""
    tenant = headers.get("X-Tenant-Id")
    principal_id = headers.get("X-Principal-Id")
    if not tenant or not principal_id:
        return None
    roles = [p.strip() for p in (headers.get("X-Workspace-Roles") or "").split(",") if p.strip()]
    groups = [p.strip() for p in (headers.get("X-Group-Ids") or "").split(",") if p.strip()]
    scopes = [p.strip() for p in (headers.get("X-Scopes") or "").split(",") if p.strip()]
    principal_type = headers.get("X-Principal-Type") or "user"
    return Principal(
        tenant_id=tenant,
        principal_id=principal_id,
        principal_type=principal_type,  # type: ignore[arg-type]
        workspace_roles=roles,
        group_ids=groups,
        scopes=scopes,
    )
