"""Secret domain schemas."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class SecretRecord(BaseModel):
    secret_id: str
    name: str
    value: str
    workspace_id: str | None = None
    description: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_view(self) -> "SecretView":
        return SecretView(
            secret_id=self.secret_id,
            name=self.name,
            workspace_id=self.workspace_id,
            description=self.description,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class SecretView(BaseModel):
    secret_id: str
    name: str
    workspace_id: str | None = None
    description: str | None = None
    created_at: datetime
    updated_at: datetime
