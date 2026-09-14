-- Agent Engine auth schema (1.0.1)
-- Passwords are NEVER stored in plaintext; application writes PBKDF2-HMAC-SHA256 hashes.
-- Run via: uv run python scripts/seed_auth_users.py
-- or apply this SQL then seed from the same script.

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
CREATE INDEX IF NOT EXISTS ix_auth_users_username ON auth_users (username);

-- Seed users are inserted by scripts/seed_auth_users.py (passwords hashed in app).
-- Never INSERT password plaintext into password_hash.
