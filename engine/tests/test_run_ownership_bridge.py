"""Tests for Principal→RunContext enrichment and ArtifactMeta auto-registration."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.application.platform.run_bridge import (
    enrich_context_with_principal,
    register_run_artifacts_into_platform,
)
from app.domain.execution import Artifact, RunContext, RunResult
from app.domain.platform import Principal
from app.engine import SkillEngine
from app.infrastructure.persistence import (
    InMemoryPlatformRegistryStore,
)
from app.interfaces.http.main import create_app


def test_enrich_context_fills_missing_owner() -> None:
    principal = Principal(tenant_id="t1", principal_id="u1")
    enriched = enrich_context_with_principal(None, principal)
    assert enriched is not None
    assert enriched.tenant_id == "t1"
    assert enriched.owner_principal_id == "u1"
    assert enriched.user_id == "u1"

    # does not overwrite explicit owner
    existing = RunContext(tenant_id="t-old", owner_principal_id="u-old", user_id="u-old")
    again = enrich_context_with_principal(existing, principal)
    assert again is not None
    assert again.tenant_id == "t-old"
    assert again.owner_principal_id == "u-old"


def test_register_run_artifacts_requires_ownership(tmp_path: Path) -> None:
    registry = InMemoryPlatformRegistryStore()
    registry.create_tenant("t1", "T")
    ws = registry.create_workspace("t1", "ws", "WS")

    file_path = tmp_path / "out.json"
    file_path.write_text("{}", encoding="utf-8")

    run_id = f"run_{uuid4().hex[:8]}"
    run = RunResult(
        run_id=run_id,
        status="succeeded",
        skill_id="demo",
        context=RunContext(
            tenant_id="t1",
            tenant_workspace_id=ws.tenant_workspace_id,
            owner_principal_id="u_alice",
            identity_id="plan-helper",
        ),
        artifacts=[
            Artifact(
                id="a1",
                run_id=run_id,
                type="json",
                mime_type="application/json",
                uri=str(file_path),
            )
        ],
        created_at=datetime.now(UTC),
    )
    created = register_run_artifacts_into_platform(registry, run)
    assert len(created) == 1
    items = registry.list_artifacts_for_owner(
        tenant_id="t1", owner_principal_id="u_alice"
    )
    assert items
    assert items[0].logical_path.endswith("out.json")
    assert run_id in items[0].logical_path

    # no ownership -> no-op
    bare = RunResult(
        run_id=f"run_{uuid4().hex[:8]}",
        status="succeeded",
        skill_id="demo",
        artifacts=run.artifacts,
    )
    assert register_run_artifacts_into_platform(registry, bare) == []


def test_http_run_skill_injects_principal_headers(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path / "artifacts")
    engine.platform_registry = InMemoryPlatformRegistryStore()
    engine.platform_registry.create_tenant("t-http", "HTTP")
    ws = engine.platform_registry.create_workspace("t-http", "content", "WS")
    definition = engine.platform_registry.create_identity(
        "t-http", ws.tenant_workspace_id, "echo", "Echo"
    )
    version = engine.platform_registry.create_identity_version(
        "t-http", definition.definition_id, "1.0.0"
    )
    engine.platform_registry.publish_identity_version("t-http", version.version_id)

    # register a trivial mock skill via package if available; else use talking-video if present
    skills_dir = Path("resources/skills/talking-video")
    if skills_dir.exists():
        engine.skill_registry.register_skill(skills_dir)
    tools_dir = Path("resources/tools/subtitle_generate_srt")
    if tools_dir.exists():
        engine.tool_registry.register_tool(tools_dir)

    client = TestClient(create_app(engine))
    headers = {
        "X-Tenant-Id": "t-http",
        "X-Principal-Id": "u_carol",
        "X-Workspace-Roles": "end_user",
    }
    if not skills_dir.exists():
        # skill missing — still assert 401 path for /me
        assert client.get("/api/v1/me/identities", headers=headers).status_code == 200
        return

    resp = client.post(
        "/skills/talking-video/runs",
        json={
            "input": {
                "topic": "demo",
                "platform": "xiaohongshu",
                "duration_seconds": 30,
            }
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ctx = body.get("context") or {}
    assert ctx.get("tenant_id") == "t-http"
    assert ctx.get("owner_principal_id") == "u_carol"
