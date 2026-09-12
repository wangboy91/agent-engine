"""Configuration loading primitives."""

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from app.domain.errors import BklEngineError

ModelProtocol = Literal["mock", "openai-compatible", "anthropic"]


class ModelProfileConfig(BaseModel):
    protocol: ModelProtocol
    model: str
    base_url: str | None = None
    api_key_env: str | None = None
    enabled: bool = True
    timeout_seconds: float = 60
    max_tokens: int = 4096
    auth_header: str | None = None
    auth_scheme: str | None = None


class ModelSettings(BaseModel):
    active_profile: str = "mock"
    profiles: dict[str, ModelProfileConfig] = Field(
        default_factory=lambda: {
            "mock": ModelProfileConfig(protocol="mock", model="mock-tool-calling")
        }
    )


class EngineConfig(BaseModel):
    models: ModelSettings = Field(default_factory=ModelSettings)


def load_engine_config(path: str | Path = "bkl.yaml") -> EngineConfig:
    config_path = Path(path)
    _load_dotenv(config_path.parent / ".env")
    if not config_path.exists():
        return EngineConfig()

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if raw is None:
        return EngineConfig()
    if not isinstance(raw, dict):
        raise BklEngineError("CONFIG_INVALID", f"Config must be a YAML object: {config_path}")

    resolved = _resolve_env(raw)
    return EngineConfig.model_validate(resolved)


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        os.environ.setdefault(key, _clean_dotenv_value(value.strip()))


def _clean_dotenv_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _resolve_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_env(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_resolve_env(inner) for inner in value]
    if isinstance(value, str):
        return _resolve_env_string(value)
    return value


def _resolve_env_string(value: str) -> str:
    pattern = re.compile(r"\$\{([A-Z0-9_]+)\}")

    def replace(match: re.Match[str]) -> str:
        env_name = match.group(1)
        env_value = os.environ.get(env_name)
        if env_value is None:
            raise BklEngineError("CONFIG_INVALID", f"Missing environment variable: {env_name}")
        return env_value

    return pattern.sub(replace, value)
