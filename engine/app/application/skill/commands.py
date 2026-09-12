"""Skill application commands."""

from typing import Any

from pydantic import BaseModel, Field

from app.domain.execution import RunContext


class RunSkillCommand(BaseModel):
    skill_id: str
    input: dict[str, Any] = Field(default_factory=dict)
    context: RunContext | None = None
