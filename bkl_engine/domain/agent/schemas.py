"""Pydantic schemas for the Agent domain."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

JsonObject = dict[str, Any]
AgentStatus = Literal["completed", "needs_input", "requires_confirmation", "failed"]
AgentIntent = Literal["run_skill", "list_skills", "list_tools", "unknown"]


class AgentMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RouteDecision(BaseModel):
    intent: AgentIntent
    skill_id: str | None = None
    confidence: float = 0
    input_draft: JsonObject = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    reason: str = ""
    scene_id: str | None = None


class InputResolution(BaseModel):
    input: JsonObject = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class ConfirmationRequest(BaseModel):
    action_id: str
    risk: str
    message: str


class ActionResult(BaseModel):
    action: str
    status: Literal["succeeded", "failed"]
    run_id: str | None = None
    output: JsonObject | None = None
    error: str | None = None
    trace_summary: JsonObject = Field(default_factory=dict)
    artifacts: list[JsonObject] = Field(default_factory=list)


class ActionPlan(BaseModel):
    actions: list[str] = Field(default_factory=list)


class AgentResponse(BaseModel):
    session_id: str
    turn_id: str
    status: AgentStatus
    message: str
    requires_confirmation: bool = False
    confirmation: ConfirmationRequest | None = None
    route_decision: RouteDecision | None = None
    action_results: list[ActionResult] = Field(default_factory=list)
    run_ids: list[str] = Field(default_factory=list)
    output: JsonObject | None = None
    artifacts: list[JsonObject] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentTurn(BaseModel):
    turn_id: str
    user_message: str
    route_decision: RouteDecision | None = None
    action_plan: ActionPlan = Field(default_factory=ActionPlan)
    action_results: list[ActionResult] = Field(default_factory=list)
    run_ids: list[str] = Field(default_factory=list)
    response: AgentResponse | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentSession(BaseModel):
    session_id: str
    workspace_id: str | None = None
    identity_id: str | None = None
    user_id: str | None = None
    messages: list[AgentMessage] = Field(default_factory=list)
    turns: list[AgentTurn] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
