"""Public SkillEngine facade shared by SDK, CLI, and API."""

from pathlib import Path

from bkl_engine.application.execution import SkillRuntime
from bkl_engine.application.execution.prompt_context import PromptContextAssembler
from bkl_engine.application.policy import PolicyEngine
from bkl_engine.application.ports import (
    AgentSessionStorePort,
    MemoryStorePort,
    ToolExecutorPort,
    WorkspaceStorePort,
)
from bkl_engine.application.tool.executor import ToolExecutor
from bkl_engine.domain.execution import RunContext, RunResult
from bkl_engine.domain.skill import Skill
from bkl_engine.domain.tool import Tool
from bkl_engine.infrastructure.config.engine_config import load_engine_config
from bkl_engine.infrastructure.model_gateway.router import (
    MockModelProvider,
    ModelProvider,
    ModelRouter,
)
from bkl_engine.infrastructure.persistence import (
    InMemoryAgentSessionStore,
    InMemoryPolicyStore,
    InMemoryRunStore,
    InMemorySecretStore,
    InMemoryWorkspaceStore,
    JsonAgentSessionStore,
    JsonCatalogStore,
    JsonPolicyStore,
    JsonRunStore,
    JsonSecretStore,
    JsonWorkspaceStore,
    LocalArtifactStore,
    LocalMarkdownMemoryStore,
)
from bkl_engine.infrastructure.repositories import InMemorySkillRegistry, InMemoryToolRegistry
from bkl_engine.infrastructure.tool_runners import ApiToolRunner, PythonToolRunner
from bkl_engine.infrastructure.tracing import InMemoryTraceStore, JsonTraceStore


