"""Tests for tenant/identity registry, ownership isolation, and artifact catalog API."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.domain.platform import build_owner_artifact_path
from app.engine import SkillEngine
from app.infrastructure.persistence import (
    InMemoryAgentSessionStore,
    InMemoryPlatformRegistryStore,
    build_artifact_meta,
)
from app.interfaces.http.main import create_app


def _client(tmp_path: Path) -> TestClient:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path / "artifacts")
    engine.platform_registry = InMemoryPlatformRegistryStore()
    engine.session_store = InMemoryAgentSessionStore()
    return TestClient(create_app(engine))


def _ws(tenant: str, workspace_id: str) -> str:
    return f"/api/v1/tenants/{tenant}/workspaces/{workspace_id}"


def _headers(
    tenant: str, principal: str, roles: str = "ws_admin", groups: str = ""
) -> dict[str, str]:
    return {
        "X-Tenant-Id": tenant,
        "X-Principal-Id": principal,
        "X-Principal-Type": "user",
        "X-Workspace-Roles": roles,
        "X-Group-Ids": groups,
    }


def _bootstrap(client: TestClient, tenant: str = "t1", admin: str = "admin1") -> dict[str, str]:
    h = _headers(tenant, admin, roles="tenant_admin,ws_admin")
    tenant_resp = client.post(
        "/api/v1/tenants",
        json={"tenant_id": tenant, "name": "Acme"},
        headers=h,
    )
    assert tenant_resp.status_code == 200, tenant_resp.text
    ws_resp = client.post(
        f"/api/v1/tenants/{tenant}/workspaces",
        json={"workspace_key": "content", "name": "内容工作区"},
        headers=h,
    )
    assert ws_resp.status_code == 200, ws_resp.text
    workspace_id = ws_resp.json()["tenant_workspace_id"]
    id_resp = client.post(
        f"/api/v1/tenants/{tenant}/workspaces/{workspace_id}/identities",
        json={"key": "plan-helper", "name": "发展规划助手"},
        headers=h,
    )
    assert id_resp.status_code == 200, id_resp.text
    definition_id = id_resp.json()["definition_id"]
    ver_resp = client.post(
        f"{_ws(tenant, workspace_id)}/identities/{definition_id}/versions",
        json={"version": "1.0.0", "model_profile": "mock", "system_prompt": "help"},
        headers=h,
    )
    assert ver_resp.status_code == 200, ver_resp.text
    version_id = ver_resp.json()["version_id"]
    pub_resp = client.post(
        f"{_ws(tenant, workspace_id)}/identity-versions/{version_id}/publish",
        headers=h,
    )
    assert pub_resp.status_code == 200, pub_resp.text
    return {
        "tenant": tenant,
        "workspace_id": workspace_id,
        "definition_id": definition_id,
        "version_id": version_id,
        "admin": admin,
    }


def test_create_tenant_workspace_identity_publish_and_grant(tmp_path: Path) -> None:
    client = _client(tmp_path)
    ctx = _bootstrap(client)
    h = _headers(ctx["tenant"], ctx["admin"], roles="ws_admin")
    grant_resp = client.post(
        f"{_ws(ctx['tenant'], ctx['workspace_id'])}/grants",
        json={
            "identity_version_id": ctx["version_id"],
            "grantee_type": "group",
            "grantee_id": "all-staff",
        },
        headers=h,
    )
    assert grant_resp.status_code == 200, grant_resp.text

    user_h = _headers(ctx["tenant"], "u_alice", roles="end_user", groups="all-staff")
    mine = client.get("/api/v1/me/identities", headers=user_h)
    assert mine.status_code == 200
    items = mine.json()
    assert len(items) == 1
    assert items[0]["key"] == "plan-helper"


def test_grant_requires_published_version(tmp_path: Path) -> None:
    client = _client(tmp_path)
    ctx = _bootstrap(client)
    h = _headers(ctx["tenant"], ctx["admin"])
    # create another draft version
    ver = client.post(
        f"{_ws(ctx['tenant'], ctx['workspace_id'])}/identities/{ctx['definition_id']}/versions",
        json={"version": "1.1.0"},
        headers=h,
    )
    draft_id = ver.json()["version_id"]
    grant = client.post(
        f"{_ws(ctx['tenant'], ctx['workspace_id'])}/grants",
        json={
            "identity_version_id": draft_id,
            "grantee_type": "user",
            "grantee_id": "u_alice",
        },
        headers=h,
    )
    assert grant.status_code == 400
    assert grant.json()["detail"]["code"] == "GRANT_REQUIRES_PUBLISHED_VERSION"


def test_identity_version_immutable_after_publish(tmp_path: Path) -> None:
    client = _client(tmp_path)
    ctx = _bootstrap(client)
    h = _headers(ctx["tenant"], ctx["admin"])
    engine: SkillEngine = client.app.state.engine
    ver = client.post(
        f"{_ws(ctx['tenant'], ctx['workspace_id'])}/identities/{ctx['definition_id']}/versions",
        json={"version": "2.0.0", "system_prompt": "v1"},
        headers=h,
    )
    draft_id = ver.json()["version_id"]
    published = client.post(
        f"{_ws(ctx['tenant'], ctx['workspace_id'])}/identity-versions/{draft_id}/publish",
        headers=h,
    )
    assert published.status_code == 200
    try:
        engine.platform_registry.update_identity_version_draft(
            ctx["tenant"], draft_id, system_prompt="changed"
        )
        raise AssertionError("expected immutability error")
    except Exception as exc:  # noqa: BLE001
        assert getattr(exc, "code", "") == "IDENTITY_VERSION_IMMUTABLE"


def test_session_owner_immutable_and_isolation(tmp_path: Path) -> None:
    client = _client(tmp_path)
    ctx = _bootstrap(client)
    admin_h = _headers(ctx["tenant"], ctx["admin"])
    client.post(
        f"{_ws(ctx['tenant'], ctx['workspace_id'])}/grants",
        json={
            "identity_version_id": ctx["version_id"],
            "grantee_type": "user",
            "grantee_id": "u_alice",
        },
        headers=admin_h,
    )
    client.post(
        f"{_ws(ctx['tenant'], ctx['workspace_id'])}/grants",
        json={
            "identity_version_id": ctx["version_id"],
            "grantee_type": "user",
            "grantee_id": "u_bob",
        },
        headers=admin_h,
    )
    alice = _headers(ctx["tenant"], "u_alice")
    bob = _headers(ctx["tenant"], "u_bob")
    created = client.post(
        f"/api/v1/me/identities/{ctx['version_id']}/sessions",
        json={"session_id": "s-shared"},
        headers=alice,
    )
    assert created.status_code == 200
    assert created.json()["owner_principal_id"] == "u_alice"

    # owner immutable
    store = client.app.state.engine.session_store
    again = store.ensure_session("s-shared", user_id="u_bob", owner_principal_id="u_bob")
    assert again.owner_principal_id == "u_alice"
    assert again.user_id == "u_alice"

    alice_get = client.get("/api/v1/me/sessions/s-shared", headers=alice)
    assert alice_get.status_code == 200
    bob_get = client.get("/api/v1/me/sessions/s-shared", headers=bob)
    assert bob_get.status_code == 404

    # principal ignores forged user_id query
    forged = client.get("/api/v1/me/sessions/s-shared?user_id=u_alice", headers=bob)
    assert forged.status_code == 404


def test_me_requires_principal_headers(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/v1/me/identities")
    assert resp.status_code == 401


def test_artifact_catalog_owner_isolation_and_elevation(tmp_path: Path) -> None:
    client = _client(tmp_path)
    ctx = _bootstrap(client)
    admin_h = _headers(ctx["tenant"], ctx["admin"])
    # register alice artifact via platform store for isolation assertions
    engine: SkillEngine = client.app.state.engine
    alice_meta = build_artifact_meta(
        tenant_id=ctx["tenant"],
        tenant_workspace_id=ctx["workspace_id"],
        owner_principal_id="u_alice",
        logical_path="发展规划助手/2026-07-28/run_1/plan.json",
        media_type="application/json",
        size_bytes=12,
        run_id="run_1",
    )
    engine.platform_registry.register_artifact(alice_meta)

    bob_h = _headers(ctx["tenant"], "u_bob")
    alice_h = _headers(ctx["tenant"], "u_alice")

    # alice lists own root
    root = client.get("/api/v1/me/artifacts?path=/", headers=alice_h)
    assert root.status_code == 200
    assert "发展规划助手" in root.json()["folders"]

    # alice can get artifact
    got = client.get(f"/api/v1/me/artifacts/{alice_meta.artifact_id}", headers=alice_h)
    assert got.status_code == 200

    # bob cannot
    bob_get = client.get(f"/api/v1/me/artifacts/{alice_meta.artifact_id}", headers=bob_h)
    assert bob_get.status_code == 404
    bob_list = client.get("/api/v1/me/artifacts?path=/", headers=bob_h)
    assert bob_list.json()["folders"] == []

    # admin cannot download without elevation
    admin_alice = client.get(f"/api/v1/me/artifacts/{alice_meta.artifact_id}", headers=admin_h)
    assert admin_alice.status_code == 404  # admin principal is admin1, not owner

    # elevation requires reason
    elev_bad = client.post(
        f"/api/v1/tenants/{ctx['tenant']}/workspaces/{ctx['workspace_id']}/artifact-elevations",
        json={"owner_principal_id": "u_alice", "reason": "  "},
        headers=admin_h,
    )
    assert elev_bad.status_code == 400

    elev = client.post(
        f"/api/v1/tenants/{ctx['tenant']}/workspaces/{ctx['workspace_id']}/artifact-elevations",
        json={
            "owner_principal_id": "u_alice",
            "reason": "INC-101 investigate",
            "path_prefix": "发展规划助手",
        },
        headers=admin_h,
    )
    assert elev.status_code == 200

    # elevated admin can list alice artifacts via admin endpoint
    admin_list = client.get(
        f"/api/v1/tenants/{ctx['tenant']}/workspaces/{ctx['workspace_id']}/artifacts?owner=u_alice",
        headers=admin_h,
    )
    assert admin_list.status_code == 200
    assert len(admin_list.json()) == 1

    audits = client.get(f"/api/v1/tenants/{ctx['tenant']}/audit-events", headers=admin_h)
    assert audits.status_code == 200
    actions = {item["action"] for item in audits.json()}
    assert "elevate_artifact_read" in actions
    assert "identity_publish" in actions
    assert "grant_create" in actions or "identity_publish" in actions


def test_build_owner_artifact_path() -> None:
    path = build_owner_artifact_path("t1", "ws1", "u1", "agent/run/file.json")
    assert path == "tenants/t1/workspaces/ws1/users/u1/agent/run/file.json"
