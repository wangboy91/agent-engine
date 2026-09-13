"""PostgreSQL stores for AgentSession / Run / Trace (runtime data plane).

Tables live on the runtime database URL (see ``database.runtime_database_url``).
In 1.0.1 this usually equals the primary platform DB; the split is config-reserved.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Index, Integer, String, Text, delete, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.domain.agent import AgentMessage, AgentSession, AgentTurn
from app.domain.errors import AgentEngineError
from app.domain.execution import RunResult, TraceEvent
from app.infrastructure.config.database import (
    create_engine_from_url,
    runtime_database_url,
)


class RuntimeBase(DeclarativeBase):
    pass


class SessionRow(RuntimeBase):
    __tablename__ = "runtime_agent_sessions"

    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    identity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    tenant_workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    owner_principal_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    identity_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RunRow(RuntimeBase):
    __tablename__ = "runtime_runs"

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    skill_id: Mapped[str] = mapped_column(String(128), index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    tenant_workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    owner_principal_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    identity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TraceEventRow(RuntimeBase):
    __tablename__ = "runtime_trace_events"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    seq: Mapped[int] = mapped_column(Integer, default=0)


Index("ix_runtime_trace_run_ts", TraceEventRow.run_id, TraceEventRow.timestamp)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class _SessionMixin:
    """Shared session factory helpers."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        RuntimeBase.metadata.create_all(self.engine)
        self._factory = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)

    def _session(self) -> Session:
        return self._factory()


