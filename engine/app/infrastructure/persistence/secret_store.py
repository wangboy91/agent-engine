"""Secret store primitives."""

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from app.domain.errors import BklEngineError
from app.domain.secret import SecretRecord, SecretView


class SecretDocument(BaseModel):
    version: int = 1
    secrets: dict[str, SecretRecord] = Field(default_factory=dict)


class InMemorySecretStore:
    def __init__(self) -> None:
        self._secrets: dict[str, SecretRecord] = {}

    def set_secret(
        self,
        name: str,
        value: str,
        workspace_id: str | None = None,
        description: str | None = None,
    ) -> SecretView:
        secret_id = _secret_id(name, workspace_id)
        existing = self._secrets.get(secret_id)
        now = datetime.now(UTC)
        record = SecretRecord(
            secret_id=secret_id,
            name=name,
            value=value,
            workspace_id=workspace_id,
            description=description,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        self._secrets[secret_id] = record
        return record.to_view()

    def get_secret(self, name: str, workspace_id: str | None = None) -> SecretRecord:
        secret = self._secrets.get(_secret_id(name, workspace_id))
        if secret is None and workspace_id is not None:
            secret = self._secrets.get(_secret_id(name, None))
        if secret is None:
            raise BklEngineError(
                "SECRET_NOT_FOUND",
                f"Secret not found: {name}",
                {"workspace_id": workspace_id},
            )
        return secret

    def list_secrets(self, workspace_id: str | None = None) -> list[SecretView]:
        secrets = list(self._secrets.values())
        if workspace_id is not None:
            secrets = [
                secret for secret in secrets
                if secret.workspace_id == workspace_id
            ]
        return [secret.to_view() for secret in secrets]


class JsonSecretStore(InMemorySecretStore):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        super().__init__()
        self._load_into_memory()

    def set_secret(
        self,
        name: str,
        value: str,
        workspace_id: str | None = None,
        description: str | None = None,
    ) -> SecretView:
        view = super().set_secret(name, value, workspace_id, description)
        self._save()
        return view

    def _load_into_memory(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            document = SecretDocument.model_validate(raw)
        except json.JSONDecodeError as exc:
            raise BklEngineError(
                "SECRET_STORE_INVALID",
                f"Invalid secret store JSON: {self.path}",
            ) from exc
        except ValidationError as exc:
            raise BklEngineError(
                "SECRET_STORE_INVALID",
                f"Invalid secret store shape: {self.path}",
            ) from exc
        self._secrets = dict(document.secrets)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        document = SecretDocument(secrets=dict(self._secrets))
        self.path.write_text(
            json.dumps(document.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _secret_id(name: str, workspace_id: str | None = None) -> str:
    if workspace_id is None:
        return f"global:{name}"
    return f"workspace:{workspace_id}:{name}"
