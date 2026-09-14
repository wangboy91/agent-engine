"""Config loading."""

from __future__ import annotations

import os
from pathlib import Path


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def load_env() -> None:
    here = Path(__file__).resolve()
    _load_env_file(here.parents[1] / ".env")
    _load_env_file(here.parents[2] / ".env")
    _load_env_file(here.parents[2] / "engine" / ".env")


def database_url() -> str:
    load_env()
    url = (
        os.getenv("ACCOUNT_DATABASE_URL")
        or os.getenv("AGENT_ENGINE_DATABASE_URL")
        or os.getenv("DATABASE_URL")
    )
    if not url:
        raise RuntimeError("ACCOUNT_DATABASE_URL (or AGENT_ENGINE_DATABASE_URL) is required")
    return url


def token_secret() -> bytes:
    load_env()
    return os.getenv("ACCOUNT_TOKEN_SECRET", "agent-engine-1.0.1-demo").encode("utf-8")


def default_port() -> int:
    load_env()
    return int(os.getenv("ACCOUNT_SERVICE_PORT", "8051"))