class PostgresAgentSessionStore(_SessionMixin):
    def get(self, session_id: str) -> AgentSession:
        with self._session() as db:
            row = db.get(SessionRow, session_id)
            if row is None:
                raise AgentEngineError("SESSION_NOT_FOUND", f"Session not found: {session_id}")
            return self._to_model(row)

    def list_sessions(
        self,
        workspace_id: str | None = None,
        identity_id: str | None = None,
    ) -> list[AgentSession]:
        with self._session() as db:
            stmt = select(SessionRow)
            if workspace_id is not None:
                stmt = stmt.where(SessionRow.workspace_id == workspace_id)
            if identity_id is not None:
                stmt = stmt.where(SessionRow.identity_id == identity_id)
            rows = db.scalars(stmt).all()
            return [self._to_model(row) for row in rows]

    def ensure_session(
        self,
        session_id: str,
        workspace_id: str | None = None,
        identity_id: str | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
        tenant_workspace_id: str | None = None,
        owner_principal_id: str | None = None,
        identity_version_id: str | None = None,
    ) -> AgentSession:
        with self._session() as db:
            row = db.get(SessionRow, session_id)
            now = _utc_now()
            if row is not None:
                # Owner fields immutable after create.
                if workspace_id is not None:
                    row.workspace_id = workspace_id
                if identity_id is not None:
                    row.identity_id = identity_id
                row.updated_at = now
                payload = dict(row.payload or {})
                payload["messages"] = payload.get("messages") or []
                payload["turns"] = payload.get("turns") or []
                row.payload = payload
                db.commit()
                return self._to_model(row)

            owner = owner_principal_id or user_id
            model = AgentSession(
                session_id=session_id,
                workspace_id=workspace_id,
                identity_id=identity_id,
                user_id=user_id or owner,
                tenant_id=tenant_id,
                tenant_workspace_id=tenant_workspace_id,
                owner_principal_id=owner,
                identity_version_id=identity_version_id,
                created_at=now,
                updated_at=now,
            )
            db.add(self._from_model(model))
            db.commit()
            return model

    def get_for_owner(
        self,
        session_id: str,
        *,
        tenant_id: str | None = None,
        tenant_workspace_id: str | None = None,
        owner_principal_id: str,
    ) -> AgentSession:
        session = self.get(session_id)
        if tenant_id is not None and session.tenant_id not in (None, tenant_id):
            raise AgentEngineError("SESSION_NOT_FOUND", f"Session not found: {session_id}")
        if (
            tenant_workspace_id is not None
            and session.tenant_workspace_id not in (None, tenant_workspace_id)
        ):
            raise AgentEngineError("SESSION_NOT_FOUND", f"Session not found: {session_id}")
        owner = session.owner_principal_id or session.user_id
        if owner is not None and owner != owner_principal_id:
            raise AgentEngineError("SESSION_NOT_FOUND", f"Session not found: {session_id}")
        return session

    def list_for_owner(
        self,
        *,
        owner_principal_id: str,
        tenant_id: str | None = None,
        tenant_workspace_id: str | None = None,
        identity_id: str | None = None,
    ) -> list[AgentSession]:
        with self._session() as db:
            stmt = select(SessionRow).where(
                (SessionRow.owner_principal_id == owner_principal_id)
                | (
                    (SessionRow.owner_principal_id.is_(None))
                    & (SessionRow.user_id == owner_principal_id)
                )
            )
            if tenant_id is not None:
                stmt = stmt.where(
                    (SessionRow.tenant_id == tenant_id) | (SessionRow.tenant_id.is_(None))
                )
            if tenant_workspace_id is not None:
                stmt = stmt.where(
                    (SessionRow.tenant_workspace_id == tenant_workspace_id)
                    | (SessionRow.tenant_workspace_id.is_(None))
                )
            if identity_id is not None:
                stmt = stmt.where(SessionRow.identity_id == identity_id)
            rows = db.scalars(stmt).all()
            return [self._to_model(row) for row in rows]

    def append_message(self, session_id: str, message: AgentMessage) -> AgentSession:
        with self._session() as db:
            row = db.get(SessionRow, session_id)
            if row is None:
                raise AgentEngineError("SESSION_NOT_FOUND", f"Session not found: {session_id}")
            payload = dict(row.payload or {})
            messages = list(payload.get("messages") or [])
            messages.append(message.model_dump(mode="json"))
            payload["messages"] = messages
            row.payload = payload
            row.updated_at = _utc_now()
            db.commit()
            return self._to_model(row)

    def append_turn(self, session_id: str, turn: AgentTurn) -> AgentSession:
        with self._session() as db:
            row = db.get(SessionRow, session_id)
            if row is None:
                raise AgentEngineError("SESSION_NOT_FOUND", f"Session not found: {session_id}")
            payload = dict(row.payload or {})
            turns = list(payload.get("turns") or [])
            turns.append(turn.model_dump(mode="json"))
            payload["turns"] = turns
            row.payload = payload
            row.updated_at = _utc_now()
            db.commit()
            return self._to_model(row)

    def _from_model(self, session: AgentSession) -> SessionRow:
        payload: dict[str, Any] = {
            "messages": [m.model_dump(mode="json") for m in session.messages],
            "turns": [t.model_dump(mode="json") for t in session.turns],
        }
        return SessionRow(
            session_id=session.session_id,
            workspace_id=session.workspace_id,
            identity_id=session.identity_id,
            user_id=session.user_id,
            tenant_id=session.tenant_id,
            tenant_workspace_id=session.tenant_workspace_id,
            owner_principal_id=session.owner_principal_id,
            identity_version_id=session.identity_version_id,
            payload=payload,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    def _to_model(self, row: SessionRow) -> AgentSession:
        payload = row.payload or {}
        messages = [AgentMessage.model_validate(item) for item in payload.get("messages") or []]
        turns = [AgentTurn.model_validate(item) for item in payload.get("turns") or []]
        return AgentSession(
            session_id=row.session_id,
            workspace_id=row.workspace_id,
            identity_id=row.identity_id,
            user_id=row.user_id,
            tenant_id=row.tenant_id,
            tenant_workspace_id=row.tenant_workspace_id,
            owner_principal_id=row.owner_principal_id,
            identity_version_id=row.identity_version_id,
            messages=messages,
            turns=turns,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class PostgresRunStore(_SessionMixin):
    def save(self, run: RunResult) -> RunResult:
        ctx = run.context
        with self._session() as db:
            row = db.get(RunRow, run.run_id)
            values = {
                "status": run.status,
                "skill_id": run.skill_id,
                "tenant_id": ctx.tenant_id if ctx else None,
                "tenant_workspace_id": ctx.tenant_workspace_id if ctx else None,
                "owner_principal_id": (
                    (ctx.owner_principal_id or ctx.user_id) if ctx else None
                ),
                "user_id": ctx.user_id if ctx else None,
                "identity_id": ctx.identity_id if ctx else None,
                "payload": run.model_dump(mode="json"),
                "completed_at": run.completed_at,
            }
            if row is None:
                row = RunRow(
                    run_id=run.run_id,
                    created_at=run.created_at or _utc_now(),
                    **values,
                )
                db.add(row)
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            db.commit()
        return run

    def get(self, run_id: str) -> RunResult:
        with self._session() as db:
            row = db.get(RunRow, run_id)
            if row is None:
                raise AgentEngineError("RUN_NOT_FOUND", f"Run not found: {run_id}")
            return RunResult.model_validate(row.payload)

    def list_runs(self) -> list[RunResult]:
        with self._session() as db:
            rows = db.scalars(select(RunRow)).all()
            return [RunResult.model_validate(row.payload) for row in rows]

    def list_for_owner(
        self,
        *,
        owner_principal_id: str,
        tenant_id: str | None = None,
    ) -> list[RunResult]:
        with self._session() as db:
            stmt = select(RunRow).where(
                (RunRow.owner_principal_id == owner_principal_id)
                | (
                    (RunRow.owner_principal_id.is_(None))
                    & (RunRow.user_id == owner_principal_id)
                )
            )
            if tenant_id is not None:
                stmt = stmt.where(
                    (RunRow.tenant_id == tenant_id) | (RunRow.tenant_id.is_(None))
                )
            rows = db.scalars(stmt).all()
            return [RunResult.model_validate(row.payload) for row in rows]


class PostgresTraceStore(_SessionMixin):
    """Trace store with in-process fan-out plus PostgreSQL persistence."""

    def __init__(self, engine: Engine) -> None:
        super().__init__(engine)
        from app.infrastructure.tracing.trace_store import InMemoryTraceStore

        self._live = InMemoryTraceStore()

    def record(
        self,
        run_id: str,
        event_type: str,
        message: str,
        data: dict[str, object],
    ) -> TraceEvent:
        event = self._live.record(run_id, event_type, message, data)
        with self._session() as db:
            last_seq = db.scalar(
                select(TraceEventRow.seq)
                .where(TraceEventRow.run_id == run_id)
                .order_by(TraceEventRow.seq.desc())
                .limit(1)
            )
            seq = int(last_seq or 0) + 1
            db.add(
                TraceEventRow(
                    id=event.id,
                    run_id=event.run_id,
                    type=event.type,
                    timestamp=event.timestamp,
                    message=event.message,
                    data=event.data,
                    seq=seq,
                )
            )
            db.commit()
        return event

    def list_events(self, run_id: str) -> list[TraceEvent]:
        with self._session() as db:
            rows = db.scalars(
                select(TraceEventRow)
                .where(TraceEventRow.run_id == run_id)
                .order_by(TraceEventRow.seq.asc())
            ).all()
            if rows:
                return [
                    TraceEvent(
                        id=row.id,
                        run_id=row.run_id,
                        type=row.type,
                        timestamp=row.timestamp,
                        message=row.message,
                        data=row.data,
                    )
                    for row in rows
                ]
        return self._live.list_events(run_id)

    def subscribe(
        self,
        workspace_id: str | None = None,
        identity_id: str | None = None,
    ) -> AbstractAsyncContextManager[Any]:
        # Delegate to in-memory async context manager for SSE/WS fan-out.
        return self._live.subscribe(workspace_id=workspace_id, identity_id=identity_id)

    def clear(self) -> None:
        with self._session() as db:
            db.execute(delete(TraceEventRow))
            db.commit()


def create_runtime_engine(engine: Engine | None = None) -> Engine | None:
    if engine is not None:
        return engine
    url = runtime_database_url()
    if not url:
        return None
    return create_engine_from_url(url)


def create_postgres_session_store(engine: Engine) -> PostgresAgentSessionStore:
    return PostgresAgentSessionStore(engine)


def create_postgres_run_store(engine: Engine) -> PostgresRunStore:
    return PostgresRunStore(engine)


def create_postgres_trace_store(engine: Engine) -> PostgresTraceStore:
    return PostgresTraceStore(engine)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
