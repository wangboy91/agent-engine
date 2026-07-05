"""Skill runtime primitives."""

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate

from bkl_engine.application.ports import (
    ArtifactStorePort,
    ModelGatewayPort,
    RunStorePort,
    SkillRegistryPort,
    ToolExecutorPort,
    ToolRegistryPort,
    TraceStorePort,
)
from bkl_engine.domain.errors import BklEngineError
from bkl_engine.domain.execution import (
    EngineError,
    RunContext,
    RunResult,
    UsageSummary,
)
from bkl_engine.domain.model import ModelResponse, ToolCallRequest
from bkl_engine.domain.skill import Skill, SkillWorkflowStep
from bkl_engine.domain.tool import Tool, ToolExecutionContext


class SkillRuntimeError(BklEngineError):
    """Raised when a Skill run fails."""


class SkillRuntime:
    def __init__(
        self,
        skill_registry: SkillRegistryPort,
        tool_registry: ToolRegistryPort,
        model_router: ModelGatewayPort,
        tool_executor: ToolExecutorPort,
        trace_store: TraceStorePort,
        artifact_store: ArtifactStorePort,
        run_store: RunStorePort,
    ) -> None:
        self.skill_registry = skill_registry
        self.tool_registry = tool_registry
        self.model_router = model_router
        self.tool_executor = tool_executor
        self.trace_store = trace_store
        self.artifact_store = artifact_store
        self.run_store = run_store

    async def run_skill(
        self,
        skill_id: str,
        input_data: dict[str, object],
        context: RunContext | None = None,
    ) -> RunResult:
        skill = self.skill_registry.get_skill(skill_id)
        run_id = f"run_{uuid4().hex}"
        run = RunResult(
            run_id=run_id,
            status="running",
            skill_id=skill.id,
            input=input_data,
            context=context,
        )
        self.run_store.save(run)
        self.trace_store.record(
            run_id,
            "skill_started",
            "Skill started",
            {"skill_id": skill.id, **self._context_trace_data(context)},
        )

        try:
            self._validate_schema(skill.input_schema, input_data, "INPUT_SCHEMA_INVALID")
            if skill.workflow is not None:
                result = await self._run_workflow(run_id, skill, input_data, context)
            elif skill.execution.type == "direct_tool":
                allowed_tools = self.tool_registry.get_allowed_tools(skill.allowed_tools)
                result = await self._run_direct_tool(
                    run_id,
                    skill,
                    input_data,
                    allowed_tools,
                    context,
                )
            else:
                allowed_tools = self.tool_registry.get_allowed_tools(skill.allowed_tools)
                result = await self._run_loop(run_id, skill, input_data, allowed_tools, context)
            self.run_store.save(result)
            return result
        except BklEngineError as exc:
            if exc.code == "TOOL_REQUIRES_CONFIRMATION":
                waiting = run.model_copy(
                    update={
                        "status": "waiting_approval",
                        "error": EngineError(
                            code=exc.code,
                            message=exc.message,
                            details=exc.details,
                            retryable=exc.retryable,
                        ),
                        "pending_approval": exc.details,
                        "trace_summary": self._trace_summary(run_id),
                    }
                )
                self.trace_store.record(
                    run_id,
                    "skill_waiting_approval",
                    "Skill waiting for approval",
                    {"code": exc.code, "message": exc.message, "details": exc.details},
                )
                self.run_store.save(waiting)
                return waiting
            failed = run.model_copy(
                update={
                    "status": "failed",
                    "error": EngineError(
                        code=exc.code,
                        message=exc.message,
                        details=exc.details,
                        retryable=exc.retryable,
                    ),
                    "trace_summary": self._trace_summary(run_id),
                    "completed_at": datetime.now(UTC),
                }
            )
            self.trace_store.record(
                run_id,
                "skill_failed",
                "Skill failed",
                {"code": exc.code, "message": exc.message},
            )
            self.run_store.save(failed)
            if isinstance(exc, SkillRuntimeError):
                raise
            raise SkillRuntimeError(exc.code, exc.message, exc.details, exc.retryable) from exc

    async def resume_run(self, run_id: str) -> RunResult:
        run = self.run_store.get(run_id)
        if run.status != "waiting_approval":
            raise SkillRuntimeError(
                "RUN_NOT_WAITING_APPROVAL",
                f"Run is not waiting for approval: {run_id}",
            )

        skill = self.skill_registry.get_skill(run.skill_id)
        self.trace_store.record(
            run_id,
            "run_resumed",
            "Run resumed",
            {"skill_id": skill.id, **self._context_trace_data(run.context)},
        )

        try:
            self._validate_schema(skill.input_schema, run.input, "INPUT_SCHEMA_INVALID")
            if skill.workflow is not None:
                result = await self._run_workflow(run_id, skill, run.input, run.context)
            elif skill.execution.type == "direct_tool":
                allowed_tools = self.tool_registry.get_allowed_tools(skill.allowed_tools)
                result = await self._run_direct_tool(
                    run_id,
                    skill,
                    run.input,
                    allowed_tools,
                    run.context,
                )
            else:
                allowed_tools = self.tool_registry.get_allowed_tools(skill.allowed_tools)
                result = await self._run_loop(run_id, skill, run.input, allowed_tools, run.context)
            self.run_store.save(result)
            return result
        except BklEngineError as exc:
            if exc.code == "TOOL_REQUIRES_CONFIRMATION":
                waiting = run.model_copy(
                    update={
                        "error": EngineError(
                            code=exc.code,
                            message=exc.message,
                            details=exc.details,
                            retryable=exc.retryable,
                        ),
                        "pending_approval": exc.details,
                        "trace_summary": self._trace_summary(run_id),
                    }
                )
                self.run_store.save(waiting)
                return waiting
            raise

    async def _run_workflow(
        self,
        run_id: str,
        skill: Skill,
        input_data: dict[str, object],
        context: RunContext | None,
    ) -> RunResult:
        if skill.workflow is None:
            raise SkillRuntimeError("WORKFLOW_NOT_CONFIGURED", "Skill has no workflow config")

        if self._workflow_uses_dag(skill):
            return await self._run_workflow_dag(run_id, skill, input_data, context)

        workflow_context: dict[str, object] = dict(input_data)
        workflow_output: dict[str, object] = {}
        step_runs: list[dict[str, object]] = []
        usage = UsageSummary()

        for step in skill.workflow.steps:
            self.trace_store.record(
                run_id,
                "workflow_step_started",
                "Workflow step started",
                {"step_id": step.id, "skill_id": step.skill_id},
            )
            try:
                child_result = await self.run_skill(
                    step.skill_id,
                    dict(workflow_context),
                    self._child_context(context, run_id, step.id),
                )
            except BklEngineError as exc:
                details: dict[str, object] = {
                    "step_id": step.id,
                    "skill_id": step.skill_id,
                    "cause_code": exc.code,
                    "cause_message": exc.message,
                    "cause_details": exc.details,
                }
                self.trace_store.record(
                    run_id,
                    "workflow_step_failed",
                    "Workflow step failed",
                    details,
                )
                raise SkillRuntimeError(
                    "WORKFLOW_STEP_FAILED",
                    (
                        f"Workflow step failed: {step.id} "
                        f"({step.skill_id}): {exc.code}: {exc.message}"
                    ),
                    details,
                    exc.retryable,
                ) from exc

            if child_result.output is None:
                raise SkillRuntimeError(
                    "WORKFLOW_STEP_EMPTY_OUTPUT",
                    f"Workflow step returned no output: {step.id}",
                    {"step_id": step.id, "skill_id": step.skill_id},
                )

            workflow_context.update(child_result.output)
            workflow_output.update(child_result.output)
            usage.input_tokens += child_result.usage.input_tokens
            usage.output_tokens += child_result.usage.output_tokens
            usage.model_cost += child_result.usage.model_cost
            usage.tool_cost += child_result.usage.tool_cost
            usage.credits_charged += child_result.usage.credits_charged

            step_runs.append(
                {
                    "step_id": step.id,
                    "skill_id": step.skill_id,
                    "run_id": child_result.run_id,
                    "status": child_result.status,
                    "trace_summary": child_result.trace_summary,
                    "artifacts": [
                        artifact.model_dump(mode="json")
                        for artifact in child_result.artifacts
                    ],
                }
            )
            self.trace_store.record(
                run_id,
                "workflow_step_succeeded",
                "Workflow step succeeded",
                {
                    "step_id": step.id,
                    "skill_id": step.skill_id,
                    "run_id": child_result.run_id,
                },
            )

        final_output = {
            "workflow_id": skill.id,
            "input": input_data,
            "step_runs": step_runs,
            **workflow_output,
        }
        self._validate_schema(skill.output_schema, final_output, "OUTPUT_SCHEMA_INVALID")

        if skill.workflow.output_artifact:
            self.artifact_store.save_text(
                run_id=run_id,
                content=json.dumps(final_output, ensure_ascii=False, indent=2),
                artifact_type="json",
                filename=skill.workflow.output_artifact,
                mime_type="application/json",
            )

        result = RunResult(
            run_id=run_id,
            status="succeeded",
            skill_id=skill.id,
            input=input_data,
            context=context,
            output=final_output,
            artifacts=self.artifact_store.list_by_run(run_id),
            trace_summary=self._trace_summary(run_id),
            usage=usage,
            completed_at=datetime.now(UTC),
        )
        self.trace_store.record(
            run_id,
            "skill_succeeded",
            "Skill succeeded",
            {"skill_id": skill.id},
        )
        return result

    async def _run_workflow_dag(
        self,
        run_id: str,
        skill: Skill,
        input_data: dict[str, object],
        context: RunContext | None,
    ) -> RunResult:
        if skill.workflow is None:
            raise SkillRuntimeError("WORKFLOW_NOT_CONFIGURED", "Skill has no workflow config")

        workflow_context: dict[str, object] = dict(input_data)
        workflow_output: dict[str, object] = {}
        step_runs: list[dict[str, object]] = []
        usage = UsageSummary()
        completed: set[str] = set()
        pending = {step.id: step for step in skill.workflow.steps}

        while pending:
            ready_steps = [
                step
                for step in skill.workflow.steps
                if step.id in pending and all(dep in completed for dep in step.depends_on)
            ]
            if not ready_steps:
                raise SkillRuntimeError(
                    "WORKFLOW_DEPENDENCY_CYCLE",
                    f"Workflow dependency graph cannot make progress: {skill.id}",
                    {"pending_step_ids": list(pending.keys())},
                )

            wave = ready_steps[: skill.workflow.max_parallel_steps]
            context_snapshot = dict(workflow_context)
            for step in wave:
                self.trace_store.record(
                    run_id,
                    "workflow_step_started",
                    "Workflow step started",
                    {
                        "step_id": step.id,
                        "skill_id": step.skill_id,
                        "depends_on": step.depends_on,
                    },
                )

            child_results = await asyncio.gather(
                *[
                    self.run_skill(
                        step.skill_id,
                        dict(context_snapshot),
                        self._child_context(context, run_id, step.id),
                    )
                    for step in wave
                ],
                return_exceptions=True,
            )

            for step, child_result in zip(wave, child_results, strict=True):
                if isinstance(child_result, BklEngineError):
                    self._record_workflow_step_failure(run_id, step, child_result)
                    raise SkillRuntimeError(
                        "WORKFLOW_STEP_FAILED",
                        (
                            f"Workflow step failed: {step.id} "
                            f"({step.skill_id}): {child_result.code}: {child_result.message}"
                        ),
                        {
                            "step_id": step.id,
                            "skill_id": step.skill_id,
                            "cause_code": child_result.code,
                            "cause_message": child_result.message,
                            "cause_details": child_result.details,
                        },
                        child_result.retryable,
                    ) from child_result
                if isinstance(child_result, BaseException):
                    raise child_result
                if child_result.output is None:
                    raise SkillRuntimeError(
                        "WORKFLOW_STEP_EMPTY_OUTPUT",
                        f"Workflow step returned no output: {step.id}",
                        {"step_id": step.id, "skill_id": step.skill_id},
                    )

            for step, child_result in zip(wave, child_results, strict=True):
                if not isinstance(child_result, RunResult):
                    continue
                workflow_context.update(child_result.output or {})
                workflow_output.update(child_result.output or {})
                usage.input_tokens += child_result.usage.input_tokens
                usage.output_tokens += child_result.usage.output_tokens
                usage.model_cost += child_result.usage.model_cost
                usage.tool_cost += child_result.usage.tool_cost
                usage.credits_charged += child_result.usage.credits_charged
                step_runs.append(self._workflow_step_run(step.id, step.skill_id, child_result))
                completed.add(step.id)
                pending.pop(step.id)
                self.trace_store.record(
                    run_id,
                    "workflow_step_succeeded",
                    "Workflow step succeeded",
                    {
                        "step_id": step.id,
                        "skill_id": step.skill_id,
                        "run_id": child_result.run_id,
                    },
                )

        final_output = {
            "workflow_id": skill.id,
            "input": input_data,
            "step_runs": step_runs,
            **workflow_output,
        }
        self._validate_schema(skill.output_schema, final_output, "OUTPUT_SCHEMA_INVALID")

        if skill.workflow.output_artifact:
            self.artifact_store.save_text(
                run_id=run_id,
                content=json.dumps(final_output, ensure_ascii=False, indent=2),
                artifact_type="json",
                filename=skill.workflow.output_artifact,
                mime_type="application/json",
            )

        result = RunResult(
            run_id=run_id,
            status="succeeded",
            skill_id=skill.id,
            input=input_data,
            context=context,
            output=final_output,
            artifacts=self.artifact_store.list_by_run(run_id),
            trace_summary=self._trace_summary(run_id),
            usage=usage,
            completed_at=datetime.now(UTC),
        )
        self.trace_store.record(
            run_id,
            "skill_succeeded",
            "Skill succeeded",
            {"skill_id": skill.id},
        )
        return result

    def _workflow_uses_dag(self, skill: Skill) -> bool:
        if skill.workflow is None:
            return False
        return (
            skill.workflow.max_parallel_steps > 1
            or any(step.depends_on for step in skill.workflow.steps)
        )

    def _workflow_step_run(
        self,
        step_id: str,
        skill_id: str,
        child_result: RunResult,
    ) -> dict[str, object]:
        return {
            "step_id": step_id,
            "skill_id": skill_id,
            "run_id": child_result.run_id,
            "status": child_result.status,
            "trace_summary": child_result.trace_summary,
            "artifacts": [
                artifact.model_dump(mode="json")
                for artifact in child_result.artifacts
            ],
        }

    def _record_workflow_step_failure(
        self,
        run_id: str,
        step: SkillWorkflowStep,
        exc: BklEngineError,
    ) -> None:
        self.trace_store.record(
            run_id,
            "workflow_step_failed",
            "Workflow step failed",
            {
                "step_id": step.id,
                "skill_id": step.skill_id,
                "cause_code": exc.code,
                "cause_message": exc.message,
                "cause_details": exc.details,
            },
        )

    def _context_trace_data(self, context: RunContext | None) -> dict[str, object]:
        if context is None:
            return {}
        data: dict[str, object] = {}
        for key in ("user_id", "workspace_id", "identity_id", "role_id", "project_id"):
            value = getattr(context, key)
            if value is not None:
                data[key] = value
        for key in ("stream_id", "parent_run_id", "workflow_step_id"):
            value = context.metadata.get(key)
            if isinstance(value, str):
                data[key] = value
        return data

    def _tool_context_data(self, context: RunContext | None) -> dict[str, str | None]:
        if context is None:
            return {}
        data: dict[str, str | None] = {}
        for key in ("user_id", "workspace_id", "identity_id", "role_id", "project_id"):
            value = getattr(context, key)
            if value is not None:
                data[key] = value
        return data

    def _child_context(
        self,
        context: RunContext | None,
        parent_run_id: str,
        step_id: str,
    ) -> RunContext:
        metadata = dict(context.metadata) if context is not None else {}
        metadata.update({"parent_run_id": parent_run_id, "workflow_step_id": step_id})
        return RunContext(
            user_id=context.user_id if context is not None else None,
            workspace_id=context.workspace_id if context is not None else None,
            identity_id=context.identity_id if context is not None else None,
            role_id=context.role_id if context is not None else None,
            project_id=context.project_id if context is not None else None,
            metadata=metadata,
        )

    async def _run_loop(
        self,
        run_id: str,
        skill: Skill,
        input_data: dict[str, object],
        allowed_tools: list[Tool],
        context: RunContext | None,
    ) -> RunResult:
        messages = self._build_messages(skill, input_data)
        tool_call_count = 0
        usage = UsageSummary()

        for _ in range(skill.limits.max_iterations):
            model_response = await self._chat_with_retries(
                run_id,
                skill,
                messages,
                self._tools_to_llm_schema(allowed_tools),
                context,
            )
            usage.input_tokens += model_response.usage.input_tokens
            usage.output_tokens += model_response.usage.output_tokens
            usage.model_cost += model_response.usage.cost
            self.trace_store.record(
                run_id,
                "llm_called",
                "Model called",
                {
                    "tool_call_count": len(model_response.tool_calls),
                    "has_final_output": model_response.final_output is not None,
                },
            )

            if model_response.final_output is not None:
                final_output = self._normalize_value_for_schema(
                    skill.output_schema,
                    model_response.final_output,
                )
                final_output_dict = cast(dict[str, object], final_output)
                self._validate_schema(
                    skill.output_schema,
                    final_output_dict,
                    "OUTPUT_SCHEMA_INVALID",
                )
                self._save_output_artifact(
                    run_id,
                    final_output_dict,
                    f"{skill.id}-output.json",
                )
                result = RunResult(
                    run_id=run_id,
                    status="succeeded",
                    skill_id=skill.id,
                    input=input_data,
                    context=context,
                    output=final_output_dict,
                    artifacts=self.artifact_store.list_by_run(run_id),
                    trace_summary=self._trace_summary(run_id),
                    usage=usage,
                    completed_at=datetime.now(UTC),
                )
                self.trace_store.record(
                    run_id,
                    "skill_succeeded",
                    "Skill succeeded",
                    {"skill_id": skill.id},
                )
                return result

            for tool_call in model_response.tool_calls:
                tool_call_count += 1
                if tool_call_count > skill.limits.max_tool_calls:
                    raise SkillRuntimeError(
                        "MAX_TOOL_CALLS_EXCEEDED",
                        "Maximum tool calls exceeded",
                    )

                tool = self._find_allowed_tool(allowed_tools, tool_call.tool_id)
                messages.append(self._assistant_tool_call_message(tool_call))
                tool_artifact_dir = self.artifact_store.tool_artifact_dir(run_id, tool_call.id)
                tool_context = ToolExecutionContext(
                    run_id=run_id,
                    skill_id=skill.id,
                    tool_call_id=tool_call.id,
                    artifact_dir=tool_artifact_dir,
                    **self._tool_context_data(context),
                )
                self.trace_store.record(
                    run_id,
                    "tool_called",
                    "Tool called",
                    {"tool_id": tool.id, "tool_call_id": tool_call.id},
                )
                policy_decision = self.tool_executor.evaluate_policy(
                    tool, tool_call.arguments, tool_context
                )
                self.trace_store.record(
                    run_id,
                    "tool_policy_checked",
                    "Tool policy checked",
                    {
                        "tool_id": tool.id,
                        "tool_call_id": tool_call.id,
                        "effect": policy_decision.effect,
                        "reason": policy_decision.reason,
                        "risk": policy_decision.risk,
                        "details": policy_decision.details,
                    },
                )
                try:
                    tool_result = await self.tool_executor.execute(
                        tool,
                        tool_call.arguments,
                        tool_context,
                        policy_decision=policy_decision,
                    )
                except BklEngineError as exc:
                    self.trace_store.record(
                        run_id,
                        "tool_failed",
                        "Tool failed",
                        {
                            "tool_id": tool.id,
                            "tool_call_id": tool_call.id,
                            "code": exc.code,
                            "message": exc.message,
                        },
                    )
                    raise
                self.trace_store.record(
                    run_id,
                    "tool_succeeded",
                    "Tool succeeded",
                    {"tool_id": tool.id, "tool_call_id": tool_call.id},
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result.output, ensure_ascii=False),
                    }
                )

        raise SkillRuntimeError("MAX_ITERATIONS_EXCEEDED", "Maximum iterations exceeded")

    async def _run_direct_tool(
        self,
        run_id: str,
        skill: Skill,
        input_data: dict[str, object],
        allowed_tools: list[Tool],
        context: RunContext | None,
    ) -> RunResult:
        tool_id = skill.execution.tool_id
        if tool_id is None:
            raise SkillRuntimeError(
                "DIRECT_TOOL_NOT_CONFIGURED",
                f"Direct tool Skill is missing execution.tool_id: {skill.id}",
            )

        tool = self._find_allowed_tool(allowed_tools, tool_id)
        tool_call_id = f"tool_{uuid4().hex}"
        tool_context = ToolExecutionContext(
            run_id=run_id,
            skill_id=skill.id,
            tool_call_id=tool_call_id,
            artifact_dir=self.artifact_store.tool_artifact_dir(run_id, tool_call_id),
            **self._tool_context_data(context),
        )
        self.trace_store.record(
            run_id,
            "tool_called",
            "Tool called",
            {"tool_id": tool.id, "tool_call_id": tool_call_id},
        )
        policy_decision = self.tool_executor.evaluate_policy(tool, input_data, tool_context)
        self.trace_store.record(
            run_id,
            "tool_policy_checked",
            "Tool policy checked",
            {
                "tool_id": tool.id,
                "tool_call_id": tool_call_id,
                "effect": policy_decision.effect,
                "reason": policy_decision.reason,
                "risk": policy_decision.risk,
                "details": policy_decision.details,
            },
        )
        try:
            tool_result = await self.tool_executor.execute(
                tool,
                input_data,
                tool_context,
                policy_decision=policy_decision,
            )
        except BklEngineError as exc:
            self.trace_store.record(
                run_id,
                "tool_failed",
                "Tool failed",
                {
                    "tool_id": tool.id,
                    "tool_call_id": tool_call_id,
                    "code": exc.code,
                    "message": exc.message,
                },
            )
            raise

        self.trace_store.record(
            run_id,
            "tool_succeeded",
            "Tool succeeded",
            {"tool_id": tool.id, "tool_call_id": tool_call_id},
        )
        final_output = self._map_direct_tool_output(skill, tool_result.output)
        normalized_output = self._normalize_value_for_schema(skill.output_schema, final_output)
        final_output_dict = cast(dict[str, object], normalized_output)
        self._validate_schema(skill.output_schema, final_output_dict, "OUTPUT_SCHEMA_INVALID")
        self._save_output_artifact(
            run_id,
            final_output_dict,
            f"{skill.id}-output.json",
        )
        result = RunResult(
            run_id=run_id,
            status="succeeded",
            skill_id=skill.id,
            input=input_data,
            context=context,
            output=final_output_dict,
            artifacts=self.artifact_store.list_by_run(run_id),
            trace_summary=self._trace_summary(run_id),
            completed_at=datetime.now(UTC),
        )
        self.trace_store.record(
            run_id,
            "skill_succeeded",
            "Skill succeeded",
            {"skill_id": skill.id},
        )
        return result

    async def _chat_with_retries(
        self,
        run_id: str,
        skill: Skill,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        context: RunContext | None,
    ) -> ModelResponse:
        max_attempts = skill.limits.max_model_retries + 1
        stream_callback = self._model_stream_callback(run_id, skill, context)
        for attempt in range(1, max_attempts + 1):
            try:
                return await self.model_router.chat(
                    skill.model.profile,
                    messages,
                    tools,
                    stream_callback=stream_callback,
                )
            except BklEngineError as exc:
                self.trace_store.record(
                    run_id,
                    "llm_failed",
                    "Model call failed",
                    {
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "code": exc.code,
                        "message": exc.message,
                        "retryable": exc.retryable,
                    },
                )
                if not exc.retryable or attempt >= max_attempts:
                    raise
                self.trace_store.record(
                    run_id,
                    "llm_retried",
                    "Retrying model call",
                    {
                        "attempt": attempt + 1,
                        "max_attempts": max_attempts,
                        "previous_code": exc.code,
                    },
                )
        raise SkillRuntimeError("MODEL_PROVIDER_ERROR", "Model call failed")

    def _model_stream_callback(
        self,
        run_id: str,
        skill: Skill,
        context: RunContext | None,
    ) -> Callable[[str], Awaitable[None]] | None:
        if context is None or not isinstance(context.metadata.get("stream_id"), str):
            return None

        async def record_delta(delta: str) -> None:
            if not delta:
                return
            self.trace_store.record(
                run_id,
                "llm_delta",
                "Model content delta",
                {
                    "skill_id": skill.id,
                    "delta": delta,
                    **self._context_trace_data(context),
                },
            )

        return record_delta

    def _map_direct_tool_output(
        self,
        skill: Skill,
        tool_output: dict[str, object],
    ) -> dict[str, object]:
        if not skill.execution.output_mapping:
            return dict(tool_output)

        mapped: dict[str, object] = {}
        for destination, source in skill.execution.output_mapping.items():
            try:
                value = self._get_mapping_value(tool_output, source)
                self._set_mapping_value(mapped, destination, value)
            except SkillRuntimeError:
                raise
            except (KeyError, TypeError, ValueError) as exc:
                raise SkillRuntimeError(
                    "DIRECT_TOOL_OUTPUT_MAPPING_FAILED",
                    f"Direct tool output mapping failed for Skill: {skill.id}",
                    {
                        "skill_id": skill.id,
                        "destination": destination,
                        "source": source,
                        "output_keys": list(tool_output.keys()),
                    },
                ) from exc
        return mapped

    def _get_mapping_value(self, value: dict[str, object], path: str) -> object:
        if path in ("", "."):
            return value
        current: object = value
        for part in path.split("."):
            if not part:
                raise ValueError("mapping source path contains an empty segment")
            if not isinstance(current, dict) or part not in current:
                raise KeyError(part)
            current = current[part]
        return current

    def _set_mapping_value(
        self,
        output: dict[str, object],
        path: str,
        value: object,
    ) -> None:
        parts = path.split(".")
        if not parts or any(not part for part in parts):
            raise ValueError("mapping destination path contains an empty segment")

        current = output
        for part in parts[:-1]:
            next_value = current.get(part)
            if next_value is None:
                nested: dict[str, object] = {}
                current[part] = nested
                current = nested
                continue
            if not isinstance(next_value, dict):
                raise TypeError(f"mapping destination path conflicts at {part}")
            current = cast(dict[str, object], next_value)
        current[parts[-1]] = value

    def _assistant_tool_call_message(self, tool_call: ToolCallRequest) -> dict[str, object]:
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.tool_id,
                        "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
                    },
                }
            ],
        }

    def _validate_schema(
        self,
        schema: dict[str, object],
        value: dict[str, object],
        code: str,
    ) -> None:
        try:
            validate(instance=value, schema=schema)
        except JsonSchemaValidationError as exc:
            raise SkillRuntimeError(
                code,
                exc.message,
                self._schema_error_details(exc, value),
            ) from exc

    def _normalize_value_for_schema(self, schema: dict[str, object], value: object) -> object:
        schema_type = schema.get("type")
        if schema_type == "object" and isinstance(value, dict):
            properties = schema.get("properties")
            if not isinstance(properties, dict):
                return value
            value = self._wrap_single_property_object(schema, properties, value)
            normalized = dict(value)
            required = schema.get("required")
            required_keys = {
                key for key in required if isinstance(key, str)
            } if isinstance(required, list) else set()
            for key, property_schema in properties.items():
                if key in normalized and isinstance(property_schema, dict):
                    if normalized[key] is None and key not in required_keys:
                        del normalized[key]
                        continue
                    normalized[key] = self._normalize_value_for_schema(
                        property_schema,
                        normalized[key],
                    )
            return normalized

        if schema_type == "array" and isinstance(value, str):
            items = schema.get("items")
            if isinstance(items, dict) and self._schema_allows_string(items):
                return self._split_string_array(value)

        if schema_type == "string" and isinstance(value, (bool, int, float)):
            return str(value)

        if schema_type == "array" and isinstance(value, list):
            items = schema.get("items")
            if not isinstance(items, dict):
                return value
            return [self._normalize_value_for_schema(items, item) for item in value]

        return value

    def _schema_allows_string(self, schema: dict[str, object]) -> bool:
        if schema.get("type") == "string":
            return True
        one_of = schema.get("oneOf")
        if not isinstance(one_of, list):
            return False
        return any(isinstance(option, dict) and option.get("type") == "string" for option in one_of)

    def _wrap_single_property_object(
        self,
        schema: dict[str, object],
        properties: dict[object, object],
        value: dict[str, object],
    ) -> dict[str, object]:
        required = schema.get("required")
        if not isinstance(required, list) or len(required) != 1:
            return value
        wrapper_key = required[0]
        if not isinstance(wrapper_key, str) or wrapper_key in value:
            return value
        wrapper_schema = properties.get(wrapper_key)
        if not isinstance(wrapper_schema, dict) or wrapper_schema.get("type") != "object":
            return value
        wrapper_properties = wrapper_schema.get("properties")
        wrapper_required = wrapper_schema.get("required")
        matched_properties = (
            isinstance(wrapper_properties, dict)
            and any(isinstance(key, str) and key in value for key in wrapper_properties)
        )
        matched_required = (
            isinstance(wrapper_required, list)
            and any(isinstance(key, str) and key in value for key in wrapper_required)
        )
        if not matched_properties and not matched_required:
            return value
        return {wrapper_key: value}

    def _schema_error_details(
        self,
        exc: JsonSchemaValidationError,
        value: dict[str, object],
    ) -> dict[str, object]:
        return {
            "path": list(exc.absolute_path),
            "schema_path": list(exc.absolute_schema_path),
            "root_keys": list(value.keys()),
            "instance_preview": self._json_preview(value),
        }

    def _json_preview(self, value: object, limit: int = 1200) -> str:
        try:
            preview = json.dumps(value, ensure_ascii=False)
        except TypeError:
            preview = str(value)
        if len(preview) <= limit:
            return preview
        return f"{preview[:limit]}..."

    def _split_string_array(self, value: str) -> list[str]:
        parts = re.split(r"\s*(?:->|→|,|，|;|；|、|\n)\s*", value.strip())
        return [part for part in parts if part]

    def _save_output_artifact(
        self,
        run_id: str,
        output: dict[str, object],
        filename: str,
    ) -> None:
        self.artifact_store.save_text(
            run_id=run_id,
            content=json.dumps(output, ensure_ascii=False, indent=2),
            artifact_type="json",
            filename=filename,
            mime_type="application/json",
        )

    def _build_messages(
        self,
        skill: Skill,
        input_data: dict[str, object],
    ) -> list[dict[str, object]]:
        return [
            {"role": "system", "content": skill.prompt},
            {"role": "user", "content": json.dumps({"input": input_data}, ensure_ascii=False)},
        ]

    def _tools_to_llm_schema(self, tools: list[Tool]) -> list[dict[str, object]]:
        return [
            {
                "id": tool.id,
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in tools
        ]

    def _find_allowed_tool(self, tools: list[Tool], tool_id: str) -> Tool:
        for tool in tools:
            if tool.id == tool_id:
                return tool
        raise SkillRuntimeError("TOOL_NOT_ALLOWED", f"Tool is not allowed: {tool_id}")

    def _trace_summary(self, run_id: str) -> dict[str, object]:
        summary: dict[str, int] = {
            "llm_called": 0,
            "tool_called": 0,
            "tool_succeeded": 0,
            "tool_failed": 0,
            "workflow_step_started": 0,
            "workflow_step_succeeded": 0,
            "workflow_step_failed": 0,
            "llm_failed": 0,
            "llm_retried": 0,
        }
        for event in self.trace_store.list_events(run_id):
            if event.type in summary:
                summary[event.type] += 1
        return dict(summary)
