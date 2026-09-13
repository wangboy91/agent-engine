"""FastAPI application entrypoint."""

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Literal, cast
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, WebSocket
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from app.application.agent import HandleAgentMessageCommand, HandleAgentMessageUseCase
from app.application.skill import RunSkillCommand, RunSkillUseCase
from app.domain.agent.schemas import AgentResponse
from app.domain.errors import AgentEngineError
from app.domain.execution import RunContext, TraceEvent
from app.domain.policy import PolicyEffect, ToolApprovalStatus
from app.engine import SkillEngine


class RegisterPathRequest(BaseModel):
    path: str


class CreateWorkspaceRequest(BaseModel):
    workspace_id: str
    name: str
    description: str | None = None


class CreateIdentityRequest(BaseModel):
    identity_id: str
    name: str
    description: str | None = None


class BindIdentitySkillRequest(BaseModel):
    skill_id: str


class InstallWorkspaceSkillRequest(BaseModel):
    skill_id: str
    display_name: str | None = None
    enabled: bool = True


class UpdateWorkspaceSkillRequest(BaseModel):
    enabled: bool


class ScanWorkspaceSkillsRequest(BaseModel):
    skills_dir: str = "resources/skills"
    tools_dir: str | None = "resources/tools"
    identity_id: str | None = None
    bind_to_identity: bool = True
    allow_tools_for_identity: bool = True
    enabled: bool = True


class RegisterIdentitySkillRequest(BaseModel):
    path: str
    enabled: bool = True


class RegisterIdentityToolRequest(BaseModel):
    path: str
    effect: PolicyEffect = "allow"
    reason: str = "identity resource registration"
    risk: str = "none"
    enabled: bool = True


class SetToolPolicyRequest(BaseModel):
    tool_id: str
    effect: PolicyEffect
    reason: str = ""
    risk: str = "none"
    enabled: bool = True


class DecideToolApprovalRequest(BaseModel):
    decided_by: str | None = None


class SetSecretRequest(BaseModel):
    name: str
    value: str
    description: str | None = None


class RunSkillRequest(BaseModel):
    input: dict[str, object]
    context: dict[str, object] = Field(default_factory=dict)
    mode: Literal["sync"] = "sync"


class ChatMessageRequest(BaseModel):
    session_id: str | None = None
    message: str
    scene_id: str | None = None
    skill_id: str | None = None
    input: dict[str, object] = Field(default_factory=dict)
    context: dict[str, object] = Field(default_factory=dict)
    confirm: bool = False


