"""Application use case for one Agent message turn."""

from __future__ import annotations

from app.application.agent.commands import HandleAgentMessageCommand
from app.application.agent.state_machine import AgentLoop
from app.application.ports import AgentRuntimePort
from app.domain.agent.scene_mapping import SceneMapping
from app.domain.agent.schemas import AgentResponse


class HandleAgentMessageUseCase:
    def __init__(
        self,
        engine: AgentRuntimePort,
        scene_mapping: SceneMapping | None = None,
    ) -> None:
        self.engine = engine
        self.scene_mapping = scene_mapping

    async def execute(self, command: HandleAgentMessageCommand) -> AgentResponse:
        loop = AgentLoop(self.engine, scene_mapping=self.scene_mapping)
        return await loop.handle_message(
            command.message,
            session_id=command.session_id,
            scene_id=command.scene_id,
            skill_id=command.skill_id,
            input_data=command.input,
            context=command.context,
            confirm=command.confirm,
        )
