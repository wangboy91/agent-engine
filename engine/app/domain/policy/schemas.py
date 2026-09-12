"""Policy domain schemas."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

PolicyEffect = Literal["allow", "ask", "deny"]
ToolApprovalStatus = Literal["pending", "approved", "denied"]


class PolicyDecision(BaseModel):
    effect: PolicyEffect = "allow"
    reason: str = ""
    risk: str = "none"
    details: dict[str, Any] = Field(default_factory=dict)


class ToolPolicyRule(BaseModel):
    rule_id: str
    tool_id: str
    effect: PolicyEffect
    workspace_id: str | None = None
    identity_id: str | None = None
    reason: str = ""
    risk: str = "none"
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ToolApprovalRecord(BaseModel):
    approval_id: str
    tool_id: str
    workspace_id: str | None = None
    identity_id: str | None = None
    skill_id: str | None = None
    run_id: str | None = None
    tool_call_id: str | None = None
    rule_id: str | None = None
    status: ToolApprovalStatus = "pending"
    reason: str = ""
    risk: str = "none"
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decided_at: datetime | None = None
    decided_by: str | None = None
