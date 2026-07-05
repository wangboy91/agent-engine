"""FastAPI application entrypoint."""

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Literal, cast
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.responses import FileResponse, StreamingResponse

from bkl_engine.application.agent import HandleAgentMessageCommand, HandleAgentMessageUseCase
from bkl_engine.application.skill import RunSkillCommand, RunSkillUseCase
from bkl_engine.domain.errors import BklEngineError
from bkl_engine.domain.execution import RunContext, TraceEvent
from bkl_engine.domain.policy import PolicyEffect, ToolApprovalStatus
from bkl_engine.engine import SkillEngine

STATIC_DIR = Path(__file__).parent / "static"


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
    skills_dir: str = "examples/skills"
    tools_dir: str | None = "examples/tools"
    identity_id: str | None = None
    bind_to_identity: bool = True
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
    api = FastAPI(title="BKL Skill Engine", version="0.1.0")
    api.state.engine = engine or SkillEngine.load()
    api.mount("/ui/assets", StaticFiles(directory=STATIC_DIR), name="runtime-console-assets")

    @api.get("/ui", include_in_schema=False)
    def runtime_console() -> FileResponse:
        return FileResponse(STATIC_DIR / "runtime-console.html")

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
        except BklEngineError as exc:
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
        except BklEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @api.get("/workspaces/{workspace_id}/identities")
    def list_identities(workspace_id: str) -> list[dict[str, Any]]:
        try:
            return [
                identity.model_dump(mode="json")
                for identity in _engine(api).workspace_store.list_identities(workspace_id)
            ]
        except BklEngineError as exc:
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
        except BklEngineError as exc:
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
        except BklEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

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
        except BklEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

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
            if request.tools_dir is not None:
                for tool_path in _iter_package_dirs(Path(request.tools_dir), "tool.yaml"):
                    tool = await engine.register_tool(str(tool_path))
                    registered_tool_ids.append(tool.id)

            registered_skill_ids: list[str] = []
            installed_skill_ids: list[str] = []
            bound_skill_ids: list[str] = []
            for skill_path in _iter_package_dirs(Path(request.skills_dir), "bkl.skill.json"):
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
                "registered_skills": registered_skill_ids,
                "installed_skills": installed_skill_ids,
                "bound_skills": bound_skill_ids,
            }
        except BklEngineError as exc:
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
        except BklEngineError as exc:
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
        except BklEngineError as exc:
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
        except BklEngineError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @api.get("/workspaces/{workspace_id}/secrets")
    def list_workspace_secrets(workspace_id: str) -> list[dict[str, Any]]:
        try:
            _engine(api).workspace_store.get_workspace(workspace_id)
            return [
                secret.model_dump(mode="json")
                for secret in _engine(api).secret_store.list_secrets(workspace_id=workspace_id)
            ]
        except BklEngineError as exc:
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
        except BklEngineError as exc:
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
        except BklEngineError as exc:
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
        except BklEngineError as exc:
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
        except BklEngineError as exc:
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
        except BklEngineError as exc:
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
        except BklEngineError as exc:
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
        except BklEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    @api.post("/tools/register")
    async def register_tool(request: RegisterPathRequest) -> dict[str, Any]:
        try:
            tool = await _engine(api).register_tool(request.path)
            return tool.model_dump(mode="json")
        except BklEngineError as exc:
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
        except BklEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    @api.post("/skills/register")
    async def register_skill(request: RegisterPathRequest) -> dict[str, Any]:
        try:
            skill = await _engine(api).register_skill(request.path)
            return skill.model_dump(mode="json")
        except BklEngineError as exc:
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
        except BklEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    @api.post("/skills/{skill_id}/runs")
    async def run_skill(skill_id: str, request: RunSkillRequest) -> dict[str, Any]:
        try:
            context = RunContext.model_validate(request.context) if request.context else None
            run = await RunSkillUseCase(_engine(api)).execute(
                RunSkillCommand(skill_id=skill_id, input=request.input, context=context)
            )
            return run.model_dump(mode="json")
        except BklEngineError as exc:
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
                except BklEngineError as exc:
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
        except BklEngineError as exc:
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
                except BklEngineError as exc:
                    yield _sse_event(
                        "agent_failed",
                        {"code": exc.code, "message": exc.message, "details": exc.details},
                    )
                    return
                finally:
                    _cancel_if_running(task)
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
            except BklEngineError as exc:
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
            except BklEngineError as exc:
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
        except BklEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    @api.post("/runs/{run_id}/resume")
    async def resume_run(run_id: str) -> dict[str, Any]:
        try:
            run = await _engine(api).resume_run(run_id)
            return run.model_dump(mode="json")
        except BklEngineError as exc:
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
        except BklEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    @api.get("/artifacts/{artifact_id}")
    def get_artifact(artifact_id: str) -> dict[str, Any]:
        try:
            return _engine(api).artifact_store.get(artifact_id).model_dump(mode="json")
        except BklEngineError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc

    return api


def _engine(api: FastAPI) -> SkillEngine:
    return cast(SkillEngine, api.state.engine)


def _iter_package_dirs(root: Path, marker: str) -> list[Path]:
    if not root.exists():
        raise BklEngineError(
            "PACKAGE_SCAN_ROOT_NOT_FOUND",
            f"Package scan root not found: {root}",
            {"root": str(root), "marker": marker},
        )
    if root.is_file():
        root = root.parent
    if (root / marker).exists():
        return [root]
    return sorted({path.parent for path in root.rglob(marker)})


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


def _sse_event(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


app = create_app()
