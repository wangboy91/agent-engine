"""Scene to Skill mapping domain primitives."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class SceneDefinition(BaseModel):
    scene_id: str
    skill_id: str
    title: str = ""
    description: str = ""
    defaults: dict[str, Any] = Field(default_factory=dict)


class SceneMapping:
    def __init__(
        self,
        scenes: Mapping[str, SceneDefinition | Mapping[str, Any]] | None = None,
    ) -> None:
        self._scenes: dict[str, SceneDefinition] = {}
        for scene_id, value in (scenes or {}).items():
            if isinstance(value, SceneDefinition):
                scene = value
            else:
                payload = dict(value)
                payload.setdefault("scene_id", scene_id)
                scene = SceneDefinition.model_validate(payload)
            self._scenes[scene.scene_id] = scene

    @classmethod
    def from_file(cls, path: str | Path) -> "SceneMapping":
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            return cls()
        raw_scenes = payload.get("scenes", payload)
        if not isinstance(raw_scenes, dict):
            return cls()
        return cls(raw_scenes)

    def get(self, scene_id: str) -> SceneDefinition | None:
        return self._scenes.get(scene_id)

    def list_scenes(self) -> list[SceneDefinition]:
        return list(self._scenes.values())
