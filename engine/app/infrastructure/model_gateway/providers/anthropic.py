"""Anthropic-compatible model provider primitives."""

import json
import os
import re
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.domain.errors import BklEngineError
from app.domain.model import ModelResponse, ModelUsage, ToolCallRequest
from app.infrastructure.config.engine_config import ModelProfileConfig


class AnthropicProvider:
    def __init__(
        self,
        config: ModelProfileConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self.client = client or httpx.AsyncClient(timeout=config.timeout_seconds)

    async def chat(
        self,
        profile: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        stream_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> ModelResponse:
        del profile, stream_callback
        if self.config.base_url is None:
            raise BklEngineError("CONFIG_INVALID", "Anthropic base_url is required")

        try:
            response = await self.client.post(
                f"{self.config.base_url.rstrip('/')}/v1/messages",
                headers=self._headers(),
                json={
                    "model": self.config.model,
                    "max_tokens": self.config.max_tokens,
                    "messages": self._format_messages(messages),
                    "tools": self._format_tools(tools),
                },
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise BklEngineError(
                "MODEL_PROVIDER_TIMEOUT",
                f"Anthropic model request timed out after {self.config.timeout_seconds}s",
                {
                    "provider": "anthropic",
                    "timeout_seconds": self.config.timeout_seconds,
                    "error_type": exc.__class__.__name__,
                },
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            details: dict[str, object] = {
                "provider": "anthropic",
                "error_type": exc.__class__.__name__,
            }
            if isinstance(exc, httpx.HTTPStatusError):
                details["status_code"] = exc.response.status_code
            raise BklEngineError(
                "MODEL_PROVIDER_ERROR",
                str(exc) or exc.__class__.__name__,
                details,
                retryable=True,
            ) from exc
        payload = response.json()
        if not isinstance(payload, dict):
            raise BklEngineError("MODEL_PROVIDER_ERROR", "Anthropic response is invalid")
        return self._parse_response(payload)

    def _headers(self) -> dict[str, str]:
        api_key = self._api_key()
        auth_header = self.config.auth_header or "x-api-key"
        auth_scheme = self.config.auth_scheme
        auth_value = f"{auth_scheme} {api_key}" if auth_scheme else api_key
        return {
            auth_header: auth_value,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def _api_key(self) -> str:
        if self.config.api_key_env is None:
            raise BklEngineError("CONFIG_INVALID", "api_key_env is required")
        api_key = os.environ.get(self.config.api_key_env)
        if api_key is None:
            raise BklEngineError(
                "SECRET_NOT_AVAILABLE",
                f"Missing model credential: {self.config.api_key_env}",
            )
        return api_key

    def _format_messages(self, messages: list[dict[str, object]]) -> list[dict[str, object]]:
        formatted: list[dict[str, object]] = []
        for message in messages:
            role = message.get("role")
            if role == "system":
                continue
            if role == "tool":
                formatted.append(
                    {
                        "role": "user",
                        "content": str(message.get("content", "")),
                    }
                )
                continue
            formatted.append(
                {
                    "role": "assistant" if role == "assistant" else "user",
                    "content": str(message.get("content", "")),
                }
            )
        return formatted

    def _format_tools(self, tools: list[dict[str, object]]) -> list[dict[str, object]]:
        return [
            {
                "name": tool["id"],
                "description": tool.get("description", ""),
                "input_schema": tool.get("input_schema", {"type": "object"}),
            }
            for tool in tools
        ]

    def _parse_response(self, payload: dict[str, Any]) -> ModelResponse:
        usage_payload = payload.get("usage", {})
        usage = ModelUsage()
        if isinstance(usage_payload, dict):
            usage = ModelUsage(
                input_tokens=int(usage_payload.get("input_tokens", 0)),
                output_tokens=int(usage_payload.get("output_tokens", 0)),
            )

        content = payload.get("content", [])
        tool_calls = self._parse_tool_calls(content)
        if tool_calls:
            return ModelResponse(tool_calls=tool_calls, usage=usage)

        return ModelResponse(final_output=self._parse_text_content(content), usage=usage)

    def _parse_tool_calls(self, content: object) -> list[ToolCallRequest]:
        if not isinstance(content, list):
            return []

        parsed: list[ToolCallRequest] = []
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = block.get("name")
            if not isinstance(name, str):
                continue
            raw_input = block.get("input", {})
            parsed.append(
                ToolCallRequest(
                    id=str(block.get("id", name)),
                    tool_id=name,
                    arguments=dict(raw_input) if isinstance(raw_input, dict) else {},
                )
            )
        return parsed

    def _parse_text_content(self, content: object) -> dict[str, object]:
        if not isinstance(content, list):
            return {}
        text = "".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
        text = self._extract_json_text(text)
        parsed = self._parse_json_object(text)
        if parsed is None:
            return {"text": text}
        if isinstance(parsed, dict):
            return dict(parsed)
        return {"text": text}

    def _parse_json_object(self, content: str) -> object | None:
        for candidate in (content, self._repair_json_text(content)):
            try:
                parsed: object = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            return parsed
        return None

    def _repair_json_text(self, content: str) -> str:
        repaired: list[str] = []
        in_string = False
        escaped = False
        for char in content:
            if in_string:
                if escaped:
                    repaired.append(char)
                    escaped = False
                    continue
                if char == "\\":
                    repaired.append(char)
                    escaped = True
                    continue
                if char == '"':
                    repaired.append(char)
                    in_string = False
                    continue
                if char == "\n":
                    repaired.append("\\n")
                    continue
                if char == "\r":
                    repaired.append("\\r")
                    continue
                repaired.append(char)
                continue
            repaired.append(char)
            if char == '"':
                in_string = True
        return re.sub(r",\s*([}\]])", r"\1", "".join(repaired))

    def _extract_json_text(self, content: str) -> str:
        stripped = content.strip()
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
        if match is not None:
            return match.group(1).strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end > start:
            return stripped[start : end + 1].strip()
        return stripped
