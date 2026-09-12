"""Prompt context assembly for Skill execution."""

import json
from dataclasses import dataclass

from app.application.ports import MemoryStorePort
from app.domain.execution import RunContext
from app.domain.memory import MemorySnapshot
from app.domain.skill import Skill


@dataclass(frozen=True)
class PromptContextAssembly:
    messages: list[dict[str, object]]
    memory_snapshot: MemorySnapshot | None = None


class PromptContextAssembler:
    def __init__(self, memory_store: MemoryStorePort | None = None) -> None:
        self.memory_store = memory_store

    def build_messages(
        self,
        skill: Skill,
        input_data: dict[str, object],
        context: RunContext | None,
    ) -> PromptContextAssembly:
        snapshot = self._load_memory_snapshot(context)
        system_prompt = self._system_prompt(skill.prompt, snapshot)
        return PromptContextAssembly(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps({"input": input_data}, ensure_ascii=False)},
            ],
            memory_snapshot=snapshot,
        )

    def _load_memory_snapshot(self, context: RunContext | None) -> MemorySnapshot | None:
        if self.memory_store is None:
            return None
        return self.memory_store.load_snapshot(
            workspace_id=context.workspace_id if context is not None else None,
            identity_id=context.identity_id if context is not None else None,
        )

    def _system_prompt(self, base_prompt: str, snapshot: MemorySnapshot | None) -> str:
        if snapshot is None or not snapshot.has_content:
            return base_prompt

        sections = [base_prompt.rstrip()]
        if snapshot.memory.strip():
            sections.append(
                "\n".join(
                    [
                        "# Workspace Memory",
                        "The following is a frozen local memory snapshot for this run.",
                        snapshot.memory.strip(),
                    ]
                )
            )
        if snapshot.user.strip():
            sections.append(
                "\n".join(
                    [
                        "# User Profile",
                        "The following is a frozen local user profile snapshot for this run.",
                        snapshot.user.strip(),
                    ]
                )
            )
        return "\n\n".join(sections)
