"""OpenAI-compatible model provider primitives."""

import json
import os
import re
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.domain.errors import BklEngineError
from app.domain.model import ModelResponse, ModelUsage, ToolCallRequest
from app.infrastructure.config.engine_config import ModelProfileConfig


class OpenAICompatibleProvider:
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
        del profile
        if self.config.base_url is None:
            raise BklEngineError("CONFIG_INVALID", "OpenAI-compatible base_url is required")

        if stream_callback is not None and not tools:
            return await self._chat_streaming(messages, stream_callback)

        try:
            response = await self.client.post(
                f"{self.config.base_url.rstrip('/')}/chat/completions",
                headers=self._headers(),
                json=self._request_payload(messages, tools, stream=False),
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise BklEngineError(
                "MODEL_PROVIDER_TIMEOUT",
                f"OpenAI-compatible model request timed out after {self.config.timeout_seconds}s",
                {
                    "provider": "openai-compatible",
                    "timeout_seconds": self.config.timeout_seconds,
                    "error_type": exc.__class__.__name__,
                },
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            details: dict[str, object] = {
                "provider": "openai-compatible",
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
            raise BklEngineError("MODEL_PROVIDER_ERROR", "OpenAI-compatible response is invalid")
        return self._parse_response(payload)

    async def _chat_streaming(
        self,
        messages: list[dict[str, object]],
        stream_callback: Callable[[str], Awaitable[None]],
    ) -> ModelResponse:
        if self.config.base_url is None:
            raise BklEngineError("CONFIG_INVALID", "OpenAI-compatible base_url is required")
        content_parts: list[str] = []
        try:
            async with self.client.stream(
                "POST",
                f"{self.config.base_url.rstrip('/')}/chat/completions",
                headers=self._headers(),
                json=self._request_payload(messages, [], stream=True),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    delta = self._parse_stream_line(line)
                    if delta is None:
                        continue
                    content_parts.append(delta)
                    await stream_callback(delta)
        except httpx.TimeoutException as exc:
            raise BklEngineError(
                "MODEL_PROVIDER_TIMEOUT",
                f"OpenAI-compatible model request timed out after {self.config.timeout_seconds}s",
                {
                    "provider": "openai-compatible",
                    "timeout_seconds": self.config.timeout_seconds,
                    "error_type": exc.__class__.__name__,
                },
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            details: dict[str, object] = {
                "provider": "openai-compatible",
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
        return ModelResponse(final_output=self._parse_content("".join(content_parts)))

    def _request_payload(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        stream: bool,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": messages,
        }
        formatted_tools = self._format_tools(tools)
        if formatted_tools:
            payload["tools"] = formatted_tools
        if stream:
            payload["stream"] = True
        return payload

    def _parse_stream_line(self, line: str) -> str | None:
        if not line.startswith("data:"):
            return None
        data = line.removeprefix("data:").strip()
        if not data or data == "[DONE]":
            return None
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        choices = payload.get("choices", [])
        if not isinstance(choices, list) or not choices:
            return None
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return None
        delta = first_choice.get("delta", {})
        if not isinstance(delta, dict):
            return None
        content = delta.get("content")
        return content if isinstance(content, str) else None

    def _headers(self) -> dict[str, str]:
        api_key = self._api_key()
        auth_header = self.config.auth_header or "Authorization"
        auth_scheme = self.config.auth_scheme or "Bearer"
        auth_value = f"{auth_scheme} {api_key}" if auth_scheme else api_key
        return {
            auth_header: auth_value,
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

    def _format_tools(self, tools: list[dict[str, object]]) -> list[dict[str, object]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["id"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {"type": "object"}),
                },
            }
            for tool in tools
        ]

    def _parse_response(self, payload: dict[str, Any]) -> ModelResponse:
        choices = payload.get("choices", [])
        if not isinstance(choices, list) or not choices:
            raise BklEngineError(
                "MODEL_PROVIDER_ERROR",
                "OpenAI-compatible response has no choices",
            )

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise BklEngineError("MODEL_PROVIDER_ERROR", "OpenAI-compatible choice is invalid")
        message = first_choice.get("message", {})
        if not isinstance(message, dict):
            raise BklEngineError("MODEL_PROVIDER_ERROR", "OpenAI-compatible message is invalid")

        usage_payload = payload.get("usage", {})
        usage = ModelUsage()
        if isinstance(usage_payload, dict):
            usage = ModelUsage(
                input_tokens=int(usage_payload.get("prompt_tokens", 0)),
                output_tokens=int(usage_payload.get("completion_tokens", 0)),
            )

        tool_calls = self._parse_tool_calls(message.get("tool_calls", []))
        if tool_calls:
            return ModelResponse(tool_calls=tool_calls, usage=usage)

        return ModelResponse(
            final_output=self._parse_content(message.get("content")),
            usage=usage,
        )

    def _parse_tool_calls(self, raw_tool_calls: object) -> list[ToolCallRequest]:
        if not isinstance(raw_tool_calls, list):
            return []

        parsed: list[ToolCallRequest] = []
        for raw_call in raw_tool_calls:
            if not isinstance(raw_call, dict):
                continue
            function = raw_call.get("function", {})
            if not isinstance(function, dict):
                continue
            name = function.get("name")
            if not isinstance(name, str):
                continue
            parsed.append(
                ToolCallRequest(
                    id=str(raw_call.get("id", name)),
                    tool_id=name,
                    arguments=self._parse_arguments(function.get("arguments")),
                )
            )
        return parsed

    def _parse_arguments(self, arguments: object) -> dict[str, object]:
        if isinstance(arguments, dict):
            return dict(arguments)
        if isinstance(arguments, str):
            try:
                parsed = json.loads(arguments)
            except json.JSONDecodeError:
                return {}
            if isinstance(parsed, dict):
                return dict(parsed)
        return {}

    def _parse_content(self, content: object) -> dict[str, object]:
        if isinstance(content, dict):
            return dict(content)
        if isinstance(content, str):
            content = self._extract_json_text(content)
            parsed = self._parse_json_object(content)
            if parsed is None:
                return {"text": content}
            if isinstance(parsed, dict):
                return dict(parsed)
            return {"text": content}
        return {}

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
