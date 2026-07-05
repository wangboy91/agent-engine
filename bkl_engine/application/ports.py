"""Application-layer ports implemented by infrastructure adapters."""

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

from bkl_engine.domain.agent import AgentMessage, AgentSession, AgentTurn
from bkl_engine.domain.execution import Artifact, ArtifactType, RunContext, RunResult, TraceEvent
from bkl_engine.domain.model import ModelResponse
from bkl_engine.domain.policy import PolicyDecision
from bkl_engine.domain.skill import Skill
from bkl_engine.domain.tool import Tool, ToolExecutionContext, ToolExecutionResult
from bkl_engine.domain.workspace import Identity, Workspace, WorkspaceSkill


@runtime_checkable
class SkillRegistryPort(Protocol):
    def register(self, skill: Skill) -> Skill:
        ...

    def get_skill(self, skill_id: str) -> Skill:
        ...

    def list_skills(self) -> list[Skill]:
        ...


@runtime_checkable
class ToolRegistryPort(Protocol):
    def register(self, tool: Tool) -> Tool:
        ...

    def get_tool(self, tool_id: str) -> Tool:
        ...

    def list_tools(self) -> list[Tool]:
        ...

    def get_allowed_tools(self, allowed_tools: list[str]) -> list[Tool]:
        ...


@runtime_checkable
class ModelGatewayPort(Protocol):
    async def chat(
        self,
        profile: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        stream_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> ModelResponse:
        ...


@runtime_checkable
class ToolRunnerPort(Protocol):
    async def execute(
        self,
        tool: Tool,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        ...


@runtime_checkable
class ToolExecutorPort(Protocol):
    def evaluate_policy(
        self,
        tool: Tool,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> PolicyDecision:
        ...

    async def execute(
        self,
        tool: Tool,
        arguments: dict[str, object],
        context: ToolExecutionContext,
        policy_decision: PolicyDecision | None = None,
    ) -> ToolExecutionResult:
        ...


@runtime_checkable
class SkillRunnerPort(Protocol):
    async def run_skill(
        self,
        skill_id: str,
        input_data: dict[str, object],
        context: RunContext | None = None,
    ) -> RunResult:
        ...


@runtime_checkable
class AgentRuntimePort(SkillRunnerPort, Protocol):
    @property
    def skill_registry(self) -> SkillRegistryPort:
        ...

    @property
    def tool_registry(self) -> ToolRegistryPort:
        ...

    @property
    def session_store(self) -> "AgentSessionStorePort":
        ...

    @property
    def workspace_store(self) -> "WorkspaceStorePort":
        ...


@runtime_checkable
class RunStorePort(Protocol):
    def save(self, run: RunResult) -> RunResult:
        ...

    def get(self, run_id: str) -> RunResult:
        ...

    def list_runs(self) -> list[RunResult]:
        ...


@runtime_checkable
class AgentSessionStorePort(Protocol):
    def get(self, session_id: str) -> AgentSession:
        ...

    def list_sessions(
        self,
        workspace_id: str | None = None,
        identity_id: str | None = None,
    ) -> list[AgentSession]:
        ...

    def ensure_session(
        self,
        session_id: str,
        workspace_id: str | None = None,
        identity_id: str | None = None,
        user_id: str | None = None,
    ) -> AgentSession:
        ...

    def append_message(self, session_id: str, message: AgentMessage) -> AgentSession:
        ...

    def append_turn(self, session_id: str, turn: AgentTurn) -> AgentSession:
        ...


@runtime_checkable
class WorkspaceStorePort(Protocol):
    def create_workspace(
        self,
        workspace_id: str,
        name: str,
        description: str | None = None,
    ) -> Workspace:
        ...

    def get_workspace(self, workspace_id: str) -> Workspace:
        ...

    def list_workspaces(self) -> list[Workspace]:
        ...

    def install_skill(
        self,
        workspace_id: str,
        skill_id: str,
        display_name: str | None = None,
        enabled: bool = True,
    ) -> WorkspaceSkill:
        ...

    def set_skill_enabled(
        self,
        workspace_id: str,
        skill_id: str,
        enabled: bool,
    ) -> WorkspaceSkill:
        ...

    def get_workspace_skill(self, workspace_id: str, skill_id: str) -> WorkspaceSkill:
        ...

    def list_workspace_skills(
        self,
        workspace_id: str,
        enabled_only: bool = False,
    ) -> list[WorkspaceSkill]:
        ...

    def list_workspace_skill_ids(
        self,
        workspace_id: str,
        enabled_only: bool = True,
    ) -> list[str]:
        ...

    def create_identity(
        self,
        workspace_id: str,
        identity_id: str,
        name: str,
        description: str | None = None,
    ) -> Identity:
        ...

    def get_identity(self, workspace_id: str, identity_id: str) -> Identity:
        ...

    def list_identities(self, workspace_id: str) -> list[Identity]:
        ...

    def bind_skill(self, workspace_id: str, identity_id: str, skill_id: str) -> Identity:
        ...

    def list_identity_skill_ids(self, workspace_id: str, identity_id: str) -> list[str]:
        ...

    def is_skill_allowed(self, workspace_id: str, identity_id: str, skill_id: str) -> bool:
        ...


@runtime_checkable
class TraceStorePort(Protocol):
    def record(
        self,
        run_id: str,
        event_type: str,
        message: str,
        data: dict[str, object],
    ) -> TraceEvent:
        ...

    def list_events(self, run_id: str) -> list[TraceEvent]:
        ...


@runtime_checkable
class ArtifactStorePort(Protocol):
    def tool_artifact_dir(self, run_id: str, tool_call_id: str) -> Path:
        ...

    def save_text(
        self,
        run_id: str,
        content: str,
        artifact_type: ArtifactType,
        filename: str,
        tool_call_id: str | None = None,
        mime_type: str = "text/plain",
    ) -> Artifact:
        ...

    def register_file(
        self,
        run_id: str,
        path: str,
        artifact_type: ArtifactType,
        mime_type: str,
        tool_call_id: str | None = None,
    ) -> Artifact:
        ...

    def get(self, artifact_id: str) -> Artifact:
        ...

    def read_text(self, artifact_id: str) -> str:
        ...

    def list_by_run(self, run_id: str) -> list[Artifact]:
        ...
