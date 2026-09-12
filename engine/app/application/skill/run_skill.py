"""Application use case for direct Skill execution."""

from __future__ import annotations

from app.application.ports import SkillRunnerPort
from app.application.skill.commands import RunSkillCommand
from app.domain.execution import RunResult


class RunSkillUseCase:
    def __init__(self, engine: SkillRunnerPort) -> None:
        self.engine = engine

    async def execute(self, command: RunSkillCommand) -> RunResult:
        return await self.engine.run_skill(command.skill_id, command.input, command.context)
