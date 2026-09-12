"""Local Skill package loader."""

import json
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.domain.common import JsonObject
from app.domain.errors import AgentEngineError
from app.domain.skill import (
    Skill,
    SkillExecutionConfig,
    SkillLimits,
    SkillModelConfig,
    SkillWorkflowConfig,
)


class SkillLoadError(AgentEngineError):
    """Raised when a Skill package cannot be loaded or validated."""

    def __init__(self, message: str) -> None:
        super().__init__("SKILL_LOAD_ERROR", message)


RUNTIME_CONFIG_FILE = "agent.skill.json"
LEGACY_RUNTIME_CONFIG_FILE = "skill.config.json"
DEFAULT_INPUT_SCHEMA: JsonObject = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "user_input": {
            "type": "string",
        }
    },
}
DEFAULT_OUTPUT_SCHEMA: JsonObject = {
    "type": "object",
    "additionalProperties": True,
}


def load_skill(path: str | Path) -> Skill:
    skill_dir = _resolve_skill_dir(Path(path))
    standard_skill_path = skill_dir / "SKILL.md"
    if not standard_skill_path.exists():
        raise SkillLoadError(f"Skill package must contain SKILL.md: {skill_dir}")
    return _load_standard_skill(skill_dir, standard_skill_path)


def _load_standard_skill(skill_dir: Path, skill_md_path: Path) -> Skill:
    frontmatter, body = _read_markdown_with_frontmatter(skill_md_path)
    _ensure_required_fields(
        frontmatter,
        required=("name", "description"),
        source=skill_md_path,
    )

    if "agent" in frontmatter:
        raise SkillLoadError(
            f"SKILL.md must not contain agent runtime config; move it to {RUNTIME_CONFIG_FILE}: "
            f"{skill_md_path}"
        )

    runtime_config_path = _runtime_config_path(skill_dir)
    runtime_config = (
        _load_runtime_config(runtime_config_path)
        if runtime_config_path is not None
        else _default_runtime_config(frontmatter["name"])
    )

    raw_skill: JsonObject = {
        "id": runtime_config.get("id", frontmatter["name"]),
        "name": frontmatter["name"],
        "version": runtime_config.get("version", "0.1.0"),
        "description": frontmatter["description"],
        "input_schema": runtime_config.get("input_schema"),
        "output_schema": runtime_config.get("output_schema"),
        "prompt": body.strip(),
        "model": runtime_config.get("model", {}),
        "limits": runtime_config.get("limits", {}),
        "tools": runtime_config.get("tools", {}),
        "workflow": runtime_config.get("workflow"),
        "execution": runtime_config.get("execution", {}),
    }
    _ensure_required_fields(
        raw_skill,
        required=("id", "name", "version", "description", "input_schema", "output_schema"),
        source=runtime_config_path or skill_md_path,
    )

    raw_skill["input_schema"] = _load_schema(skill_dir, raw_skill["input_schema"], "input_schema")
    raw_skill["output_schema"] = _load_schema(
        skill_dir,
        raw_skill["output_schema"],
        "output_schema",
    )
    return _build_skill(raw_skill, skill_dir, runtime_config_path or skill_md_path)


def _build_skill(raw_skill: JsonObject, skill_dir: Path, source: Path) -> Skill:
    allowed_tools = _load_allowed_tools(raw_skill)

    try:
        workflow = (
            SkillWorkflowConfig.model_validate(raw_skill["workflow"])
            if raw_skill.get("workflow") is not None
            else None
        )
        return Skill.model_validate(
            {
                **raw_skill,
                "allowed_tools": allowed_tools,
                "model": SkillModelConfig.model_validate(raw_skill.get("model", {})),
                "limits": SkillLimits.model_validate(raw_skill.get("limits", {})),
                "workflow": workflow,
                "execution": SkillExecutionConfig.model_validate(raw_skill.get("execution", {})),
                "package_path": skill_dir,
            }
        )
    except ValidationError as exc:
        raise SkillLoadError(f"Invalid skill definition in {source}: {exc}") from exc


def _resolve_skill_dir(path: Path) -> Path:
    if path.is_dir():
        return path
    if path.name == "SKILL.md":
        return path.parent
    raise SkillLoadError(f"Skill path must be a directory or SKILL.md file: {path}")


def _read_markdown_with_frontmatter(path: Path) -> tuple[JsonObject, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n?(.*)\Z", text, re.DOTALL)
    if match is None:
        raise SkillLoadError(f"SKILL.md must start with YAML frontmatter: {path}")

    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise SkillLoadError(f"Invalid YAML frontmatter in {path}: {exc}") from exc

    if not isinstance(frontmatter, dict):
        raise SkillLoadError(f"SKILL.md frontmatter must be a YAML object: {path}")

    body = match.group(2)
    if not body.strip():
        raise SkillLoadError(f"SKILL.md body must contain Markdown instructions: {path}")

    return dict(frontmatter), body


def _runtime_config_path(skill_dir: Path) -> Path | None:
    runtime_config_path = skill_dir / RUNTIME_CONFIG_FILE
    if runtime_config_path.exists():
        return runtime_config_path
    legacy_runtime_config_path = skill_dir / LEGACY_RUNTIME_CONFIG_FILE
    if legacy_runtime_config_path.exists():
        return legacy_runtime_config_path
    return None


def _default_runtime_config(skill_name: object) -> JsonObject:
    return {
        "id": str(skill_name),
        "version": "0.1.0",
        "input_schema": DEFAULT_INPUT_SCHEMA,
        "output_schema": DEFAULT_OUTPUT_SCHEMA,
        "model": {"profile": "mock"},
        "tools": {"allow": []},
    }


def _load_runtime_config(path: Path) -> JsonObject:
    if not path.exists():
        raise SkillLoadError(f"Skill package must contain {RUNTIME_CONFIG_FILE}: {path.parent}")
    try:
        runtime_config = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SkillLoadError(f"Invalid JSON runtime config in {path}: {exc}") from exc
    if not isinstance(runtime_config, dict):
        raise SkillLoadError(f"{RUNTIME_CONFIG_FILE} must be a JSON object: {path}")
    return dict(runtime_config)


def _ensure_required_fields(raw_skill: JsonObject, required: tuple[str, ...], source: Path) -> None:
    missing = [field for field in required if field not in raw_skill]
    if missing:
        raise SkillLoadError(f"Missing required field(s) in {source}: {', '.join(missing)}")


def _load_schema(skill_dir: Path, schema_ref: Any, field_name: str) -> JsonObject:
    if isinstance(schema_ref, dict):
        return dict(schema_ref)
    if not isinstance(schema_ref, str):
        raise SkillLoadError(f"{field_name} must be a JSON object or schema file path")
    schema_path = skill_dir / schema_ref
    if not schema_path.exists():
        raise SkillLoadError(f"{field_name} file not found: {schema_path}")
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SkillLoadError(f"Invalid JSON schema in {schema_path}: {exc}") from exc
    if not isinstance(schema, dict):
        raise SkillLoadError(f"{field_name} must resolve to a JSON object: {schema_path}")
    return dict(schema)


def _load_allowed_tools(raw_skill: JsonObject) -> list[str]:
    tools = raw_skill.get("tools", {})
    if not isinstance(tools, dict):
        raise SkillLoadError("tools must be an object")
    allowed = tools.get("allow", [])
    if not isinstance(allowed, list) or not all(isinstance(tool_id, str) for tool_id in allowed):
        raise SkillLoadError("tools.allow must be a list of tool ids")
    return allowed
