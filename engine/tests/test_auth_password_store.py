"""Password hashing + auth store tests (no plaintext in DB)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from app.application.platform.passwords import hash_password, verify_password
from app.domain.errors import AgentEngineError
from app.infrastructure.config.database import primary_database_url
from app.infrastructure.persistence.auth_store_pg import PostgresAuthStore


def test_password_hash_roundtrip_and_not_plaintext() -> None:
    encoded = hash_password("Secret@12345")
    assert "Secret@12345" not in encoded
    assert encoded.startswith("pbkdf2_sha256$")
    assert verify_password("Secret@12345", encoded)
    assert not verify_password("Secret@12346", encoded)


def test_password_min_length() -> None:
    with pytest.raises(ValueError):
        hash_password("short")


@pytest.fixture()
def auth_store() -> PostgresAuthStore:
    url = primary_database_url()
    if not url:
        pytest.skip("no database url")
    try:
        probe = create_engine(url)
        with probe.connect() as conn:
            conn.execute(text("SELECT 1"))
        probe.dispose()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"pg unavailable: {exc}")
    return PostgresAuthStore(create_engine(url, pool_pre_ping=True, future=True))


def test_pg_auth_create_login_change_password(auth_store: PostgresAuthStore) -> None:
    suffix = __import__("uuid").uuid4().hex[:8]
    username = f"pytest.user.change.{suffix}"
    profile = auth_store.create_user(
        username=username,
        password="OldPass@123",
        tenant_id="t-demo",
        principal_id=f"u_pytest_{suffix}",
        display_name="测试用户",
        workspace_roles=["end_user"],
        group_ids=["all-staff"],
    )
    assert profile["username"] == username
    assert "password" not in profile
    assert "password_hash" not in profile

    ok = auth_store.authenticate(username, "OldPass@123")
    assert ok["user_id"] == f"u_pytest_{suffix}"

    with pytest.raises(Exception) as bad:
        auth_store.authenticate(username, "WrongPass@1")
    assert getattr(bad.value, "code", "") == "INVALID_CREDENTIALS"

    auth_store.change_password(
        username=username, old_password="OldPass@123", new_password="NewPass@456"
    )
    auth_store.authenticate(username, "NewPass@456")
    with pytest.raises(AgentEngineError):
        auth_store.authenticate(username, "OldPass@123")

    # hash not plaintext in table
    url = primary_database_url()
    assert url
    eng = create_engine(url)
    with eng.connect() as conn:
        row = conn.execute(
            text("SELECT password_hash FROM auth_users WHERE username=:u"),
            {"u": username},
        ).one()
    assert "NewPass@456" not in row[0]
    assert "OldPass@123" not in row[0]
