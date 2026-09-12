"""Tool policy store primitives."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError

from app.domain.errors import BklEngineError
from app.domain.policy import (
    PolicyEffect,
    ToolApprovalRecord,
    ToolApprovalStatus,
    ToolPolicyRule,
)


class PolicyDocument(BaseModel):
    version: int = 1
    tool_rules: dict[str, ToolPolicyRule] = Field(default_factory=dict)
    tool_approvals: dict[str, ToolApprovalRecord] = Field(default_factory=dict)


class InMemoryPolicyStore:
    def __init__(self) -> None:
        self._tool_rules: dict[str, ToolPolicyRule] = {}
        self._tool_approvals: dict[str, ToolApprovalRecord] = {}

    def set_tool_rule(
        self,
        tool_id: str,
        effect: PolicyEffect,
        workspace_id: str | None = None,
        identity_id: str | None = None,
        reason: str = "",
        risk: str = "none",
        enabled: bool = True,
    ) -> ToolPolicyRule:
        rule_id = _tool_rule_id(tool_id, workspace_id, identity_id)
        existing = self._tool_rules.get(rule_id)
        now = datetime.now(UTC)
        rule = ToolPolicyRule(
            rule_id=rule_id,
            tool_id=tool_id,
            effect=effect,
            workspace_id=workspace_id,
            identity_id=identity_id,
            reason=reason,
            risk=risk,
            enabled=enabled,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        self._tool_rules[rule_id] = rule
        return rule

    def get_tool_rule(self, rule_id: str) -> ToolPolicyRule:
        rule = self._tool_rules.get(rule_id)
        if rule is None:
            raise BklEngineError("POLICY_RULE_NOT_FOUND", f"Policy rule not found: {rule_id}")
        return rule

    def list_tool_rules(
        self,
        workspace_id: str | None = None,
        identity_id: str | None = None,
    ) -> list[ToolPolicyRule]:
        rules = list(self._tool_rules.values())
        if workspace_id is not None:
            rules = [rule for rule in rules if rule.workspace_id == workspace_id]
        if identity_id is not None:
            rules = [rule for rule in rules if rule.identity_id == identity_id]
        return rules

    def find_tool_rule(
        self,
        tool_id: str,
        workspace_id: str | None = None,
        identity_id: str | None = None,
    ) -> ToolPolicyRule | None:
        for rule_id in _candidate_rule_ids(tool_id, workspace_id, identity_id):
            rule = self._tool_rules.get(rule_id)
            if rule is not None and rule.enabled:
                return rule
        return None

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
        approval = ToolApprovalRecord(
            approval_id=f"approval_{uuid4().hex}",
            tool_id=tool_id,
            workspace_id=workspace_id,
            identity_id=identity_id,
            skill_id=skill_id,
            run_id=run_id,
            tool_call_id=tool_call_id,
            rule_id=rule_id,
            reason=reason,
            risk=risk,
        )
        self._tool_approvals[approval.approval_id] = approval
        return approval

    def get_tool_approval(self, approval_id: str) -> ToolApprovalRecord:
        approval = self._tool_approvals.get(approval_id)
        if approval is None:
            raise BklEngineError(
                "TOOL_APPROVAL_NOT_FOUND",
                f"Tool approval not found: {approval_id}",
            )
        return approval

    def list_tool_approvals(
        self,
        workspace_id: str | None = None,
        identity_id: str | None = None,
        status: ToolApprovalStatus | None = None,
    ) -> list[ToolApprovalRecord]:
        approvals = list(self._tool_approvals.values())
        if workspace_id is not None:
            approvals = [
                approval for approval in approvals
                if approval.workspace_id == workspace_id
            ]
        if identity_id is not None:
            approvals = [
                approval for approval in approvals
                if approval.identity_id == identity_id
            ]
        if status is not None:
            approvals = [approval for approval in approvals if approval.status == status]
        return approvals

    def approve_tool_approval(
        self,
        approval_id: str,
        decided_by: str | None = None,
    ) -> ToolApprovalRecord:
        return self._decide_tool_approval(approval_id, "approved", decided_by)

    def deny_tool_approval(
        self,
        approval_id: str,
        decided_by: str | None = None,
    ) -> ToolApprovalRecord:
        return self._decide_tool_approval(approval_id, "denied", decided_by)

    def find_active_tool_approval(
        self,
        tool_id: str,
        workspace_id: str | None = None,
        identity_id: str | None = None,
        skill_id: str | None = None,
    ) -> ToolApprovalRecord | None:
        approvals = [
            approval
            for approval in self._tool_approvals.values()
            if approval.status == "approved"
            and approval.tool_id == tool_id
            and approval.workspace_id == workspace_id
            and approval.identity_id == identity_id
            and approval.skill_id == skill_id
        ]
        if not approvals:
            return None
        return sorted(
            approvals,
            key=lambda approval: approval.decided_at or approval.requested_at,
        )[-1]

    def _decide_tool_approval(
        self,
        approval_id: str,
        status: ToolApprovalStatus,
        decided_by: str | None,
    ) -> ToolApprovalRecord:
        approval = self.get_tool_approval(approval_id)
        updated = approval.model_copy(
            update={
                "status": status,
                "decided_at": datetime.now(UTC),
                "decided_by": decided_by,
            }
        )
        self._tool_approvals[approval_id] = updated
        return updated


class JsonPolicyStore(InMemoryPolicyStore):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        super().__init__()
        self._load_into_memory()

    def set_tool_rule(
        self,
        tool_id: str,
        effect: PolicyEffect,
        workspace_id: str | None = None,
        identity_id: str | None = None,
        reason: str = "",
        risk: str = "none",
        enabled: bool = True,
    ) -> ToolPolicyRule:
        rule = super().set_tool_rule(
            tool_id,
            effect,
            workspace_id=workspace_id,
            identity_id=identity_id,
            reason=reason,
            risk=risk,
            enabled=enabled,
        )
        self._save()
        return rule

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
        approval = super().create_tool_approval(
            tool_id,
            workspace_id=workspace_id,
            identity_id=identity_id,
            skill_id=skill_id,
            run_id=run_id,
            tool_call_id=tool_call_id,
            rule_id=rule_id,
            reason=reason,
            risk=risk,
        )
        self._save()
        return approval

    def approve_tool_approval(
        self,
        approval_id: str,
        decided_by: str | None = None,
    ) -> ToolApprovalRecord:
        approval = super().approve_tool_approval(approval_id, decided_by)
        self._save()
        return approval

    def deny_tool_approval(
        self,
        approval_id: str,
        decided_by: str | None = None,
    ) -> ToolApprovalRecord:
        approval = super().deny_tool_approval(approval_id, decided_by)
        self._save()
        return approval

    def _load_into_memory(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            document = PolicyDocument.model_validate(raw)
        except json.JSONDecodeError as exc:
            raise BklEngineError(
                "POLICY_STORE_INVALID",
                f"Invalid policy store JSON: {self.path}",
            ) from exc
        except ValidationError as exc:
            raise BklEngineError(
                "POLICY_STORE_INVALID",
                f"Invalid policy store shape: {self.path}",
            ) from exc
        self._tool_rules = dict(document.tool_rules)
        self._tool_approvals = dict(document.tool_approvals)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        document = PolicyDocument(
            tool_rules=dict(self._tool_rules),
            tool_approvals=dict(self._tool_approvals),
        )
        self.path.write_text(
            json.dumps(document.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _tool_rule_id(
    tool_id: str,
    workspace_id: str | None = None,
    identity_id: str | None = None,
) -> str:
    if workspace_id is not None and identity_id is not None:
        return f"identity:{workspace_id}:{identity_id}:{tool_id}"
    if workspace_id is not None:
        return f"workspace:{workspace_id}:{tool_id}"
    return f"global:{tool_id}"


def _candidate_rule_ids(
    tool_id: str,
    workspace_id: str | None,
    identity_id: str | None,
) -> list[str]:
    candidates: list[str] = []
    if workspace_id is not None and identity_id is not None:
        candidates.append(_tool_rule_id(tool_id, workspace_id, identity_id))
    if workspace_id is not None:
        candidates.append(_tool_rule_id(tool_id, workspace_id, None))
    candidates.append(_tool_rule_id(tool_id, None, None))
    return candidates
