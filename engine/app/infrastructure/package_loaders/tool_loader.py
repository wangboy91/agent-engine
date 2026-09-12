"""Local Tool package loader."""

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.domain.common import JsonObject
from app.domain.errors import BklEngineError
from app.domain.tool import Tool, ToolPermissions, ToolRuntimeConfig


class ToolLoadError(BklEngineError):
    """Raised when a Tool package cannot be loaded or validated."""

    def __init__(self, message: str) -> None:
        super().__init__("TOOL_LOAD_ERROR", message)


def load_tool(path: str | Path) -> Tool:
    tool_dir = _resolve_tool_dir(Path(path))
    tool_yaml_path = tool_dir / "tool.yaml"

    raw_tool = _read_yaml_object(tool_yaml_path)
    _ensure_required_fields(
        raw_tool,
        required=("id", "type", "name", "description", "input_schema", "output_schema"),
        source=tool_yaml_path,
    )

    raw_tool["input_schema"] = _load_schema(tool_dir, raw_tool["input_schema"], "input_schema")
    raw_tool["output_schema"] = _load_schema(tool_dir, raw_tool["output_schema"], "output_schema")

    runtime = ToolRuntimeConfig.model_validate(raw_tool.get("runtime", {}))
    permissions = _build_permissions(raw_tool.get("permissions"), runtime)

    try:
        return Tool.model_validate(
            {
                **raw_tool,
                "runtime": runtime,
                "permissions": permissions,
                "package_path": tool_dir,
            }
        )
    except ValidationError as exc:
        raise ToolLoadError(f"Invalid tool definition in {tool_yaml_path}: {exc}") from exc


def _resolve_tool_dir(path: Path) -> Path:
    if path.is_dir():
        return path
    if path.name == "tool.yaml":
        return path.parent
    raise ToolLoadError(f"Tool path must be a directory or tool.yaml file: {path}")


def _read_yaml_object(path: Path) -> JsonObject:
    if not path.exists():
        raise ToolLoadError(f"Tool definition not found: {path}")

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ToolLoadError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ToolLoadError(f"Tool definition must be a YAML object: {path}")

    return dict(data)


def _ensure_required_fields(raw_tool: JsonObject, required: tuple[str, ...], source: Path) -> None:
    missing = [field for field in required if field not in raw_tool]
    if missing:
        raise ToolLoadError(f"Missing required field(s) in {source}: {', '.join(missing)}")


def _load_schema(tool_dir: Path, schema_ref: Any, field_name: str) -> JsonObject:
    if isinstance(schema_ref, dict):
        return dict(schema_ref)

    if not isinstance(schema_ref, str):
        raise ToolLoadError(f"{field_name} must be a JSON object or schema file path")

    schema_path = tool_dir / schema_ref
    if not schema_path.exists():
        raise ToolLoadError(f"{field_name} file not found: {schema_path}")

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ToolLoadError(f"Invalid JSON schema in {schema_path}: {exc}") from exc

    if not isinstance(schema, dict):
        raise ToolLoadError(f"{field_name} must resolve to a JSON object: {schema_path}")

    return dict(schema)


def _build_permissions(raw_permissions: Any, runtime: ToolRuntimeConfig) -> ToolPermissions:
    if raw_permissions is None:
        return ToolPermissions(
            network=runtime.network,
            filesystem_read=runtime.filesystem.read,
            filesystem_write=runtime.filesystem.write,
        )

    if not isinstance(raw_permissions, dict):
        raise ToolLoadError("permissions must be a YAML object")

    filesystem = raw_permissions.get("filesystem", {})
    if filesystem is None:
        filesystem = {}
    if not isinstance(filesystem, dict):
        raise ToolLoadError("permissions.filesystem must be a YAML object")

    return ToolPermissions(
        network=bool(raw_permissions.get("network", runtime.network)),
        filesystem_read=list(filesystem.get("read", runtime.filesystem.read)),
        filesystem_write=list(filesystem.get("write", runtime.filesystem.write)),
        secrets=list(raw_permissions.get("secrets", [])),
    )
