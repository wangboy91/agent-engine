import re
from pathlib import Path

from bkl_engine.domain.errors import BklEngineError
from bkl_engine.domain.memory import MemorySnapshot, MemorySource, MemoryTarget

DEFAULT_WORKSPACE_ID = "default_workspace"
DEFAULT_IDENTITY_ID = "default_operator"
MEMORY_FILENAME = "MEMORY.md"
USER_FILENAME = "USER.md"
_VALID_SCOPE_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")


class LocalMarkdownMemoryStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def load_snapshot(
        self,
        workspace_id: str | None = None,
        identity_id: str | None = None,
    ) -> MemorySnapshot:
        resolved_workspace_id = self._scope_segment(
            workspace_id or DEFAULT_WORKSPACE_ID,
            "workspace_id",
        )
        resolved_identity_id = self._scope_segment(
            identity_id or DEFAULT_IDENTITY_ID,
            "identity_id",
        )
        memory_path = self._target_path(resolved_workspace_id, resolved_identity_id, "memory")
        user_path = self._target_path(resolved_workspace_id, resolved_identity_id, "user")
        memory = self._read_text(memory_path)
        user = self._read_text(user_path)
        sources: list[MemorySource] = []
        if memory.strip():
            sources.append(
                MemorySource(target="memory", path=memory_path, char_count=len(memory))
            )
        if user.strip():
            sources.append(MemorySource(target="user", path=user_path, char_count=len(user)))
        return MemorySnapshot(
            workspace_id=resolved_workspace_id,
            identity_id=resolved_identity_id,
            memory=memory,
            user=user,
            sources=sources,
        )

    def append_entry(
        self,
        workspace_id: str | None,
        identity_id: str | None,
        target: MemoryTarget,
        content: str,
    ) -> MemorySnapshot:
        if target not in {"memory", "user"}:
            raise BklEngineError("MEMORY_TARGET_INVALID", f"Invalid memory target: {target}")
        resolved_workspace_id = self._scope_segment(
            workspace_id or DEFAULT_WORKSPACE_ID,
            "workspace_id",
        )
        resolved_identity_id = self._scope_segment(
            identity_id or DEFAULT_IDENTITY_ID,
            "identity_id",
        )
        normalized = content.strip()
        if normalized:
            path = self._target_path(resolved_workspace_id, resolved_identity_id, target)
            path.parent.mkdir(parents=True, exist_ok=True)
            existing = self._read_text(path)
            separator = "" if not existing or existing.endswith("\n") else "\n"
            entry_body = normalized.replace("\n", "\n  ")
            entry = f"- {entry_body}\n"
            path.write_text(f"{existing}{separator}{entry}", encoding="utf-8")
        return self.load_snapshot(resolved_workspace_id, resolved_identity_id)

    def _target_path(
        self,
        workspace_id: str,
        identity_id: str,
        target: MemoryTarget,
    ) -> Path:
        filename = MEMORY_FILENAME if target == "memory" else USER_FILENAME
        return self.root / workspace_id / identity_id / filename

    def _read_text(self, path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _scope_segment(self, value: str, field_name: str) -> str:
        if not _VALID_SCOPE_SEGMENT.fullmatch(value):
            raise BklEngineError(
                "MEMORY_SCOPE_INVALID",
                f"Invalid memory {field_name}: {value}",
            )
        return value
