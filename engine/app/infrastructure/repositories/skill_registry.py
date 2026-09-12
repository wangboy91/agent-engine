"""In-memory Skill registry adapter."""

from pathlib import Path

from app.domain.errors import BklEngineError
from app.domain.skill import Skill
from app.infrastructure.package_loaders.skill_loader import load_skill


class InMemorySkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> Skill:
        self._skills[skill.id] = skill
        return skill

    def register_skill(self, path: str | Path) -> Skill:
        return self.register(load_skill(path))

    def get_skill(self, skill_id: str) -> Skill:
        skill = self._skills.get(skill_id)
        if skill is None:
            raise BklEngineError("SKILL_NOT_FOUND", f"Skill not found: {skill_id}")
        if not skill.enabled:
            raise BklEngineError("SKILL_DISABLED", f"Skill is disabled: {skill_id}")
        return skill

    def list_skills(self) -> list[Skill]:
        return list(self._skills.values())

    def enable_skill(self, skill_id: str) -> Skill:
        skill = self.get_skill(skill_id)
        enabled = skill.model_copy(update={"enabled": True})
        self._skills[skill_id] = enabled
        return enabled

    def disable_skill(self, skill_id: str) -> Skill:
        skill = self.get_skill(skill_id)
        disabled = skill.model_copy(update={"enabled": False})
        self._skills[skill_id] = disabled
        return disabled
