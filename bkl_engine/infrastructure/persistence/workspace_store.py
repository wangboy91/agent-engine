"""Workspace and identity catalog store primitives."""

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from bkl_engine.domain.errors import BklEngineError
from bkl_engine.domain.workspace import Identity, Workspace, WorkspaceSkill


class WorkspaceDocument(BaseModel):
    version: int = 1
    workspaces: dict[str, Workspace] = Field(default_factory=dict)
    workspace_skills: dict[str, WorkspaceSkill] = Field(default_factory=dict)
    identities: dict[str, Identity] = Field(default_factory=dict)


class InMemoryWorkspaceStore:
    def __init__(self) -> None:
        self._workspaces: dict[str, Workspace] = {}
        self._workspace_skills: dict[tuple[str, str], WorkspaceSkill] = {}
        self._identities: dict[tuple[str, str], Identity] = {}

    def create_workspace(
        self,
        workspace_id: str,
        name: str,
        description: str | None = None,
    ) -> Workspace:
        if workspace_id in self._workspaces:
            raise BklEngineError(
                "WORKSPACE_ALREADY_EXISTS",
                f"Workspace already exists: {workspace_id}",
            )
        workspace = Workspace(
            workspace_id=workspace_id,
            name=name,
            description=description,
        )
        self._workspaces[workspace_id] = workspace
        return workspace

    def get_workspace(self, workspace_id: str) -> Workspace:
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise BklEngineError("WORKSPACE_NOT_FOUND", f"Workspace not found: {workspace_id}")
        return workspace

    def list_workspaces(self) -> list[Workspace]:
        return list(self._workspaces.values())

    def install_skill(
        self,
        workspace_id: str,
        skill_id: str,
        display_name: str | None = None,
        enabled: bool = True,
    ) -> WorkspaceSkill:
        self.get_workspace(workspace_id)
        key = (workspace_id, skill_id)
        existing = self._workspace_skills.get(key)
        now = datetime.now(UTC)
        workspace_skill = WorkspaceSkill(
            workspace_id=workspace_id,
            skill_id=skill_id,
            display_name=display_name,
            enabled=enabled,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        self._workspace_skills[key] = workspace_skill
        return workspace_skill

    def set_skill_enabled(
        self,
        workspace_id: str,
        skill_id: str,
        enabled: bool,
    ) -> WorkspaceSkill:
        workspace_skill = self.get_workspace_skill(workspace_id, skill_id)
        updated = workspace_skill.model_copy(
            update={"enabled": enabled, "updated_at": datetime.now(UTC)}
        )
        self._workspace_skills[(workspace_id, skill_id)] = updated
        return updated

    def get_workspace_skill(self, workspace_id: str, skill_id: str) -> WorkspaceSkill:
        self.get_workspace(workspace_id)
        workspace_skill = self._workspace_skills.get((workspace_id, skill_id))
        if workspace_skill is None:
            raise BklEngineError(
                "WORKSPACE_SKILL_NOT_INSTALLED",
                f"Skill is not installed in workspace: {skill_id}",
                {"workspace_id": workspace_id, "skill_id": skill_id},
            )
        return workspace_skill

    def list_workspace_skills(
        self,
        workspace_id: str,
        enabled_only: bool = False,
    ) -> list[WorkspaceSkill]:
        self.get_workspace(workspace_id)
        skills = [
            workspace_skill
            for workspace_skill in self._workspace_skills.values()
            if workspace_skill.workspace_id == workspace_id
        ]
        if enabled_only:
            skills = [workspace_skill for workspace_skill in skills if workspace_skill.enabled]
        return skills

    def list_workspace_skill_ids(
        self,
        workspace_id: str,
        enabled_only: bool = True,
    ) -> list[str]:
        return [
            workspace_skill.skill_id
            for workspace_skill in self.list_workspace_skills(
                workspace_id,
                enabled_only=enabled_only,
            )
        ]

    def create_identity(
        self,
        workspace_id: str,
        identity_id: str,
        name: str,
        description: str | None = None,
    ) -> Identity:
        self.get_workspace(workspace_id)
        key = (workspace_id, identity_id)
        if key in self._identities:
            raise BklEngineError(
                "IDENTITY_ALREADY_EXISTS",
                f"Identity already exists: {identity_id}",
                {"workspace_id": workspace_id, "identity_id": identity_id},
            )
        identity = Identity(
            identity_id=identity_id,
            workspace_id=workspace_id,
            name=name,
            description=description,
        )
        self._identities[key] = identity
        return identity

    def get_identity(self, workspace_id: str, identity_id: str) -> Identity:
        identity = self._identities.get((workspace_id, identity_id))
        if identity is None:
            raise BklEngineError(
                "IDENTITY_NOT_FOUND",
                f"Identity not found: {identity_id}",
                {"workspace_id": workspace_id, "identity_id": identity_id},
            )
        return identity

    def list_identities(self, workspace_id: str) -> list[Identity]:
        self.get_workspace(workspace_id)
        return [
            identity
            for identity in self._identities.values()
            if identity.workspace_id == workspace_id
        ]

    def bind_skill(self, workspace_id: str, identity_id: str, skill_id: str) -> Identity:
        identity = self.get_identity(workspace_id, identity_id)
        self.get_workspace_skill(workspace_id, skill_id)
        if skill_id in identity.skill_ids:
            return identity
        updated = identity.model_copy(
            update={
                "skill_ids": [*identity.skill_ids, skill_id],
                "updated_at": datetime.now(UTC),
            }
        )
        self._identities[(workspace_id, identity_id)] = updated
        return updated

    def list_identity_skill_ids(self, workspace_id: str, identity_id: str) -> list[str]:
        enabled_skill_ids = set(self.list_workspace_skill_ids(workspace_id, enabled_only=True))
        return [
            skill_id
            for skill_id in self.get_identity(workspace_id, identity_id).skill_ids
            if skill_id in enabled_skill_ids
        ]

    def is_skill_allowed(self, workspace_id: str, identity_id: str, skill_id: str) -> bool:
        return skill_id in self.list_identity_skill_ids(workspace_id, identity_id)


class JsonWorkspaceStore(InMemoryWorkspaceStore):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        super().__init__()
        self._load_into_memory()

    def create_workspace(
        self,
        workspace_id: str,
        name: str,
        description: str | None = None,
    ) -> Workspace:
        workspace = super().create_workspace(workspace_id, name, description)
        self._save()
        return workspace

    def create_identity(
        self,
        workspace_id: str,
        identity_id: str,
        name: str,
        description: str | None = None,
    ) -> Identity:
        identity = super().create_identity(workspace_id, identity_id, name, description)
        self._save()
        return identity

    def install_skill(
        self,
        workspace_id: str,
        skill_id: str,
        display_name: str | None = None,
        enabled: bool = True,
    ) -> WorkspaceSkill:
        workspace_skill = super().install_skill(workspace_id, skill_id, display_name, enabled)
        self._save()
        return workspace_skill

    def set_skill_enabled(
        self,
        workspace_id: str,
        skill_id: str,
        enabled: bool,
    ) -> WorkspaceSkill:
        workspace_skill = super().set_skill_enabled(workspace_id, skill_id, enabled)
        self._save()
        return workspace_skill

    def bind_skill(self, workspace_id: str, identity_id: str, skill_id: str) -> Identity:
        identity = super().bind_skill(workspace_id, identity_id, skill_id)
        self._save()
        return identity

    def _load_into_memory(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            document = WorkspaceDocument.model_validate(raw)
        except json.JSONDecodeError as exc:
            raise BklEngineError(
                "WORKSPACE_STORE_INVALID",
                f"Invalid workspace store JSON: {self.path}",
            ) from exc
        except ValidationError as exc:
            raise BklEngineError(
                "WORKSPACE_STORE_INVALID",
                f"Invalid workspace store shape: {self.path}",
            ) from exc

        self._workspaces = dict(document.workspaces)
        self._workspace_skills = {
            (workspace_skill.workspace_id, workspace_skill.skill_id): workspace_skill
            for workspace_skill in document.workspace_skills.values()
        }
        self._identities = {
            (identity.workspace_id, identity.identity_id): identity
            for identity in document.identities.values()
        }

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        document = WorkspaceDocument(
            workspaces=dict(self._workspaces),
            workspace_skills={
                _workspace_skill_key(workspace_id, skill_id): workspace_skill
                for (workspace_id, skill_id), workspace_skill in self._workspace_skills.items()
            },
            identities={
                _identity_key(workspace_id, identity_id): identity
                for (workspace_id, identity_id), identity in self._identities.items()
            },
        )
        self.path.write_text(
            json.dumps(document.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _identity_key(workspace_id: str, identity_id: str) -> str:
    return f"{workspace_id}/{identity_id}"


def _workspace_skill_key(workspace_id: str, skill_id: str) -> str:
    return f"{workspace_id}/{skill_id}"
