"""Agent application commands."""

from typing import Any

from pydantic import BaseModel, Field

from bkl_engine.domain.execution import RunContext


class HandleAgentMessageCommand(BaseModel):
    message: str
    session_id: str | None = None
    scene_id: str | None = None
    skill_id: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    context: RunContext | None = None
    confirm: bool = False
