"""Database connection configuration.

1.0.1 ships a single PostgreSQL database for both platform registry and runtime data.
Two-database split is reserved via env vars:

- ``AGENT_ENGINE_DATABASE_URL``           primary/control-plane DB (platform registry)
- ``AGENT_ENGINE_RUNTIME_DATABASE_URL``   optional runtime DB (session/run/trace)

When runtime URL is unset, runtime stores use the primary URL.
When neither is set, callers fall back to JSON adapters.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def _engine_env_path() -> Path:
    # engine/app/infrastructure/config -> engine/
    return Path(__file__).resolve().parents[3] / ".env"


def load_database_env_once() -> None:
    """Load database URLs from engine/.env if not already in the process environment."""
    keys = {
        "AGENT_ENGINE_DATABASE_URL",
        "AGENT_ENGINE_RUNTIME_DATABASE_URL",
        "DATABASE_URL",
    }
    if any(os.getenv(key) for key in keys):
        return
    env_path = _engine_env_path()
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in keys:
            os.environ.setdefault(key, value)


def primary_database_url() -> str | None:
    load_database_env_once()
    return os.getenv("AGENT_ENGINE_DATABASE_URL") or os.getenv("DATABASE_URL")


def runtime_database_url() -> str | None:
    """Runtime store URL; defaults to primary when secondary is not configured."""
    load_database_env_once()
    return os.getenv("AGENT_ENGINE_RUNTIME_DATABASE_URL") or primary_database_url()


def database_mode() -> str:
    """Return ``pg`` when a database URL is available, otherwise ``json``."""
    return "pg" if primary_database_url() or runtime_database_url() else "json"


def create_engine_from_url(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True, future=True)


def probe_engine(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
