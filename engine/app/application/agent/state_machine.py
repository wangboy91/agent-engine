"""Bounded Agent state machine that orchestrates SkillEngine calls."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.application.agent.actions import ActionRegistry
from app.application.agent.confirmation import ConfirmationPolicy
from app.application.agent.input_resolver import InputResolver
from app.application.agent.router import SkillRouter
from app.application.ports import (
    AgentRuntimePort,
    AgentSessionStorePort,
    WorkspaceStorePort,
)
from app.domain.agent.scene_mapping import SceneDefinition, SceneMapping
from app.domain.agent.schemas import (
    ActionResult,
    AgentMessage,
    AgentResponse,
    AgentTurn,
    ConfirmationRequest,
    RouteDecision,
)
from app.domain.execution import RunContext


class AgentLoop:
    def __init__(
        self,
        engine: AgentRuntimePort,
        scene_mapping: SceneMapping | None = None,
        router: SkillRouter | None = None,
        input_resolver: InputResolver | None = None,
        action_registry: ActionRegistry | None = None,
        confirmation_policy: ConfirmationPolicy | None = None,
        session_store: AgentSessionStorePort | None = None,
        workspace_store: WorkspaceStorePort | None = None,
        auto_run_threshold: float = 0.85,
        max_agent_steps: int = 6,
    ) -> None:
        self.engine = engine
        self.scene_mapping = scene_mapping or SceneMapping()
        self.router = router or SkillRouter(engine.skill_registry, auto_run_threshold)
        self.input_resolver = input_resolver or InputResolver()
        self.actions = action_registry or ActionRegistry(engine)
        self.confirmation_policy = confirmation_policy or ConfirmationPolicy()
        self.session_store = session_store or engine.session_store
        self.workspace_store = workspace_store or engine.workspace_store
        self.auto_run_threshold = auto_run_threshold
        self.max_agent_steps = max_agent_steps

    async def handle_message(
        self,
        message: str,
        *,
        session_id: str | None = None,
        scene_id: str | None = None,
        skill_id: str | None = None,
        input_data: dict[str, Any] | None = None,
        context: RunContext | None = None,
        confirm: bool = False,
    ) -> AgentResponse:
        resolved_session_id = session_id or f"sess_{uuid4().hex}"
        turn_id = f"turn_{uuid4().hex}"
        allowed_skill_ids = self._allowed_skill_ids(context)
        route, scene = self._route(
            message,
            scene_id=scene_id,
            skill_id=skill_id,
            allowed_skill_ids=allowed_skill_ids,
        )

        if route.intent != "run_skill" or route.skill_id is None:
            response = AgentResponse(
                session_id=resolved_session_id,
                turn_id=turn_id,
                status="needs_input",
                message="无法确定要运行哪个 Skill，请指定 skill_id 或说明业务场景。",
                route_decision=route,
            )
            self._record_session_turn(resolved_session_id, turn_id, message, response, context)
            return response

        if (
            route.confidence < self.auto_run_threshold
            and scene_id is None
            and skill_id is None
            and not confirm
        ):
            response = AgentResponse(
                session_id=resolved_session_id,
                turn_id=turn_id,
                status="requires_confirmation",
                message=f"可能要运行 {route.skill_id}，但置信度较低，请确认。",
                requires_confirmation=True,
                confirmation=ConfirmationRequest(
                    action_id=f"confirm_run_skill:{route.skill_id}",
                    risk="low",
                    message=f"确认运行 Skill: {route.skill_id}",
                ),
                route_decision=route,
            )
            self._record_session_turn(resolved_session_id, turn_id, message, response, context)
            return response

        skill = self.engine.skill_registry.get_skill(route.skill_id)
        merged_input_draft = dict(route.input_draft)
        if input_data:
            merged_input_draft.update(input_data)
        resolution = self.input_resolver.resolve(
            skill,
            message,
            input_draft=merged_input_draft,
            defaults=scene.defaults if scene is not None else None,
        )
        route = route.model_copy(
            update={
                "input_draft": resolution.input,
                "missing_fields": resolution.missing_fields,
            }
        )
        if resolution.missing_fields:
            response = AgentResponse(
                session_id=resolved_session_id,
                turn_id=turn_id,
                status="needs_input",
                message="缺少必填输入字段：" + ", ".join(resolution.missing_fields),
                route_decision=route,
                missing_fields=resolution.missing_fields,
            )
            self._record_session_turn(resolved_session_id, turn_id, message, response, context)
            return response

        run = await self.actions.run_skill(skill.id, resolution.input, context)
        response = AgentResponse(
            session_id=resolved_session_id,
            turn_id=turn_id,
            status="completed",
            message=f"已运行 Skill: {skill.id}",
            route_decision=route,
            action_results=[
                ActionResult(
                    action="run_skill",
                    status="succeeded",
                    run_id=run.run_id,
                    output=run.output,
                    trace_summary=run.trace_summary,
                    artifacts=[artifact.model_dump(mode="json") for artifact in run.artifacts],
                )
            ],
            run_ids=[run.run_id],
            output=run.output,
            artifacts=[artifact.model_dump(mode="json") for artifact in run.artifacts],
        )
        self._record_session_turn(resolved_session_id, turn_id, message, response, context)
        return response

    def _route(
        self,
        message: str,
        *,
        scene_id: str | None,
        skill_id: str | None,
        allowed_skill_ids: list[str] | None,
    ) -> tuple[RouteDecision, SceneDefinition | None]:
        if skill_id is not None:
            return (
                self.router.route(
                    message,
                    explicit_skill_id=skill_id,
                    allowed_skill_ids=allowed_skill_ids,
                ),
                None,
            )

        if scene_id is not None:
            scene = self.scene_mapping.get(scene_id)
            if scene is None:
                return (
                    RouteDecision(
                        intent="unknown",
                        confidence=0,
                        reason=f"scene not found: {scene_id}",
                        scene_id=scene_id,
                    ),
                    None,
                )
            if allowed_skill_ids is not None and scene.skill_id not in allowed_skill_ids:
                return (
                    RouteDecision(
                        intent="unknown",
                        skill_id=scene.skill_id,
                        confidence=0,
                        reason="scene skill is not available to the active identity",
                        scene_id=scene_id,
                    ),
                    scene,
                )
            return (
                RouteDecision(
                    intent="run_skill",
                    skill_id=scene.skill_id,
                    confidence=1,
                    reason="scene mapping",
                    scene_id=scene_id,
                ),
                scene,
            )

        return self.router.route(message, allowed_skill_ids=allowed_skill_ids), None

    def _allowed_skill_ids(self, context: RunContext | None) -> list[str] | None:
        if context is None or context.workspace_id is None or context.identity_id is None:
            return None
        return self.workspace_store.list_identity_skill_ids(
            context.workspace_id,
            context.identity_id,
        )

    def _record_session_turn(
        self,
        session_id: str,
        turn_id: str,
        user_message: str,
        response: AgentResponse,
        context: RunContext | None,
    ) -> None:
        self.session_store.ensure_session(
            session_id,
            workspace_id=context.workspace_id if context is not None else None,
            identity_id=context.identity_id if context is not None else None,
            user_id=context.user_id if context is not None else None,
        )
        self.session_store.append_message(
            session_id,
            AgentMessage(role="user", content=user_message),
        )
        self.session_store.append_message(
            session_id,
            AgentMessage(role="assistant", content=response.message),
        )
        self.session_store.append_turn(
            session_id,
            AgentTurn(
                turn_id=turn_id,
                user_message=user_message,
                route_decision=response.route_decision,
                action_results=response.action_results,
                run_ids=response.run_ids,
                response=response,
            ),
        )
