"""Persistence infrastructure adapters."""

from app.domain.platform import build_artifact_meta
from app.infrastructure.persistence.artifact_store import LocalArtifactStore
from app.infrastructure.persistence.catalog_store import (
    CatalogDocument,
    CatalogEntry,
    JsonCatalogStore,
)
from app.infrastructure.persistence.memory_store import LocalMarkdownMemoryStore
from app.infrastructure.persistence.platform_registry import (
    InMemoryPlatformRegistryStore,
    JsonPlatformRegistryStore,
    list_directory_nodes,
)
from app.infrastructure.persistence.platform_registry_pg import (
    PostgresPlatformRegistryStore,
    create_platform_registry_from_env,
    default_database_url,
    init_db,
)
from app.infrastructure.persistence.policy_store import InMemoryPolicyStore, JsonPolicyStore
from app.infrastructure.persistence.run_store import InMemoryRunStore, JsonRunStore
from app.infrastructure.persistence.runtime_registry_pg import (
    PostgresAgentSessionStore,
    PostgresRunStore,
    PostgresTraceStore,
    create_postgres_run_store,
    create_postgres_session_store,
    create_postgres_trace_store,
    create_runtime_engine,
)
from app.infrastructure.persistence.secret_store import InMemorySecretStore, JsonSecretStore
from app.infrastructure.persistence.session_store import (
    InMemoryAgentSessionStore,
    JsonAgentSessionStore,
)
from app.infrastructure.persistence.workspace_store import (
    InMemoryWorkspaceStore,
    JsonWorkspaceStore,
)

__all__ = [
    "CatalogDocument",
    "CatalogEntry",
    "InMemoryAgentSessionStore",
    "InMemoryPlatformRegistryStore",
    "InMemoryPolicyStore",
    "InMemoryRunStore",
    "InMemorySecretStore",
    "InMemoryWorkspaceStore",
    "JsonAgentSessionStore",
    "JsonCatalogStore",
    "JsonPlatformRegistryStore",
    "JsonPolicyStore",
    "JsonRunStore",
    "JsonSecretStore",
    "JsonWorkspaceStore",
    "LocalArtifactStore",
    "LocalMarkdownMemoryStore",
    "PostgresAgentSessionStore",
    "PostgresPlatformRegistryStore",
    "PostgresRunStore",
    "PostgresTraceStore",
    "build_artifact_meta",
    "create_platform_registry_from_env",
    "create_postgres_run_store",
    "create_postgres_session_store",
    "create_postgres_trace_store",
    "create_runtime_engine",
    "default_database_url",
    "init_db",
    "list_directory_nodes",
]
