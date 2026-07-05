"""Trace store primitives."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError

from bkl_engine.domain.errors import BklEngineError
from bkl_engine.domain.execution import TraceEvent


class TraceDocument(BaseModel):
    version: int = 1
    events: dict[str, list[TraceEvent]] = Field(default_factory=dict)


class TraceSubscriber:
    def __init__(
        self,
        workspace_id: str | None = None,
        identity_id: str | None = None,
    ) -> None:
        self.queue: asyncio.Queue[TraceEvent] = asyncio.Queue(maxsize=1000)
        self.workspace_id = workspace_id
        self.identity_id = identity_id
        self.tracked_run_ids: set[str] = set()

    def accepts(self, event: TraceEvent) -> bool:
        if self.workspace_id is None and self.identity_id is None:
            return True
        if event.run_id in self.tracked_run_ids:
            return True
        if self.workspace_id is not None and event.data.get("workspace_id") != self.workspace_id:
            return False
        if self.identity_id is not None and event.data.get("identity_id") != self.identity_id:
            return False
        self.tracked_run_ids.add(event.run_id)
        return True


class InMemoryTraceStore:
    def __init__(self) -> None:
        self._events: dict[str, list[TraceEvent]] = {}
        self._subscribers: set[TraceSubscriber] = set()

    def record(
        self,
        run_id: str,
        event_type: str,
        message: str,
        data: dict[str, object],
    ) -> TraceEvent:
        event = TraceEvent(
            id=f"trace_{uuid4().hex}",
            run_id=run_id,
            type=event_type,
            message=message,
            data=self._redact(data),
        )
        self._events.setdefault(run_id, []).append(event)
        self._publish(event)
        return event

    def list_events(self, run_id: str) -> list[TraceEvent]:
        return list(self._events.get(run_id, []))

    @asynccontextmanager
    async def subscribe(
        self,
        workspace_id: str | None = None,
        identity_id: str | None = None,
    ) -> AsyncIterator[asyncio.Queue[TraceEvent]]:
        subscriber = TraceSubscriber(workspace_id=workspace_id, identity_id=identity_id)
        self._subscribers.add(subscriber)
        try:
            yield subscriber.queue
        finally:
            self._subscribers.discard(subscriber)

    def _publish(self, event: TraceEvent) -> None:
        stale: list[TraceSubscriber] = []
        for subscriber in self._subscribers:
            if not subscriber.accepts(event):
                continue
            try:
                subscriber.queue.put_nowait(event)
            except asyncio.QueueFull:
                stale.append(subscriber)
        for subscriber in stale:
            self._subscribers.discard(subscriber)

    def _redact(self, data: dict[str, object]) -> dict[str, object]:
        redacted: dict[str, object] = {}
        sensitive_parts = ("authorization", "api_key", "password", "secret", "token", "credential")
        for key, value in data.items():
            if any(part in key.lower() for part in sensitive_parts):
                redacted[key] = "[REDACTED]"
            elif isinstance(value, dict):
                redacted[key] = self._redact(value)
            else:
                redacted[key] = value
        return redacted


class JsonTraceStore(InMemoryTraceStore):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        super().__init__()
        self._load_into_memory()

    def record(
        self,
        run_id: str,
        event_type: str,
        message: str,
        data: dict[str, object],
    ) -> TraceEvent:
        event = super().record(run_id, event_type, message, data)
        self._save()
        return event

    def _load_into_memory(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            document = TraceDocument.model_validate(raw)
        except json.JSONDecodeError as exc:
            raise BklEngineError(
                "TRACE_STORE_INVALID",
                f"Invalid trace store JSON: {self.path}",
            ) from exc
        except ValidationError as exc:
            raise BklEngineError(
                "TRACE_STORE_INVALID",
                f"Invalid trace store shape: {self.path}",
            ) from exc
        self._events = {run_id: list(events) for run_id, events in document.events.items()}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        document = TraceDocument(
            events={run_id: list(events) for run_id, events in self._events.items()}
        )
        self.path.write_text(
            json.dumps(document.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