class SkillEngine:
    def __init__(
        self,
        skill_registry: InMemorySkillRegistry,
        tool_registry: InMemoryToolRegistry,
        model_router: ModelRouter,
        tool_executor: ToolExecutorPort,
        trace_store: InMemoryTraceStore,
        artifact_store: LocalArtifactStore,
        run_store: InMemoryRunStore,
        session_store: AgentSessionStorePort | None = None,
        memory_store: MemoryStorePort | None = None,
        workspace_store: WorkspaceStorePort | None = None,
        policy_store: InMemoryPolicyStore | JsonPolicyStore | None = None,
        secret_store: InMemorySecretStore | JsonSecretStore | None = None,
        catalog_store: JsonCatalogStore | None = None,
    ) -> None:
        self.skill_registry = skill_registry
        self.tool_registry = tool_registry
        self.model_router = model_router
        self.tool_executor = tool_executor
        self.trace_store = trace_store
        self.artifact_store = artifact_store
        self.run_store = run_store
        self.session_store: AgentSessionStorePort = session_store or InMemoryAgentSessionStore()
        self.memory_store = memory_store
        self.workspace_store: WorkspaceStorePort = workspace_store or InMemoryWorkspaceStore()
        self.policy_store = policy_store or InMemoryPolicyStore()
        self.secret_store = secret_store or InMemorySecretStore()
        self.catalog_store = catalog_store
        self.runtime = SkillRuntime(
            skill_registry=skill_registry,
            tool_registry=tool_registry,
            model_router=model_router,
            tool_executor=tool_executor,
            trace_store=trace_store,
            artifact_store=artifact_store,
            run_store=run_store,
            prompt_context_assembler=(
                PromptContextAssembler(memory_store) if memory_store is not None else None
            ),
        )

    @classmethod
    def load(
        cls,
        config_path: str | Path | None = None,
        catalog_path: str | Path | None = None,
        workspace_path: str | Path | None = None,
        session_path: str | Path | None = None,
        run_path: str | Path | None = None,
        trace_path: str | Path | None = None,
        policy_path: str | Path | None = None,
        secret_path: str | Path | None = None,
    ) -> "SkillEngine":
        config = load_engine_config(config_path or "bkl.yaml")
        catalog_store = JsonCatalogStore(catalog_path) if catalog_path is not None else None
        state_dir = _state_dir(catalog_path)
        policy_store = JsonPolicyStore(policy_path or state_dir / "policies.json")
        secret_store = JsonSecretStore(secret_path or state_dir / "secrets.json")
        engine = cls(
            skill_registry=InMemorySkillRegistry(),
            tool_registry=InMemoryToolRegistry(),
            model_router=ModelRouter.from_config(config),
            tool_executor=_default_tool_executor(policy_store, secret_store),
            trace_store=JsonTraceStore(trace_path or state_dir / "traces.json"),
            artifact_store=LocalArtifactStore("data/artifacts"),
            run_store=JsonRunStore(run_path or state_dir / "runs.json"),
            session_store=JsonAgentSessionStore(session_path or state_dir / "sessions.json"),
            memory_store=LocalMarkdownMemoryStore(state_dir / "memory"),
            workspace_store=JsonWorkspaceStore(workspace_path or state_dir / "workspaces.json"),
            policy_store=policy_store,
            secret_store=secret_store,
            catalog_store=catalog_store,
        )
        engine.load_catalog()
        return engine

    @classmethod
    def create_for_testing(
        cls,
        artifact_root: str | Path = "data/artifacts",
        model_provider: ModelProvider | None = None,
        tool_executor: ToolExecutorPort | None = None,
        memory_root: str | Path | None = None,
    ) -> "SkillEngine":
        policy_store = InMemoryPolicyStore()
        secret_store = InMemorySecretStore()
        resolved_artifact_root = Path(artifact_root)
        return cls(
            skill_registry=InMemorySkillRegistry(),
            tool_registry=InMemoryToolRegistry(),
            model_router=ModelRouter(model_provider or MockModelProvider()),
            tool_executor=tool_executor or _default_tool_executor(policy_store, secret_store),
            trace_store=InMemoryTraceStore(),
            artifact_store=LocalArtifactStore(resolved_artifact_root),
            run_store=InMemoryRunStore(),
            session_store=InMemoryAgentSessionStore(),
            memory_store=LocalMarkdownMemoryStore(
                memory_root or resolved_artifact_root / ".bkl" / "memory"
            ),
            workspace_store=InMemoryWorkspaceStore(),
            policy_store=policy_store,
            secret_store=secret_store,
        )

    async def register_tool(self, path: str | Path) -> Tool:
        tool = self.tool_registry.register_tool(path)
        if self.catalog_store is not None:
            self.catalog_store.upsert_tool(tool)
        return tool

    async def register_skill(self, path: str | Path) -> Skill:
        skill = self.skill_registry.register_skill(path)
        if self.catalog_store is not None:
            self.catalog_store.upsert_skill(skill)
        return skill

    def load_catalog(self) -> None:
        if self.catalog_store is None:
            return
        for entry in self.catalog_store.list_tools():
            if entry.enabled and Path(entry.path).exists():
                self.tool_registry.register_tool(entry.path)
        for entry in self.catalog_store.list_skills():
            if entry.enabled and Path(entry.path).exists():
                self.skill_registry.register_skill(entry.path)

    async def run_skill(
        self,
        skill_id: str,
        input_data: dict[str, object],
        context: RunContext | None = None,
    ) -> RunResult:
        return await self.runtime.run_skill(skill_id, input_data, context)

    async def resume_run(self, run_id: str) -> RunResult:
        return await self.runtime.resume_run(run_id)


def _default_tool_executor(
    policy_store: InMemoryPolicyStore | JsonPolicyStore | None = None,
    secret_store: InMemorySecretStore | JsonSecretStore | None = None,
) -> ToolExecutor:
    return ToolExecutor(
        python_runner=PythonToolRunner(),
        api_runner=ApiToolRunner(),
        policy_engine=PolicyEngine(policy_store),
        secret_store=secret_store,
    )


def _state_dir(catalog_path: str | Path | None) -> Path:
    if catalog_path is not None:
        return Path(catalog_path).parent
    return Path(".bkl")
