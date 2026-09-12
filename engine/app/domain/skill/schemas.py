"""Skill domain schemas."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.domain.common import JsonObject


class SkillLimits(BaseModel):
    max_iterations: int = 8
    max_tool_calls: int = 12
    max_model_retries: int = 2
    max_tokens: int = 12_000
    timeout_seconds: int = 600
    max_credits: int = 100


class SkillModelConfig(BaseModel):
    profile: str = "mock"
    fallback_profile: str | None = None


class SkillWorkflowStep(BaseModel):
    id: str
    skill_id: str
    description: str | None = None
    depends_on: list[str] = Field(default_factory=list)


class SkillWorkflowConfig(BaseModel):
    steps: list[SkillWorkflowStep] = Field(min_length=1)
    output_artifact: str | None = "workflow_output.json"
    max_parallel_steps: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_step_graph(self) -> "SkillWorkflowConfig":
        step_ids = [step.id for step in self.steps]
        duplicate_ids = sorted({step_id for step_id in step_ids if step_ids.count(step_id) > 1})
        if duplicate_ids:
            raise ValueError(f"workflow step ids must be unique: {', '.join(duplicate_ids)}")

        known_ids = set(step_ids)
        for step in self.steps:
            unknown_deps = [dep for dep in step.depends_on if dep not in known_ids]
            if unknown_deps:
                raise ValueError(
                    f"workflow step {step.id} depends on unknown step(s): "
                    f"{', '.join(unknown_deps)}"
                )
            if step.id in step.depends_on:
                raise ValueError(f"workflow step {step.id} cannot depend on itself")
        return self


class SkillExecutionConfig(BaseModel):
    type: Literal["llm_loop", "direct_tool"] = "llm_loop"
    tool_id: str | None = None
    output_mapping: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_direct_tool_config(self) -> "SkillExecutionConfig":
        if self.type == "direct_tool" and not self.tool_id:
            raise ValueError("execution.tool_id is required when execution.type is direct_tool")
        return self


class Skill(BaseModel):
    id: str
    name: str
    version: str
    description: str
    input_schema: JsonObject
    output_schema: JsonObject
    prompt: str
    allowed_tools: list[str]
    model: SkillModelConfig = Field(default_factory=SkillModelConfig)
    limits: SkillLimits = Field(default_factory=SkillLimits)
    workflow: SkillWorkflowConfig | None = None
    execution: SkillExecutionConfig = Field(default_factory=SkillExecutionConfig)
    enabled: bool = True
    package_path: Path | None = None
