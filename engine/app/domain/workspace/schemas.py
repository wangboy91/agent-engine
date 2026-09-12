"""Workspace and identity domain schemas."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class Workspace(BaseModel):
    workspace_id: str
    name: str
    description: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkspaceSkill(BaseModel):
    workspace_id: str
    skill_id: str
    display_name: str | None = None
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Identity(BaseModel):
    identity_id: str
    workspace_id: str
    name: str
    description: str | None = None
    skill_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
