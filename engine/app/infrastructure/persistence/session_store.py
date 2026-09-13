"""Agent session store primitives."""

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from app.domain.agent import AgentMessage, AgentSession, AgentTurn
from app.domain.errors import AgentEngineError


class SessionDocument(BaseModel):
    version: int = 1
    sessions: dict[str, AgentSession] = Field(default_factory=dict)


class InMemoryAgentSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, AgentSession] = {}

    def get(self, session_id: str) -> AgentSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise AgentEngineError("SESSION_NOT_FOUND", f"Session not found: {session_id}")
        return session

    def list_sessions(
        self,
        workspace_id: str | None = None,
        identity_id: str | None = None,
    ) -> list[AgentSession]:
        sessions = list(self._sessions.values())
        if workspace_id is not None:
            sessions = [session for session in sessions if session.workspace_id == workspace_id]
        if identity_id is not None:
            sessions = [session for session in sessions if session.identity_id == identity_id]
        return sessions

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
        existing = self._sessions.get(session_id)
        if existing is not None:
            update: dict[str, object] = {"updated_at": datetime.now(UTC)}
            # Owner fields are immutable after create (1.0.1 isolation).
            if workspace_id is not None:
                update["workspace_id"] = workspace_id
            if identity_id is not None:
                update["identity_id"] = identity_id
            session = existing.model_copy(update=update)
            self._sessions[session_id] = session
            return session

        owner = owner_principal_id or user_id
        session = AgentSession(
            session_id=session_id,
            workspace_id=workspace_id,
            identity_id=identity_id,
            user_id=user_id or owner,
            tenant_id=tenant_id,
            tenant_workspace_id=tenant_workspace_id,
            owner_principal_id=owner,
            identity_version_id=identity_version_id,
        )
        self._sessions[session_id] = session
        return session

    def get_for_owner(
        self,
        session_id: str,
        *,
        tenant_id: str | None = None,
        tenant_workspace_id: str | None = None,
        owner_principal_id: str,
    ) -> AgentSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise AgentEngineError("SESSION_NOT_FOUND", f"Session not found: {session_id}")
        if tenant_id is not None and session.tenant_id not in (None, tenant_id):
            raise AgentEngineError("SESSION_NOT_FOUND", f"Session not found: {session_id}")
        if (
            tenant_workspace_id is not None
            and session.tenant_workspace_id not in (None, tenant_workspace_id)
        ):
            raise AgentEngineError("SESSION_NOT_FOUND", f"Session not found: {session_id}")
        session_owner = session.owner_principal_id or session.user_id
        if session_owner is not None and session_owner != owner_principal_id:
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
        sessions: list[AgentSession] = []
        for session in self._sessions.values():
            owner = session.owner_principal_id or session.user_id
            if owner != owner_principal_id:
                continue
            if tenant_id is not None and session.tenant_id not in (None, tenant_id):
                continue
            if (
                tenant_workspace_id is not None
                and session.tenant_workspace_id not in (None, tenant_workspace_id)
            ):
                continue
            if identity_id is not None and session.identity_id != identity_id:
                continue
            sessions.append(session)
        return sessions

    def append_message(self, session_id: str, message: AgentMessage) -> AgentSession:
        session = self.get(session_id)
        updated = session.model_copy(
            update={
                "messages": [*session.messages, message],
                "updated_at": datetime.now(UTC),
            }
        )
        self._sessions[session_id] = updated
        return updated

    def append_turn(self, session_id: str, turn: AgentTurn) -> AgentSession:
        session = self.get(session_id)
        updated = session.model_copy(
            update={
                "turns": [*session.turns, turn],
                "updated_at": datetime.now(UTC),
            }
        )
        self._sessions[session_id] = updated
        return updated


class JsonAgentSessionStore(InMemoryAgentSessionStore):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        super().__init__()
        self._load_into_memory()

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
        session = super().ensure_session(
            session_id,
            workspace_id=workspace_id,
            identity_id=identity_id,
            user_id=user_id,
            tenant_id=tenant_id,
            tenant_workspace_id=tenant_workspace_id,
            owner_principal_id=owner_principal_id,
            identity_version_id=identity_version_id,
        )
        self._save()
        return session

    def append_message(self, session_id: str, message: AgentMessage) -> AgentSession:
        session = super().append_message(session_id, message)
        self._save()
        return session

    def append_turn(self, session_id: str, turn: AgentTurn) -> AgentSession:
        session = super().append_turn(session_id, turn)
        self._save()
        return session

    def _load_into_memory(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            document = SessionDocument.model_validate(raw)
        except json.JSONDecodeError as exc:
            raise AgentEngineError(
                "SESSION_STORE_INVALID",
                f"Invalid session store JSON: {self.path}",
            ) from exc
        except ValidationError as exc:
            raise AgentEngineError(
                "SESSION_STORE_INVALID",
                f"Invalid session store shape: {self.path}",
            ) from exc
        self._sessions = dict(document.sessions)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        document = SessionDocument(sessions=dict(self._sessions))
        self.path.write_text(
            json.dumps(document.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
