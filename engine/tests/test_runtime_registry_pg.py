"""PostgreSQL Session/Run/Trace runtime store tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from app.domain.execution import RunContext, RunResult
from app.infrastructure.config.database import runtime_database_url
from app.infrastructure.persistence.runtime_registry_pg import (
    PostgresAgentSessionStore,
    PostgresRunStore,
    PostgresTraceStore,
)


@pytest.fixture()
def runtime_engine():
    url = runtime_database_url()
    if not url:
        pytest.skip("runtime database url not set")
    try:
        probe = create_engine(url)
        with probe.connect() as conn:
            conn.execute(text("SELECT 1"))
        probe.dispose()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"runtime PostgreSQL unavailable: {exc}")
    return create_engine(url, pool_pre_ping=True, future=True)


def test_pg_session_owner_immutable(runtime_engine) -> None:
    store = PostgresAgentSessionStore(runtime_engine)
    sid = f"s-{uuid4().hex[:12]}"
    created = store.ensure_session(
        sid,
        user_id="u_alice",
        owner_principal_id="u_alice",
        tenant_id="t1",
        tenant_workspace_id="ws1",
        identity_id="id1",
    )
    assert created.owner_principal_id == "u_alice"

    again = store.ensure_session(sid, user_id="u_bob", owner_principal_id="u_bob")
    assert again.owner_principal_id == "u_alice"
    assert again.user_id == "u_alice"

    with pytest.raises(Exception) as exc:  # noqa: BLE001
        store.get_for_owner(sid, owner_principal_id="u_bob", tenant_id="t1")
    assert getattr(exc.value, "code", "") == "SESSION_NOT_FOUND"

    ok = store.get_for_owner(sid, owner_principal_id="u_alice", tenant_id="t1")
    assert ok.session_id == sid

    mine = store.list_for_owner(owner_principal_id="u_alice", tenant_id="t1")
    assert any(item.session_id == sid for item in mine)


def test_pg_run_owner_filter_and_trace_persist(runtime_engine) -> None:
    run_store = PostgresRunStore(runtime_engine)
    trace_store = PostgresTraceStore(runtime_engine)

    rid = f"run-{uuid4().hex[:12]}"
    run = RunResult(
        run_id=rid,
        status="succeeded",
        skill_id="demo-skill",
        context=RunContext(
            tenant_id="t1",
            tenant_workspace_id="ws1",
            owner_principal_id="u_alice",
            user_id="u_alice",
            identity_id="id1",
            identity_version_id="ver1",
        ),
        output={"ok": True},
    )
    run_store.save(run)

    loaded = run_store.get(rid)
    assert loaded.context is not None
    assert loaded.context.owner_principal_id == "u_alice"

    mine = run_store.list_for_owner(owner_principal_id="u_alice", tenant_id="t1")
    assert any(item.run_id == rid for item in mine)
    others = run_store.list_for_owner(owner_principal_id="u_bob", tenant_id="t1")
    assert all(item.run_id != rid for item in others)

    trace_store.record(rid, "skill_started", "started", {"skill_id": "demo-skill"})
    trace_store.record(rid, "skill_completed", "done", {"skill_id": "demo-skill"})
    events = trace_store.list_events(rid)
    assert len(events) >= 2
    assert events[0].type == "skill_started"
    assert events[1].type == "skill_completed"
