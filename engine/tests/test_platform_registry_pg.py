"""PostgreSQL platform registry integration tests.

Skipped automatically when AGENT_ENGINE_DATABASE_URL is not reachable.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

from app.domain.platform import build_artifact_meta
from app.infrastructure.persistence.platform_registry_pg import (
    PostgresPlatformRegistryStore,
    default_database_url,
)


def _database_url() -> str | None:
    return default_database_url()


@pytest.fixture()
def pg_store() -> PostgresPlatformRegistryStore:
    url = _database_url()
    if not url:
        pytest.skip("AGENT_ENGINE_DATABASE_URL not set")
    try:
        probe = create_engine(url)
        with probe.connect() as conn:
            conn.execute(text("SELECT 1"))
        probe.dispose()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    return PostgresPlatformRegistryStore(url)


def test_pg_tenant_identity_grant_artifact_roundtrip(
    pg_store: PostgresPlatformRegistryStore,
) -> None:
    suffix = os.urandom(4).hex()
    tenant_id = f"t-pg-{suffix}"
    tenant = pg_store.create_tenant(tenant_id, "PG Demo")
    assert tenant.tenant_id == tenant_id

    workspace = pg_store.create_workspace(tenant_id, f"ws-{suffix}", "内容工作区")
    definition = pg_store.create_identity(
        tenant_id, workspace.tenant_workspace_id, f"plan-{suffix}", "发展规划助手"
    )
    version = pg_store.create_identity_version(
        tenant_id, definition.definition_id, "1.0.0", system_prompt="help"
    )
    assert version.status == "draft"
    published = pg_store.publish_identity_version(tenant_id, version.version_id)
    assert published.status == "published"
    assert published.published_at is not None

    draft = pg_store.create_identity_version(tenant_id, definition.definition_id, "1.1.0")
    with pytest.raises(Exception) as exc:  # noqa: BLE001
        pg_store.create_grant(
            tenant_id,
            workspace.tenant_workspace_id,
            draft.version_id,
            "user",
            "u_alice",
            "admin",
        )
    assert getattr(exc.value, "code", "") == "GRANT_REQUIRES_PUBLISHED_VERSION"

    grant = pg_store.create_grant(
        tenant_id,
        workspace.tenant_workspace_id,
        published.version_id,
        "user",
        "u_alice",
        "admin",
    )
    listed = pg_store.list_grants_for_principal(tenant_id, "u_alice")
    assert any(g.grant_id == grant.grant_id for g in listed)

    meta = build_artifact_meta(
        tenant_id=tenant_id,
        tenant_workspace_id=workspace.tenant_workspace_id,
        owner_principal_id="u_alice",
        logical_path=f"发展规划助手/2026-07-28/run_{suffix}/plan.json",
        media_type="application/json",
        size_bytes=10,
        run_id=f"run_{suffix}",
    )
    pg_store.register_artifact(meta)

    got = pg_store.get_artifact_for_owner(
        meta.artifact_id, tenant_id=tenant_id, owner_principal_id="u_alice"
    )
    assert got.logical_path == meta.logical_path

    with pytest.raises(Exception) as missing:  # noqa: BLE001
        pg_store.get_artifact_for_owner(
            meta.artifact_id, tenant_id=tenant_id, owner_principal_id="u_bob"
        )
    assert getattr(missing.value, "code", "") == "ARTIFACT_NOT_FOUND"

    root = pg_store.list_artifacts_for_owner(tenant_id=tenant_id, owner_principal_id="u_alice")
    assert root
    assert any(item.logical_path.startswith("发展规划助手/") for item in root)

    elev = pg_store.create_elevation(
        tenant_id=tenant_id,
        tenant_workspace_id=workspace.tenant_workspace_id,
        actor_principal_id="admin1",
        owner_principal_id="u_alice",
        path_prefix="发展规划助手",
        reason="INC-1",
    )
    assert elev.reason == "INC-1"
    assert pg_store.has_active_elevation(
        tenant_id=tenant_id,
        actor_principal_id="admin1",
        owner_principal_id="u_alice",
        logical_path=got.logical_path,
    )

    audits = pg_store.list_audits(tenant_id)
    assert any(a.action == "elevate_artifact_read" for a in audits)


def test_pg_duplicate_workspace_key_rejected(pg_store: PostgresPlatformRegistryStore) -> None:
    suffix = os.urandom(4).hex()
    tenant_id = f"t-pg-dup-{suffix}"
    pg_store.create_tenant(tenant_id, "Dup")
    pg_store.create_workspace(tenant_id, "content", "WS1")
    with pytest.raises(Exception) as exc:  # noqa: BLE001
        pg_store.create_workspace(tenant_id, "content", "WS2")
    assert getattr(exc.value, "code", "") == "TENANT_WORKSPACE_ALREADY_EXISTS"
