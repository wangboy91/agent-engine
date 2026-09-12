"""API tool primitives."""

import os
from typing import Any

import httpx
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate

from app.domain.errors import AgentEngineError
from app.domain.tool import Tool, ToolExecutionContext, ToolExecutionResult


class ApiToolExecutionError(AgentEngineError):
    """Raised when an API Tool cannot be executed."""


class ApiToolRunner:
    async def execute(
        self,
        tool: Tool,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        del context
        try:
            validate(instance=arguments, schema=tool.input_schema)
        except JsonSchemaValidationError as exc:
            raise ApiToolExecutionError(
                "TOOL_INPUT_SCHEMA_INVALID",
                f"Invalid input for tool {tool.id}: {exc.message}",
            ) from exc

        method = str(tool.config.get("method", "GET")).upper()
        base_url = str(tool.config.get("base_url", "")).rstrip("/")
        url = str(tool.config.get("url", ""))
        timeout = float(tool.config.get("timeout_seconds", tool.runtime.timeout_seconds))
        headers = self._build_auth_headers(tool.config.get("auth"))

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method,
                f"{base_url}{url}",
                json=arguments if method in {"POST", "PUT", "PATCH"} else None,
                params=self._to_query_params(arguments) if method == "GET" else None,
                headers=headers,
            )
            response.raise_for_status()
            output: Any = response.json()

        if not isinstance(output, dict):
            raise ApiToolExecutionError(
                "TOOL_OUTPUT_SCHEMA_INVALID",
                "API output must be an object",
            )

        try:
            validate(instance=output, schema=tool.output_schema)
        except JsonSchemaValidationError as exc:
            raise ApiToolExecutionError(
                "TOOL_OUTPUT_SCHEMA_INVALID",
                f"Invalid output from tool {tool.id}: {exc.message}",
            ) from exc

        return ToolExecutionResult(output=output)

    def _to_query_params(self, arguments: dict[str, object]) -> dict[str, str]:
        return {key: str(value) for key, value in arguments.items()}

    def _build_auth_headers(self, auth: object) -> dict[str, str]:
        if not isinstance(auth, dict):
            return {}
        if auth.get("type") != "api_key":
            return {}

        header = str(auth.get("header", "Authorization"))
        env_name = auth.get("value_env") or auth.get("api_key_env")
        if not isinstance(env_name, str):
            return {}

        value = os.environ.get(env_name)
        if value is None:
            raise ApiToolExecutionError(
                "SECRET_NOT_AVAILABLE",
                f"Required API credential is not available: {env_name}",
            )
        return {header: value}
