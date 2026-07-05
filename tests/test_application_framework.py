import asyncio
from pathlib import Path

import pytest

import bkl_engine.infrastructure
import bkl_engine.interfaces
from bkl_engine.application.agent import HandleAgentMessageCommand, HandleAgentMessageUseCase
from bkl_engine.application.agent.input_resolver import InputResolver
from bkl_engine.application.agent.router import SkillRouter
from bkl_engine.application.agent.state_machine import AgentLoop
from bkl_engine.application.execution.skill_runtime import SkillRuntime, SkillRuntimeError
from bkl_engine.application.ports import (
    AgentSessionStorePort,
    ArtifactStorePort,
    RunStorePort,
    TraceStorePort,
    WorkspaceStorePort,
)
from bkl_engine.application.skill import RunSkillCommand, RunSkillUseCase
from bkl_engine.application.tool.executor import ToolExecutor as CanonicalToolExecutor
from bkl_engine.domain.agent import AgentResponse, AgentTurnState, RouteDecision, SceneMapping
from bkl_engine.domain.execution import ExecutionState
from bkl_engine.domain.policy import PolicyDecision
from bkl_engine.domain.tool import Tool, ToolExecutionContext, ToolExecutionResult
from bkl_engine.engine import SkillEngine
from bkl_engine.infrastructure.package_loaders.skill_loader import load_skill
from bkl_engine.infrastructure.package_loaders.tool_loader import load_tool
from bkl_engine.infrastructure.persistence.secret_store import InMemorySecretStore
from bkl_engine.infrastructure.repositories.skill_registry import InMemorySkillRegistry
from bkl_engine.infrastructure.repositories.tool_registry import InMemoryToolRegistry
from bkl_engine.infrastructure.tool_runners.api_tool import ApiToolRunner
from bkl_engine.infrastructure.tool_runners.python_tool import PythonToolRunner