def create_app(engine: SkillEngine | None = None) -> FastAPI:
    api = FastAPI(title="Agent Engine", version="0.1.0")
    api.state.engine = engine or SkillEngine.load()

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/workspaces")
    def create_workspace(request: CreateWorkspaceRequest) -> dict[str, Any]:
        try:
            workspace = _engine(api).workspace_store.create_workspace(
                workspace_id=request.workspace_id,
                name=request.name,
                description=request.description,
            )
            return workspace.model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @api.get("/workspaces")
    def list_workspaces() -> list[dict[str, Any]]:
        return [
            workspace.model_dump(mode="json")
            for workspace in _engine(api).workspace_store.list_workspaces()
        ]

    @api.post("/workspaces/{workspace_id}/identities")
    def create_identity(
        workspace_id: str,
        request: CreateIdentityRequest,
    ) -> dict[str, Any]:
        try:
            identity = _engine(api).workspace_store.create_identity(
                workspace_id=workspace_id,
                identity_id=request.identity_id,
                name=request.name,
                description=request.description,
            )
            return identity.model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @api.get("/workspaces/{workspace_id}/identities")
    def list_identities(workspace_id: str) -> list[dict[str, Any]]:
        try:
            return [
                identity.model_dump(mode="json")
                for identity in _engine(api).workspace_store.list_identities(workspace_id)
            ]
        except AgentEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    @api.post("/workspaces/{workspace_id}/skills")
    def install_workspace_skill(
        workspace_id: str,
        request: InstallWorkspaceSkillRequest,
    ) -> dict[str, Any]:
        try:
            _engine(api).skill_registry.get_skill(request.skill_id)
            workspace_skill = _engine(api).workspace_store.install_skill(
                workspace_id,
                request.skill_id,
                display_name=request.display_name,
                enabled=request.enabled,
            )
            return workspace_skill.model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @api.get("/workspaces/{workspace_id}/skills")
    def list_workspace_skills(
        workspace_id: str,
        enabled_only: bool = False,
    ) -> list[dict[str, Any]]:
        try:
            return [
                workspace_skill.model_dump(mode="json")
                for workspace_skill in _engine(api).workspace_store.list_workspace_skills(
                    workspace_id,
                    enabled_only=enabled_only,
                )
            ]
        except AgentEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    @api.post("/workspaces/{workspace_id}/skills/scan")
    async def scan_workspace_skills(
        workspace_id: str,
        request: ScanWorkspaceSkillsRequest,
    ) -> dict[str, Any]:
        try:
            engine = _engine(api)
            engine.workspace_store.get_workspace(workspace_id)
            if request.identity_id is not None:
                engine.workspace_store.get_identity(workspace_id, request.identity_id)

            registered_tool_ids: list[str] = []
            identity_tool_ids: list[str] = []
            if request.tools_dir is not None:
                for tool_path in _iter_package_dirs(Path(request.tools_dir), "tool.yaml"):
                    tool = await engine.register_tool(str(tool_path))
                    registered_tool_ids.append(tool.id)
                    if (
                        request.allow_tools_for_identity
                        and request.identity_id is not None
                    ):
                        _allow_identity_tool(
                            engine,
                            workspace_id,
                            request.identity_id,
                            tool.id,
                            reason="workspace resource scan",
                        )
                        identity_tool_ids.append(tool.id)

            registered_skill_ids: list[str] = []
            installed_skill_ids: list[str] = []
            bound_skill_ids: list[str] = []
            for skill_path in _iter_package_dirs(Path(request.skills_dir), "agent.skill.json"):
                skill = await engine.register_skill(str(skill_path))
                registered_skill_ids.append(skill.id)
                engine.workspace_store.install_skill(
                    workspace_id,
                    skill.id,
                    display_name=skill.name,
                    enabled=request.enabled,
                )
                installed_skill_ids.append(skill.id)
                if request.bind_to_identity and request.identity_id is not None:
                    engine.workspace_store.bind_skill(workspace_id, request.identity_id, skill.id)
                    bound_skill_ids.append(skill.id)

            return {
                "workspace_id": workspace_id,
                "identity_id": request.identity_id,
                "skills_dir": request.skills_dir,
                "tools_dir": request.tools_dir,
                "registered_tools": registered_tool_ids,
                "identity_tools": identity_tool_ids,
                "registered_skills": registered_skill_ids,
                "installed_skills": installed_skill_ids,
                "bound_skills": bound_skill_ids,
            }
        except AgentEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @api.patch("/workspaces/{workspace_id}/skills/{skill_id}")
    def update_workspace_skill(
        workspace_id: str,
        skill_id: str,
        request: UpdateWorkspaceSkillRequest,
    ) -> dict[str, Any]:
        try:
            workspace_skill = _engine(api).workspace_store.set_skill_enabled(
                workspace_id,
                skill_id,
                request.enabled,
            )
            return workspace_skill.model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @api.post("/workspaces/{workspace_id}/identities/{identity_id}/skills/register")
    async def register_identity_skill(
        workspace_id: str,
        identity_id: str,
        request: RegisterIdentitySkillRequest,
    ) -> dict[str, Any]:
        try:
            engine = _engine(api)
            engine.workspace_store.get_identity(workspace_id, identity_id)
            skill = await engine.register_skill(request.path)
            workspace_skill = engine.workspace_store.install_skill(
                workspace_id,
                skill.id,
                display_name=skill.name,
                enabled=request.enabled,
            )
            identity = engine.workspace_store.bind_skill(workspace_id, identity_id, skill.id)
            return {
                "workspace_id": workspace_id,
                "identity_id": identity_id,
                "skill": skill.model_dump(mode="json"),
                "workspace_skill": workspace_skill.model_dump(mode="json"),
                "identity": identity.model_dump(mode="json"),
            }
        except AgentEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @api.post("/workspaces/{workspace_id}/identities/{identity_id}/tools/register")
    async def register_identity_tool(
        workspace_id: str,
        identity_id: str,
        request: RegisterIdentityToolRequest,
    ) -> dict[str, Any]:
        try:
            engine = _engine(api)
            engine.workspace_store.get_identity(workspace_id, identity_id)
            tool = await engine.register_tool(request.path)
            rule = engine.policy_store.set_tool_rule(
                tool.id,
                request.effect,
                workspace_id=workspace_id,
                identity_id=identity_id,
                reason=request.reason,
                risk=request.risk,
                enabled=request.enabled,
            )
            return {
                "workspace_id": workspace_id,
                "identity_id": identity_id,
                "tool": tool.model_dump(mode="json"),
                "policy": rule.model_dump(mode="json"),
            }
        except AgentEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @api.post("/workspaces/{workspace_id}/identities/{identity_id}/skills")
    def bind_identity_skill(
        workspace_id: str,
        identity_id: str,
        request: BindIdentitySkillRequest,
    ) -> dict[str, Any]:
        try:
            _engine(api).skill_registry.get_skill(request.skill_id)
            identity = _engine(api).workspace_store.bind_skill(
                workspace_id,
                identity_id,
                request.skill_id,
            )
            return identity.model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @api.get("/workspaces/{workspace_id}/identities/{identity_id}/skills")
    def list_identity_skills(workspace_id: str, identity_id: str) -> list[dict[str, Any]]:
        try:
            skill_ids = _engine(api).workspace_store.list_identity_skill_ids(
                workspace_id,
                identity_id,
            )
            return [
                _engine(api).skill_registry.get_skill(skill_id).model_dump(mode="json")
                for skill_id in skill_ids
            ]
        except AgentEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    @api.post("/workspaces/{workspace_id}/secrets")
    def set_workspace_secret(
        workspace_id: str,
        request: SetSecretRequest,
    ) -> dict[str, Any]:
        try:
            _engine(api).workspace_store.get_workspace(workspace_id)
            secret = _engine(api).secret_store.set_secret(
                request.name,
                request.value,
                workspace_id=workspace_id,
                description=request.description,
            )
            return secret.model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @api.get("/workspaces/{workspace_id}/secrets")
    def list_workspace_secrets(workspace_id: str) -> list[dict[str, Any]]:
        try:
            _engine(api).workspace_store.get_workspace(workspace_id)
            return [
                secret.model_dump(mode="json")
                for secret in _engine(api).secret_store.list_secrets(workspace_id=workspace_id)
            ]
        except AgentEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    @api.post("/workspaces/{workspace_id}/tool-policies")
    def set_workspace_tool_policy(
        workspace_id: str,
        request: SetToolPolicyRequest,
    ) -> dict[str, Any]:
        try:
            _engine(api).workspace_store.get_workspace(workspace_id)
            _engine(api).tool_registry.get_tool(request.tool_id)
            rule = _engine(api).policy_store.set_tool_rule(
                request.tool_id,
                request.effect,
                workspace_id=workspace_id,
                reason=request.reason,
                risk=request.risk,
                enabled=request.enabled,
            )
            return rule.model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @api.get("/workspaces/{workspace_id}/tool-policies")
    def list_workspace_tool_policies(workspace_id: str) -> list[dict[str, Any]]:
        try:
            _engine(api).workspace_store.get_workspace(workspace_id)
            return [
                rule.model_dump(mode="json")
                for rule in _engine(api).policy_store.list_tool_rules(
                    workspace_id=workspace_id,
                    identity_id=None,
                )
            ]
        except AgentEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    @api.post("/workspaces/{workspace_id}/identities/{identity_id}/tool-policies")
    def set_identity_tool_policy(
        workspace_id: str,
        identity_id: str,
        request: SetToolPolicyRequest,
    ) -> dict[str, Any]:
        try:
            _engine(api).workspace_store.get_identity(workspace_id, identity_id)
            _engine(api).tool_registry.get_tool(request.tool_id)
            rule = _engine(api).policy_store.set_tool_rule(
                request.tool_id,
                request.effect,
                workspace_id=workspace_id,
                identity_id=identity_id,
                reason=request.reason,
                risk=request.risk,
                enabled=request.enabled,
            )
            return rule.model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @api.get("/workspaces/{workspace_id}/identities/{identity_id}/tool-policies")
    def list_identity_tool_policies(
        workspace_id: str,
        identity_id: str,
    ) -> list[dict[str, Any]]:
        try:
            _engine(api).workspace_store.get_identity(workspace_id, identity_id)
            return [
                rule.model_dump(mode="json")
                for rule in _engine(api).policy_store.list_tool_rules(
                    workspace_id=workspace_id,
                    identity_id=identity_id,
                )
            ]
        except AgentEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    @api.get("/tool-approvals")
    def list_tool_approvals(
        workspace_id: str | None = None,
        identity_id: str | None = None,
        status: ToolApprovalStatus | None = None,
    ) -> list[dict[str, Any]]:
        return [
            approval.model_dump(mode="json")
            for approval in _engine(api).policy_store.list_tool_approvals(
                workspace_id=workspace_id,
                identity_id=identity_id,
                status=status,
            )
        ]

    @api.get("/tool-approvals/{approval_id}")
    def get_tool_approval(approval_id: str) -> dict[str, Any]:
        try:
            return _engine(api).policy_store.get_tool_approval(approval_id).model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    @api.post("/tool-approvals/{approval_id}/approve")
    def approve_tool_approval(
        approval_id: str,
        request: DecideToolApprovalRequest,
    ) -> dict[str, Any]:
        try:
            approval = _engine(api).policy_store.approve_tool_approval(
                approval_id,
                decided_by=request.decided_by,
            )
            return approval.model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    @api.post("/tool-approvals/{approval_id}/deny")
    def deny_tool_approval(
        approval_id: str,
        request: DecideToolApprovalRequest,
    ) -> dict[str, Any]:
        try:
            approval = _engine(api).policy_store.deny_tool_approval(
                approval_id,
                decided_by=request.decided_by,
            )
            return approval.model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    @api.post("/tools/register")
    async def register_tool(request: RegisterPathRequest) -> dict[str, Any]:
        try:
            tool = await _engine(api).register_tool(request.path)
            return tool.model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @api.get("/tools")
    def list_tools() -> list[dict[str, Any]]:
        return [
            tool.model_dump(mode="json")
            for tool in _engine(api).tool_registry.list_tools()
        ]

    @api.get("/tools/{tool_id}")
    def get_tool(tool_id: str) -> dict[str, Any]:
        try:
            return _engine(api).tool_registry.get_tool(tool_id).model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    @api.post("/skills/register")
    async def register_skill(request: RegisterPathRequest) -> dict[str, Any]:
        try:
            skill = await _engine(api).register_skill(request.path)
            return skill.model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @api.get("/skills")
    def list_skills() -> list[dict[str, Any]]:
        return [
            skill.model_dump(mode="json")
            for skill in _engine(api).skill_registry.list_skills()
        ]

    @api.get("/skills/{skill_id}")
    def get_skill(skill_id: str) -> dict[str, Any]:
        try:
            return _engine(api).skill_registry.get_skill(skill_id).model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    @api.post("/skills/{skill_id}/runs")
    async def run_skill(
        skill_id: str,
        request: RunSkillRequest,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_principal_id: str | None = Header(default=None, alias="X-Principal-Id"),
        x_principal_type: str | None = Header(default=None, alias="X-Principal-Type"),
        x_workspace_roles: str | None = Header(default=None, alias="X-Workspace-Roles"),
        x_group_ids: str | None = Header(default=None, alias="X-Group-Ids"),
    ) -> dict[str, Any]:
        try:
            context = RunContext.model_validate(request.context) if request.context else None
            principal = None
            if x_tenant_id and x_principal_id:
                from app.application.platform.run_bridge import enrich_context_with_principal
                from app.domain.platform import Principal

                principal = Principal(
                    tenant_id=x_tenant_id,
                    principal_id=x_principal_id,
                    principal_type=(x_principal_type or "user"),  # type: ignore[arg-type]
                    workspace_roles=[
                        p.strip() for p in (x_workspace_roles or "").split(",") if p.strip()
                    ],
                    group_ids=[p.strip() for p in (x_group_ids or "").split(",") if p.strip()],
                )
                context = enrich_context_with_principal(context, principal)
            run = await RunSkillUseCase(_engine(api)).execute(
                RunSkillCommand(skill_id=skill_id, input=request.input, context=context)
            )
            return run.model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @api.post("/skills/{skill_id}/runs/events")
    async def run_skill_events(skill_id: str, request: RunSkillRequest) -> StreamingResponse:
        async def stream() -> AsyncIterator[str]:
            stream_id = _new_stream_id()
            context = _context_with_stream_id(
                RunContext.model_validate(request.context) if request.context else None,
                stream_id,
            )
            engine = _engine(api)
            async with engine.trace_store.subscribe(
                workspace_id=context.workspace_id,
                identity_id=context.identity_id,
            ) as queue:
                task = asyncio.create_task(
                    RunSkillUseCase(engine).execute(
                        RunSkillCommand(skill_id=skill_id, input=request.input, context=context)
                    )
                )
                yield _sse_event("run_started", {"skill_id": skill_id, "stream_id": stream_id})
                try:
                    async for event_name, data in _stream_trace_events(queue, task, stream_id):
                        yield _sse_event(event_name, data)
                    run = await task
                except AgentEngineError as exc:
                    yield _sse_event(
                        "run_failed",
                        {"code": exc.code, "message": exc.message, "details": exc.details},
                    )
                    return
                finally:
                    _cancel_if_running(task)
            yield _sse_event("run_completed", run.model_dump(mode="json"))

        return StreamingResponse(stream(), media_type="text/event-stream")

    @api.post("/chat/messages")
    async def chat_message(request: ChatMessageRequest) -> dict[str, Any]:
        try:
            context = RunContext.model_validate(request.context) if request.context else None
            response = await HandleAgentMessageUseCase(_engine(api)).execute(
                HandleAgentMessageCommand(
                    message=request.message,
                    session_id=request.session_id,
                    scene_id=request.scene_id,
                    skill_id=request.skill_id,
                    input=request.input,
                    context=context,
                    confirm=request.confirm,
                )
            )
            return response.model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @api.post("/chat/messages/events")
    async def chat_message_events(request: ChatMessageRequest) -> StreamingResponse:
        async def stream() -> AsyncIterator[str]:
            stream_id = _new_stream_id()
            context = _context_with_stream_id(
                RunContext.model_validate(request.context) if request.context else None,
                stream_id,
            )
            engine = _engine(api)
            async with engine.trace_store.subscribe(
                workspace_id=context.workspace_id,
                identity_id=context.identity_id,
            ) as queue:
                task = asyncio.create_task(
                    HandleAgentMessageUseCase(engine).execute(
                        HandleAgentMessageCommand(
                            message=request.message,
                            session_id=request.session_id,
                            scene_id=request.scene_id,
                            skill_id=request.skill_id,
                            input=request.input,
                            context=context,
                            confirm=request.confirm,
                        )
                    )
                )
                yield _sse_event(
                    "agent_started",
                    {"session_id": request.session_id, "stream_id": stream_id},
                )
                try:
                    async for event_name, data in _stream_trace_events(queue, task, stream_id):
                        yield _sse_event(event_name, data)
                    response = await task
                except AgentEngineError as exc:
                    yield _sse_event(
                        "agent_failed",
                        {"code": exc.code, "message": exc.message, "details": exc.details},
                    )
                    return
                finally:
                    _cancel_if_running(task)
            if response.status == "completed":
                for chunk in _markdown_chunks(_agent_response_markdown(response)):
                    yield _sse_event(
                        "markdown_delta",
                        {
                            "message_id": response.turn_id,
                            "role": "assistant",
                            "delta": chunk,
                        },
                    )
                    await asyncio.sleep(0)
                yield _sse_event(
                    "markdown_completed",
                    {
                        "message_id": response.turn_id,
                        "role": "assistant",
                    },
                )
            yield _sse_event("agent_completed", response.model_dump(mode="json"))

        return StreamingResponse(stream(), media_type="text/event-stream")

    @api.websocket("/ws/skills/{skill_id}/runs")
    async def run_skill_websocket(websocket: WebSocket, skill_id: str) -> None:
        await websocket.accept()
        payload = await websocket.receive_json()
        request = RunSkillRequest.model_validate(payload)
        stream_id = _new_stream_id()
        context = _context_with_stream_id(
            RunContext.model_validate(request.context) if request.context else None,
            stream_id,
        )
        engine = _engine(api)
        async with engine.trace_store.subscribe(
            workspace_id=context.workspace_id,
            identity_id=context.identity_id,
        ) as queue:
            task = asyncio.create_task(
                RunSkillUseCase(engine).execute(
                    RunSkillCommand(skill_id=skill_id, input=request.input, context=context)
                )
            )
            await websocket.send_json(
                {"event": "run_started", "data": {"skill_id": skill_id, "stream_id": stream_id}}
            )
            try:
                await _send_trace_events(websocket, queue, task, stream_id)
                run = await task
            except AgentEngineError as exc:
                await websocket.send_json(
                    {
                        "event": "run_failed",
                        "data": {
                            "code": exc.code,
                            "message": exc.message,
                            "details": exc.details,
                        },
                    }
                )
                return
            finally:
                _cancel_if_running(task)
        await websocket.send_json({"event": "run_completed", "data": run.model_dump(mode="json")})

    @api.websocket("/ws/chat")
    async def chat_websocket(websocket: WebSocket) -> None:
        await websocket.accept()
        payload = await websocket.receive_json()
        request = ChatMessageRequest.model_validate(payload)
        stream_id = _new_stream_id()
        context = _context_with_stream_id(
            RunContext.model_validate(request.context) if request.context else None,
            stream_id,
        )
        engine = _engine(api)
        async with engine.trace_store.subscribe(
            workspace_id=context.workspace_id,
            identity_id=context.identity_id,
        ) as queue:
            task = asyncio.create_task(
                HandleAgentMessageUseCase(engine).execute(
                    HandleAgentMessageCommand(
                        message=request.message,
                        session_id=request.session_id,
                        scene_id=request.scene_id,
                        skill_id=request.skill_id,
                        input=request.input,
                        context=context,
                        confirm=request.confirm,
                    )
                )
            )
            await websocket.send_json(
                {
                    "event": "agent_started",
                    "data": {"session_id": request.session_id, "stream_id": stream_id},
                }
            )
            try:
                await _send_trace_events(websocket, queue, task, stream_id)
                response = await task
            except AgentEngineError as exc:
                await websocket.send_json(
                    {
                        "event": "agent_failed",
                        "data": {
                            "code": exc.code,
                            "message": exc.message,
                            "details": exc.details,
                        },
                    }
                )
                return
            finally:
                _cancel_if_running(task)
        await websocket.send_json(
            {"event": "agent_completed", "data": response.model_dump(mode="json")}
        )

    @api.get("/runs")
    def list_runs() -> list[dict[str, Any]]:
        return [run.model_dump(mode="json") for run in _engine(api).run_store.list_runs()]

    @api.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        try:
            return _engine(api).run_store.get(run_id).model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    @api.post("/runs/{run_id}/resume")
    async def resume_run(run_id: str) -> dict[str, Any]:
        try:
            run = await _engine(api).resume_run(run_id)
            return run.model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @api.get("/runs/{run_id}/trace")
    def get_trace(run_id: str) -> list[dict[str, Any]]:
        return [
            event.model_dump(mode="json")
            for event in _engine(api).trace_store.list_events(run_id)
        ]

    @api.get("/runs/{run_id}/artifacts")
    def get_artifacts(run_id: str) -> list[dict[str, Any]]:
        return [
            artifact.model_dump(mode="json")
            for artifact in _engine(api).artifact_store.list_by_run(run_id)
        ]

    @api.get("/sessions")
    def list_sessions(
        workspace_id: str | None = None,
        identity_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return [
            session.model_dump(mode="json")
            for session in _engine(api).session_store.list_sessions(
                workspace_id=workspace_id,
                identity_id=identity_id,
            )
        ]

    @api.get("/sessions/{session_id}")
    def get_session(session_id: str) -> dict[str, Any]:
        try:
            return _engine(api).session_store.get(session_id).model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    @api.get("/artifacts/{artifact_id}")
    def get_artifact(artifact_id: str) -> dict[str, Any]:
        try:
            return _engine(api).artifact_store.get(artifact_id).model_dump(mode="json")
        except AgentEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    from app.interfaces.http.api_v1 import router as api_v1_router

    api.include_router(api_v1_router)

    return api


def _engine(api: FastAPI) -> SkillEngine:
    return cast(SkillEngine, api.state.engine)


def _iter_package_dirs(root: Path, marker: str) -> list[Path]:
    if not root.exists():
        raise AgentEngineError(
            "PACKAGE_SCAN_ROOT_NOT_FOUND",
            f"Package scan root not found: {root}",
            {"root": str(root), "marker": marker},
        )
    if root.is_file():
        root = root.parent
    if (root / marker).exists():
        return [root]
    return sorted({path.parent for path in root.rglob(marker)})


def _allow_identity_tool(
    engine: SkillEngine,
    workspace_id: str,
    identity_id: str,
    tool_id: str,
    reason: str,
) -> None:
    engine.policy_store.set_tool_rule(
        tool_id,
        "allow",
        workspace_id=workspace_id,
        identity_id=identity_id,
        reason=reason,
    )


def _new_stream_id() -> str:
    return f"stream_{uuid4().hex}"


def _context_with_stream_id(context: RunContext | None, stream_id: str) -> RunContext:
    if context is None:
        return RunContext(metadata={"stream_id": stream_id})
    metadata = dict(context.metadata)
    metadata["stream_id"] = stream_id
    return context.model_copy(update={"metadata": metadata})


async def _stream_trace_events(
    queue: asyncio.Queue[TraceEvent],
    task: asyncio.Task[Any],
    stream_id: str,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    tracked_run_ids: set[str] = set()
    while True:
        if task.done() and queue.empty():
            break
        try:
            event = await asyncio.wait_for(queue.get(), timeout=0.05)
        except TimeoutError:
            continue

        if not _should_emit_trace_event(event, stream_id, tracked_run_ids):
            continue
        tracked_run_ids.add(event.run_id)
        yield event.type, event.model_dump(mode="json")


async def _send_trace_events(
    websocket: WebSocket,
    queue: asyncio.Queue[TraceEvent],
    task: asyncio.Task[Any],
    stream_id: str,
) -> None:
    async for event_name, data in _stream_trace_events(queue, task, stream_id):
        await websocket.send_json({"event": event_name, "data": data})


def _should_emit_trace_event(
    event: TraceEvent,
    stream_id: str,
    tracked_run_ids: set[str],
) -> bool:
    event_stream_id = event.data.get("stream_id")
    if event_stream_id == stream_id:
        return True
    return event.run_id in tracked_run_ids


def _cancel_if_running(task: asyncio.Task[Any]) -> None:
    if not task.done():
        task.cancel()


def _markdown_chunks(markdown: str, chunk_size: int = 480) -> list[str]:
    if not markdown:
        return []
    return [
        markdown[index : index + chunk_size]
        for index in range(0, len(markdown), chunk_size)
    ]


def _agent_response_markdown(response: AgentResponse) -> str:
    output = response.output or {}
    route_decision = response.route_decision
    skill_id = route_decision.skill_id if route_decision else None
    lines = [
        "### 运行结果",
        "",
        f"- 状态：{_status_label(response.status)}",
        f"- Skill：`{skill_id or 'unknown'}`",
    ]

    _append_script(lines, output)
    _append_titles(lines, output)
    _append_subtitle(lines, output)
    _append_segments(lines, output)
    _append_storyboard(lines, output)
    _append_prompt_pack(lines, output)

    if len(lines) <= 4:
        lines.extend(
            [
                "",
                "#### JSON 输出",
                "",
                "```json",
                json.dumps(output, ensure_ascii=False, indent=2),
                "```",
            ]
        )

    if response.artifacts:
        lines.extend(["", "#### 产物", ""])
        for artifact in response.artifacts:
            uri = artifact.get("uri") or artifact.get("name") or artifact.get("id")
            if uri:
                lines.append(f"- `{uri}`")
    return "\n".join(lines)


def _append_script(lines: list[str], output: dict[str, Any]) -> None:
    script = output.get("script")
    if isinstance(script, dict):
        full_text = script.get("full_text")
        if full_text:
            lines.extend(["", "#### 口播脚本", "", str(full_text)])
    elif script:
        lines.extend(["", "#### 脚本", "", str(script)])


def _append_titles(lines: list[str], output: dict[str, Any]) -> None:
    titles = output.get("titles")
    if not isinstance(titles, list) or not titles:
        return
    lines.extend(["", "#### 标题", ""])
    for title in titles:
        lines.append(f"- {title}")


def _append_subtitle(lines: list[str], output: dict[str, Any]) -> None:
    subtitle_path = output.get("subtitle_path")
    if subtitle_path:
        lines.extend(["", "#### 字幕", "", f"- `{subtitle_path}`"])


def _append_segments(lines: list[str], output: dict[str, Any]) -> None:
    script_segments = _list_of_objects(output.get("script_segments"))
    if script_segments:
        lines.extend(["", "#### 脚本分段", ""])
        for segment in script_segments[:8]:
            time_range = segment.get("time_range") or segment.get("start") or ""
            text = (
                segment.get("spoken_text")
                or segment.get("text")
                or segment.get("screen_text")
                or ""
            )
            lines.append(f"- {time_range} {text}".strip())

    segments = _list_of_objects(output.get("segments"))
    if segments:
        lines.extend(["", "#### 片段", ""])
        for segment in segments[:8]:
            start = segment.get("start") or ""
            end = segment.get("end") or ""
            text = segment.get("text") or ""
            lines.append(f"- {start} {end} {text}".strip())


def _append_storyboard(lines: list[str], output: dict[str, Any]) -> None:
    storyboard = output.get("storyboard")
    shots = _list_of_objects(storyboard.get("shots") if isinstance(storyboard, dict) else None)
    if not shots:
        return
    lines.extend(["", "#### 分镜", ""])
    for shot in shots[:8]:
        shot_id = shot.get("shot_id") or shot.get("id") or ""
        description = shot.get("description") or shot.get("visual") or ""
        duration = shot.get("duration") or ""
        suffix = f"（{duration}s）" if duration else ""
        lines.append(f"- {shot_id}：{description}{suffix}")


def _append_prompt_pack(lines: list[str], output: dict[str, Any]) -> None:
    prompt_pack = output.get("render_prompt_pack")
    prompts = _list_of_objects(
        prompt_pack.get("prompts") if isinstance(prompt_pack, dict) else None
    )
    if not prompts:
        return
    lines.extend(["", "#### 渲染提示词", ""])
    for prompt in prompts[:8]:
        shot_id = prompt.get("shot_id") or prompt.get("id") or ""
        prompt_text = prompt.get("prompt") or prompt.get("text") or ""
        lines.append(f"- {shot_id}：{prompt_text}")


def _list_of_objects(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _status_label(status: str) -> str:
    labels = {
        "completed": "已完成",
        "succeeded": "成功",
        "failed": "失败",
        "running": "运行中",
        "needs_input": "需要补充信息",
        "requires_confirmation": "需要确认",
        "waiting_approval": "等待审批",
    }
    return labels.get(status, status)


def _sse_event(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


app = create_app()
