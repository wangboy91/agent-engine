"""OpenAPI Tool importer."""

import re
from pathlib import Path
from typing import Any

import yaml

from app.domain.tool import Tool

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def import_openapi_tools(
    spec: dict[str, Any] | str | Path,
    base_url: str | None = None,
    auth: dict[str, object] | None = None,
) -> list[Tool]:
    document = _load_spec(spec)
    paths = document.get("paths", {})
    if not isinstance(paths, dict):
        return []

    tools: list[Tool] = []
    for path, path_item in paths.items():
        if not isinstance(path, str) or not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            tool_id = str(operation.get("operationId") or _stable_operation_id(method, path))
            input_schema = _extract_input_schema(operation)
            output_schema = _extract_output_schema(operation)
            tools.append(
                Tool(
                    id=tool_id,
                    type="api",
                    name=str(operation.get("summary") or tool_id),
                    description=str(
                        operation.get("summary")
                        or operation.get("description")
                        or tool_id
                    ),
                    input_schema=input_schema,
                    output_schema=output_schema,
                    config={
                        "method": method.upper(),
                        "url": path,
                        "base_url": base_url or "",
                        "auth": auth or {},
                    },
                )
            )
    return tools


def _load_spec(spec: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(spec, dict):
        return spec

    path = Path(spec)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"OpenAPI document must be an object: {path}")
    return data


def _extract_input_schema(operation: dict[str, Any]) -> dict[str, Any]:
    request_body = operation.get("requestBody", {})
    if isinstance(request_body, dict):
        content = request_body.get("content", {})
        if isinstance(content, dict):
            json_content = content.get("application/json", {})
            if isinstance(json_content, dict) and isinstance(json_content.get("schema"), dict):
                return dict(json_content["schema"])
    return {"type": "object", "additionalProperties": True}


def _extract_output_schema(operation: dict[str, Any]) -> dict[str, Any]:
    responses = operation.get("responses", {})
    if not isinstance(responses, dict):
        return {"type": "object", "additionalProperties": True}
    for status_code, response in responses.items():
        if not str(status_code).startswith("2") or not isinstance(response, dict):
            continue
        content = response.get("content", {})
        if isinstance(content, dict):
            json_content = content.get("application/json", {})
            if isinstance(json_content, dict) and isinstance(json_content.get("schema"), dict):
                return dict(json_content["schema"])
    return {"type": "object", "additionalProperties": True}


def _stable_operation_id(method: str, path: str) -> str:
    cleaned = path.strip("/")
    cleaned = re.sub(r"[{}]", "", cleaned)
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", cleaned).strip("_")
    return f"{method.lower()}_{cleaned}" if cleaned else method.lower()
