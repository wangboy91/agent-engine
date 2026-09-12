"""Deterministic Agent actions over SkillEngine."""

from __future__ import annotations

from typing import Any

from app.application.ports import AgentRuntimePort
from app.domain.execution import RunContext, RunResult


class ActionRegistry:
    def __init__(self, engine: AgentRuntimePort) -> None:
        self.engine = engine

    async def run_skill(
        self,
        skill_id: str,
        input_data: dict[str, Any],
        context: RunContext | None = None,
    ) -> RunResult:
        return await self.engine.run_skill(skill_id, input_data, context)

    def list_skills(self) -> list[str]:
        return [skill.id for skill in self.engine.skill_registry.list_skills()]

    def list_tools(self) -> list[str]:
        return [tool.id for tool in self.engine.tool_registry.list_tools()]
