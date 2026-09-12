"""Memory domain schemas."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

MemoryTarget = Literal["memory", "user"]


class MemorySource(BaseModel):
    target: MemoryTarget
    path: Path
    char_count: int = Field(ge=0)


class MemorySnapshot(BaseModel):
    workspace_id: str
    identity_id: str
    memory: str = ""
    user: str = ""
    sources: list[MemorySource] = Field(default_factory=list)

    @property
    def has_content(self) -> bool:
        return bool(self.memory.strip() or self.user.strip())