def test_application_use_case_runs_explicit_skill(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    asyncio.run(engine.register_tool("examples/tools/subtitle_generate_srt"))
    asyncio.run(engine.register_skill("examples/skills/talking-video"))

    use_case = RunSkillUseCase(engine)
    result = asyncio.run(
        use_case.execute(
            RunSkillCommand(
                skill_id="talking-video",
                input={
                    "topic": "适合程序员的护眼台灯",
                    "platform": "xiaohongshu",
                    "duration_seconds": 60,
                },
            )
        )
    )

    assert result.status == "succeeded"
    assert result.output is not None
    assert result.output["subtitle_path"] == "subtitle.srt"
    assert result.trace_summary["tool_called"] == 1


def test_application_use_case_routes_agent_message_to_skill(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    asyncio.run(engine.register_tool("examples/tools/subtitle_generate_srt"))
    asyncio.run(engine.register_skill("examples/skills/talking-video"))

    use_case = HandleAgentMessageUseCase(engine)
    response = asyncio.run(
        use_case.execute(
            HandleAgentMessageCommand(
                message="帮我生成60秒小红书口播视频，主题是程序员护眼台灯"
            )
        )
    )

    assert response.status == "completed"
    assert response.route_decision is not None
    assert response.route_decision.skill_id == "talking-video"
    assert response.run_ids
    assert response.output is not None
    assert response.output["subtitle_path"] == "subtitle.srt"


def test_framework_exposes_ports_and_explicit_states(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)

    assert isinstance(engine.run_store, RunStorePort)
    assert isinstance(engine.trace_store, TraceStorePort)
    assert isinstance(engine.artifact_store, ArtifactStorePort)
    assert isinstance(engine.session_store, AgentSessionStorePort)
    assert isinstance(engine.workspace_store, WorkspaceStorePort)
    assert bkl_engine.infrastructure.__doc__
    assert bkl_engine.interfaces.__doc__
    assert AgentTurnState.MESSAGE_RECEIVED.value == "message_received"
    assert AgentTurnState.WAITING_CONFIRMATION.value == "waiting_confirmation"
    assert ExecutionState.TOOL_POLICY_CHECKING.value == "tool_policy_checking"
    assert ExecutionState.SUCCEEDED.value == "succeeded"


def test_agent_runtime_uses_canonical_ddd_import_paths() -> None:
    assert AgentLoop.__module__ == "bkl_engine.application.agent.state_machine"
    assert SkillRouter.__module__ == "bkl_engine.application.agent.router"
    assert InputResolver.__module__ == "bkl_engine.application.agent.input_resolver"
    assert AgentResponse.__module__ == "bkl_engine.domain.agent.schemas"
    assert RouteDecision.__module__ == "bkl_engine.domain.agent.schemas"
    assert SceneMapping.__module__ == "bkl_engine.domain.agent.scene_mapping"


def test_skill_and_tool_runtime_use_canonical_ddd_import_paths() -> None:
    assert SkillRuntime.__module__ == "bkl_engine.application.execution.skill_runtime"
    assert CanonicalToolExecutor.__module__ == "bkl_engine.application.tool.executor"
    assert InMemorySkillRegistry.__module__ == (
        "bkl_engine.infrastructure.repositories.skill_registry"
    )
    assert InMemoryToolRegistry.__module__ == (
        "bkl_engine.infrastructure.repositories.tool_registry"
    )
    assert load_skill.__module__ == "bkl_engine.infrastructure.package_loaders.skill_loader"
    assert load_tool.__module__ == "bkl_engine.infrastructure.package_loaders.tool_loader"


def test_tool_policy_denial_blocks_skill_run_and_records_trace(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(
        artifact_root=tmp_path,
        tool_executor=CanonicalToolExecutor(
            python_runner=PythonToolRunner(),
            api_runner=ApiToolRunner(),
            policy_engine=DenyEveryToolPolicy(),
        ),
    )
    asyncio.run(engine.register_tool("examples/tools/subtitle_generate_srt"))
    asyncio.run(engine.register_skill("examples/skills/talking-video"))

    with pytest.raises(SkillRuntimeError, match="TOOL_POLICY_DENIED"):
        asyncio.run(
            engine.run_skill(
                "talking-video",
                {
                    "topic": "适合程序员的护眼台灯",
                    "platform": "xiaohongshu",
                    "duration_seconds": 60,
                },
            )
        )

    failed_run = engine.run_store.list_runs()[0]
    events = engine.trace_store.list_events(failed_run.run_id)
    assert failed_run.status == "failed"
    assert failed_run.trace_summary["tool_failed"] == 1
    assert any(event.type == "tool_policy_checked" for event in events)
    assert any(event.type == "tool_failed" for event in events)


class DenyEveryToolPolicy:
    def evaluate_tool_execution(self, *args: object, **kwargs: object) -> PolicyDecision:
        return PolicyDecision(effect="deny", reason="test policy denial")


def test_tool_executor_resolves_allowed_secret_refs(tmp_path: Path) -> None:
    secret_store = InMemorySecretStore()
    secret_store.set_secret("VIDEO_API_KEY", "secret-value", workspace_id="workspace_content_ops")
    runner = CapturingToolRunner()
    executor = CanonicalToolExecutor(
        python_runner=runner,
        api_runner=ApiToolRunner(),
        secret_store=secret_store,
    )
    tool = Tool(
        id="secret_tool",
        name="Secret Tool",
        type="python",
        description="Uses a secret",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        permissions={"secrets": ["VIDEO_API_KEY"]},
    )

    result = asyncio.run(
        executor.execute(
            tool,
            {"api_key": {"secret_ref": "VIDEO_API_KEY"}},
            ToolExecutionContext(
                run_id="run_001",
                tool_call_id="tool_001",
                artifact_dir=tmp_path,
                workspace_id="workspace_content_ops",
            ),
        )
    )

    assert result.output["api_key"] == "secret-value"


def test_tool_executor_rejects_unallowed_secret_refs(tmp_path: Path) -> None:
    secret_store = InMemorySecretStore()
    secret_store.set_secret("VIDEO_API_KEY", "secret-value", workspace_id="workspace_content_ops")
    executor = CanonicalToolExecutor(
        python_runner=CapturingToolRunner(),
        api_runner=ApiToolRunner(),
        secret_store=secret_store,
    )
    tool = Tool(
        id="secret_tool",
        name="Secret Tool",
        type="python",
        description="Uses a secret",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    with pytest.raises(Exception, match="SECRET_NOT_ALLOWED"):
        asyncio.run(
            executor.execute(
                tool,
                {"api_key": {"secret_ref": "VIDEO_API_KEY"}},
                ToolExecutionContext(
                    run_id="run_001",
                    tool_call_id="tool_001",
                    artifact_dir=tmp_path,
                    workspace_id="workspace_content_ops",
                ),
            )
        )


class CapturingToolRunner:
    async def execute(
        self,
        tool: Tool,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        del tool, context
        return ToolExecutionResult(output=dict(arguments))
