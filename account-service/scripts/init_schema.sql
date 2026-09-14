-- Account service schema (shared DB with engine is OK; later split)
-- Passwords are PBKDF2 hashes only.

CREATE TABLE IF NOT EXISTS auth_users (
    user_id              VARCHAR(64) PRIMARY KEY,
    username             VARCHAR(128) NOT NULL UNIQUE,
    password_hash        TEXT NOT NULL,
    tenant_id            VARCHAR(64) NOT NULL,
    principal_type       VARCHAR(32) NOT NULL DEFAULT 'user',
    display_name         VARCHAR(128) NOT NULL,
    workspace_roles      JSONB NOT NULL DEFAULT '[]'::jsonb,
    group_ids            JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    password_updated_at  TIMESTAMPTZ NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL,
    updated_at           TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_auth_users_tenant ON auth_users (tenant_id);

CREATE TABLE IF NOT EXISTS identity_links (
    link_id           VARCHAR(64) PRIMARY KEY,
    external_system   VARCHAR(64) NOT NULL,
    external_user_id  VARCHAR(128) NOT NULL,
    tenant_id         VARCHAR(64) NOT NULL,
    principal_id      VARCHAR(64) NOT NULL,
    display_name      VARCHAR(128),
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_identity_links_ext
    ON identity_links (external_system, external_user_id, tenant_id);
