"""Tool domain schemas."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from bkl_engine.domain.common import JsonObject

ToolType = Literal["api", "python", "llm", "skill", "system"]


class ToolFilesystemConfig(BaseModel):
    read: list[str] = Field(default_factory=list)
    write: list[str] = Field(default_factory=list)


class ToolRuntimeConfig(BaseModel):
    timeout_seconds: int = 60
    memory_mb: int | None = None
    network: bool = False
    filesystem: ToolFilesystemConfig = Field(default_factory=ToolFilesystemConfig)


class ToolPermissions(BaseModel):
    network: bool = False
    filesystem_read: list[str] = Field(default_factory=list)
    filesystem_write: list[str] = Field(default_factory=list)
    secrets: list[str] = Field(default_factory=list)


class Tool(BaseModel):
    id: str
    name: str
    type: ToolType
    description: str
    input_schema: JsonObject
    output_schema: JsonObject
    config: JsonObject = Field(default_factory=dict)
    permissions: ToolPermissions = Field(default_factory=ToolPermissions)
    enabled: bool = True
    entry: str | None = None
    runtime: ToolRuntimeConfig = Field(default_factory=ToolRuntimeConfig)
    package_path: Path | None = None


class ToolExecutionContext(BaseModel):
    run_id: str
    tool_call_id: str
    artifact_dir: Path
    skill_id: str | None = None
    user_id: str | None = None
    workspace_id: str | None = None
    identity_id: str | None = None
    role_id: str | None = None
    project_id: str | None = None


class ToolExecutionResult(BaseModel):
    output: JsonObject
    stderr: str = ""
    artifacts: list[str] = Field(default_factory=list)
