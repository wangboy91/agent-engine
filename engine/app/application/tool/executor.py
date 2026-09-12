"""Tool executor primitives."""

from typing import Protocol

from app.application.policy import PolicyEngine, ToolExecutionPolicy
from app.application.ports import ToolRunnerPort
from app.domain.errors import BklEngineError
from app.domain.policy import PolicyDecision
from app.domain.secret import SecretRecord
from app.domain.tool import Tool, ToolExecutionContext, ToolExecutionResult


class SecretResolver(Protocol):
    def get_secret(self, name: str, workspace_id: str | None = None) -> SecretRecord:
        ...


class ToolExecutor:
    def __init__(
        self,
        python_runner: ToolRunnerPort,
        api_runner: ToolRunnerPort,
        policy_engine: ToolExecutionPolicy | None = None,
        secret_store: SecretResolver | None = None,
    ) -> None:
        self.python_runner = python_runner
        self.api_runner = api_runner
        self.policy_engine = policy_engine or PolicyEngine()
        self.secret_store = secret_store

    def evaluate_policy(
        self,
        tool: Tool,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> PolicyDecision:
        return self.policy_engine.evaluate_tool_execution(tool, arguments, context)

    async def execute(
        self,
        tool: Tool,
        arguments: dict[str, object],
        context: ToolExecutionContext,
        policy_decision: PolicyDecision | None = None,
    ) -> ToolExecutionResult:
        decision = policy_decision or self.evaluate_policy(tool, arguments, context)
        self._ensure_policy_allows(tool, decision)
        resolved_arguments = self._resolve_secret_refs(tool, arguments, context)
        if tool.type == "python":
            return await self.python_runner.execute(tool, resolved_arguments, context)
        if tool.type == "api":
            return await self.api_runner.execute(tool, resolved_arguments, context)
        raise BklEngineError("TOOL_TYPE_UNSUPPORTED", f"Unsupported tool type: {tool.type}")

    def _ensure_policy_allows(self, tool: Tool, decision: PolicyDecision) -> None:
        if decision.effect == "allow":
            return
        if decision.effect == "ask":
            raise BklEngineError(
                "TOOL_REQUIRES_CONFIRMATION",
                f"Tool requires confirmation: {tool.id}",
                {"reason": decision.reason, "risk": decision.risk, **decision.details},
            )
        raise BklEngineError(
            "TOOL_POLICY_DENIED",
            f"Tool execution denied: {tool.id}",
            {"reason": decision.reason, "risk": decision.risk, **decision.details},
        )

    def _resolve_secret_refs(
        self,
        tool: Tool,
        value: dict[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        resolved = self._resolve_secret_value(tool, value, context)
        if not isinstance(resolved, dict):
            raise BklEngineError("SECRET_REF_INVALID", "Tool arguments must resolve to an object")
        return resolved

    def _resolve_secret_value(
        self,
        tool: Tool,
        value: object,
        context: ToolExecutionContext,
    ) -> object:
        if isinstance(value, dict):
            secret_name = value.get("secret_ref") or value.get("$secret")
            if isinstance(secret_name, str):
                return self._resolve_secret(tool, secret_name, context)
            return {
                key: self._resolve_secret_value(tool, item, context)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._resolve_secret_value(tool, item, context) for item in value]
        return value

    def _resolve_secret(
        self,
        tool: Tool,
        name: str,
        context: ToolExecutionContext,
    ) -> str:
        if self.secret_store is None:
            raise BklEngineError("SECRET_STORE_NOT_CONFIGURED", "Secret store is not configured")
        if name not in tool.permissions.secrets:
            raise BklEngineError(
                "SECRET_NOT_ALLOWED",
                f"Tool is not allowed to access secret: {name}",
                {"tool_id": tool.id, "secret": name},
            )
        return self.secret_store.get_secret(name, context.workspace_id).value
