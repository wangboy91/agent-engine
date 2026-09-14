"""Engine no longer owns login; account is a separate service."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.engine import SkillEngine
from app.interfaces.http.main import create_app


def test_engine_auth_login_removed(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path / "artifacts")
    client = TestClient(create_app(engine))
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "ws.admin", "password": "WsAdmin@123"},
    )
    # login moved to account-service
    assert resp.status_code == 404


def test_engine_accepts_header_principal(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path / "artifacts")
    client = TestClient(create_app(engine))
    headers = {
        "X-Tenant-Id": "t-demo",
        "X-Principal-Id": "u_alice",
        "X-Workspace-Roles": "end_user",
    }
    resp = client.get("/api/v1/me/identities", headers=headers)
    assert resp.status_code == 200
