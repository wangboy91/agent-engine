import asyncio
import json

import httpx
import pytest

from bkl_engine.domain.errors import BklEngineError
from bkl_engine.infrastructure.config.engine_config import ModelProfileConfig
from bkl_engine.infrastructure.model_gateway.providers.anthropic import AnthropicProvider
from bkl_engine.infrastructure.model_gateway.providers.openai_compatible import (
    OpenAICompatibleProvider,
)


def test_openai_compatible_provider_posts_chat_completions(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("MODEL_KEY", "secret")

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://example.com/v2/chat/completions"
        assert request.headers["authorization"] == "Bearer secret"
        body = json.loads(request.content)
        assert body["model"] == "astron-code-latest"
        assert body["messages"][0]["role"] == "user"
        assert body["max_tokens"] == 4096
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    provider = OpenAICompatibleProvider(
        ModelProfileConfig(
            protocol="openai-compatible",
            base_url="https://example.com/v2",
            api_key_env="MODEL_KEY",
            model="astron-code-latest",
        ),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    response = asyncio.run(provider.chat("active", [{"role": "user", "content": "ping"}], []))

    assert response.final_output == {"ok": True}
    assert response.usage.input_tokens == 3
    assert response.usage.output_tokens == 2


def test_openai_compatible_provider_parses_fenced_json(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("MODEL_KEY", "secret")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '```json\n{"ok": true}\n```'}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    provider = OpenAICompatibleProvider(
        ModelProfileConfig(
            protocol="openai-compatible",
            base_url="https://example.com/v2",
            api_key_env="MODEL_KEY",
            model="astron-code-latest",
        ),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    response = asyncio.run(provider.chat("active", [{"role": "user", "content": "ping"}], []))

    assert response.final_output == {"ok": True}


def test_openai_compatible_provider_parses_embedded_fenced_json(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("MODEL_KEY", "secret")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '结果如下：\n```json\n{"ok": true}\n```\n请查收'
                        }
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    provider = OpenAICompatibleProvider(
        ModelProfileConfig(
            protocol="openai-compatible",
            base_url="https://example.com/v2",
            api_key_env="MODEL_KEY",
            model="astron-code-latest",
        ),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    response = asyncio.run(provider.chat("active", [{"role": "user", "content": "ping"}], []))

    assert response.final_output == {"ok": True}


def test_openai_compatible_provider_repairs_unescaped_newlines(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("MODEL_KEY", "secret")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"screen_text": "第一行\n第二行"}'}}
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    provider = OpenAICompatibleProvider(
        ModelProfileConfig(
            protocol="openai-compatible",
            base_url="https://example.com/v2",
            api_key_env="MODEL_KEY",
            model="astron-code-latest",
        ),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    response = asyncio.run(provider.chat("active", [{"role": "user", "content": "ping"}], []))

    assert response.final_output == {"screen_text": "第一行\n第二行"}


def test_openai_compatible_provider_wraps_network_errors(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("MODEL_KEY", "secret")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.RemoteProtocolError("Server disconnected without sending a response.")

    provider = OpenAICompatibleProvider(
        ModelProfileConfig(
            protocol="openai-compatible",
            base_url="https://example.com/v2",
            api_key_env="MODEL_KEY",
            model="astron-code-latest",
        ),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(BklEngineError) as exc_info:
        asyncio.run(provider.chat("active", [{"role": "user", "content": "ping"}], []))

    assert exc_info.value.code == "MODEL_PROVIDER_ERROR"
    assert exc_info.value.retryable is True
    assert exc_info.value.details["error_type"] == "RemoteProtocolError"


def test_anthropic_provider_posts_messages(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("MODEL_KEY", "secret")

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://example.com/anthropic/v1/messages"
        assert request.headers["x-api-key"] == "secret"
        assert request.headers["anthropic-version"] == "2023-06-01"
        body = json.loads(request.content)
        assert body["model"] == "astron-code-latest"
        assert body["messages"][0]["role"] == "user"
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": '{"ok": true}'}],
                "usage": {"input_tokens": 4, "output_tokens": 2},
            },
        )

    provider = AnthropicProvider(
        ModelProfileConfig(
            protocol="anthropic",
            base_url="https://example.com/anthropic",
            api_key_env="MODEL_KEY",
            model="astron-code-latest",
        ),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    response = asyncio.run(provider.chat("active", [{"role": "user", "content": "ping"}], []))

    assert response.final_output == {"ok": True}
    assert response.usage.input_tokens == 4
    assert response.usage.output_tokens == 2
