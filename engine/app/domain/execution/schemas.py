"""Execution domain schemas."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.common import JsonObject

RunStatus = Literal["pending", "running", "waiting_approval", "succeeded", "failed"]
ArtifactType = Literal["text", "json", "image", "audio", "video", "subtitle", "zip", "log"]


class EngineError(BaseModel):
    code: str
    message: str
    details: JsonObject = Field(default_factory=dict)
    retryable: bool = False


class UsageSummary(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    model_cost: float = 0
    tool_cost: float = 0
    credits_charged: float = 0


class Artifact(BaseModel):
    id: str
    run_id: str
    tool_call_id: str | None = None
    type: ArtifactType
    mime_type: str
    uri: str
    metadata: JsonObject = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TraceEvent(BaseModel):
    id: str
    run_id: str
    type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message: str
    data: JsonObject = Field(default_factory=dict)


class RunContext(BaseModel):
    user_id: str | None = None
    workspace_id: str | None = None
    identity_id: str | None = None
    role_id: str | None = None
    project_id: str | None = None
    metadata: JsonObject = Field(default_factory=dict)


class RunResult(BaseModel):
    run_id: str
    status: RunStatus
    skill_id: str
    input: JsonObject = Field(default_factory=dict)
    context: RunContext | None = None
    output: JsonObject | None = None
    error: EngineError | None = None
    pending_approval: JsonObject | None = None
    artifacts: list[Artifact] = Field(default_factory=list)
    trace_summary: JsonObject = Field(default_factory=dict)
    usage: UsageSummary = Field(default_factory=UsageSummary)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
