"""Model-call domain schemas."""

from pydantic import BaseModel, Field


class ToolCallRequest(BaseModel):
    id: str
    tool_id: str
    arguments: dict[str, object] = Field(default_factory=dict)


class ModelUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0


class ModelResponse(BaseModel):
    final_output: dict[str, object] | None = None
    tool_calls: list[ToolCallRequest] = Field(default_factory=list)
    usage: ModelUsage = Field(default_factory=ModelUsage)
