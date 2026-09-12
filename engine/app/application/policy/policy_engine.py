"""Policy engine primitives."""

from typing import Protocol

from app.domain.policy import PolicyDecision, ToolApprovalRecord, ToolPolicyRule
from app.domain.tool import Tool, ToolExecutionContext


class ToolExecutionPolicy(Protocol):
    def evaluate_tool_execution(
        self,
        tool: Tool,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> PolicyDecision:
        ...


class ToolPolicyStore(Protocol):
    def find_tool_rule(
        self,
        tool_id: str,
        workspace_id: str | None = None,
        identity_id: str | None = None,
    ) -> ToolPolicyRule | None:
        ...

    def create_tool_approval(
        self,
        tool_id: str,
        workspace_id: str | None = None,
        identity_id: str | None = None,
        skill_id: str | None = None,
        run_id: str | None = None,
        tool_call_id: str | None = None,
        rule_id: str | None = None,
        reason: str = "",
        risk: str = "none",
    ) -> ToolApprovalRecord:
        ...

    def find_active_tool_approval(
        self,
        tool_id: str,
        workspace_id: str | None = None,
        identity_id: str | None = None,
        skill_id: str | None = None,
    ) -> ToolApprovalRecord | None:
        ...


class PolicyEngine:
    """Default policy engine.

    The v0.1 default stays permissive to preserve existing local behavior.
    Product deployments can inject stricter implementations through ToolExecutor.
    """

    def __init__(self, policy_store: ToolPolicyStore | None = None) -> None:
        self.policy_store = policy_store

    def evaluate_tool_execution(
        self,
        tool: Tool,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> PolicyDecision:
        del arguments
        if self.policy_store is None:
            return PolicyDecision(effect="allow", reason="default policy")

        rule = self.policy_store.find_tool_rule(
            tool.id,
            workspace_id=context.workspace_id,
            identity_id=context.identity_id,
        )
        if rule is None:
            return PolicyDecision(effect="allow", reason="no matching policy rule")

        scope = "identity" if rule.identity_id is not None else "workspace"
        if rule.workspace_id is None:
            scope = "global"
        details = {
            "rule_id": rule.rule_id,
            "scope": scope,
            "workspace_id": rule.workspace_id,
            "identity_id": rule.identity_id,
            "tool_id": rule.tool_id,
        }
        if rule.effect != "ask":
            return PolicyDecision(
                effect=rule.effect,
                reason=rule.reason or f"matched {scope} tool policy rule",
                risk=rule.risk,
                details=details,
            )

        approval = self.policy_store.find_active_tool_approval(
            tool.id,
            workspace_id=context.workspace_id,
            identity_id=context.identity_id,
            skill_id=context.skill_id,
        )
        if approval is not None:
            return PolicyDecision(
                effect="allow",
                reason="approved tool policy request",
                risk=rule.risk,
                details={
                    **details,
                    "approval_id": approval.approval_id,
                    "approval_status": approval.status,
                },
            )

        requested = self.policy_store.create_tool_approval(
            tool.id,
            workspace_id=context.workspace_id,
            identity_id=context.identity_id,
            skill_id=context.skill_id,
            run_id=context.run_id,
            tool_call_id=context.tool_call_id,
            rule_id=rule.rule_id,
            reason=rule.reason or f"matched {scope} tool policy rule",
            risk=rule.risk,
        )
        return PolicyDecision(
            effect="ask",
            reason=rule.reason or f"matched {scope} tool policy rule",
            risk=rule.risk,
            details={
                **details,
                "approval_id": requested.approval_id,
                "approval_status": requested.status,
            },
        )
