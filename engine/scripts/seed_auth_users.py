"""Seed default users into PostgreSQL auth_users (hashed passwords only)."""

from __future__ import annotations

import argparse
import sys

from app.application.platform.passwords import hash_password
from app.domain.errors import AgentEngineError
from app.infrastructure.config.database import primary_database_url
from app.infrastructure.persistence.auth_store_pg import PostgresAuthStore, create_auth_store

# username, password, tenant, principal_id, display_name, roles, groups, type
DEFAULT_SEED = [
    (
        "platform.admin",
        "Platform@123",
        "t-demo",
        "u_platform_admin",
        "韩启",
        ["platform_admin"],
        [],
        "platform_operator",
    ),
    (
        "tenant.admin",
        "Tenant@123",
        "t-demo",
        "u_tenant_admin",
        "沈舟",
        ["tenant_admin", "ws_admin"],
        [],
        "user",
    ),
    (
        "ws.admin",
        "WsAdmin@123",
        "t-demo",
        "u_ws_admin",
        "赵安",
        ["ws_admin"],
        [],
        "user",
    ),
    (
        "dev.lin",
        "Dev@12345",
        "t-demo",
        "u_dev",
        "林晓晴",
        ["developer"],
        [],
        "user",
    ),
    (
        "ops.li",
        "Ops@12345",
        "t-demo",
        "u_ops",
        "李衡",
        ["operator"],
        ["all-staff"],
        "user",
    ),
    (
        "audit.zhou",
        "Audit@123",
        "t-demo",
        "u_auditor",
        "周谨",
        ["auditor"],
        [],
        "user",
    ),
    (
        "user.gu",
        "User@123",
        "t-demo",
        "u_alice",
        "顾南",
        ["end_user"],
        ["all-staff"],
        "user",
    ),
    (
        "user.ye",
        "User@123",
        "t-demo",
        "u_bob",
        "叶清",
        ["end_user"],
        ["all-staff"],
        "user",
    ),
]


def seed(store: PostgresAuthStore, reset_passwords: bool = False) -> list[str]:
    created: list[str] = []
    for username, password, tenant, principal_id, name, roles, groups, ptype in DEFAULT_SEED:
        existing = store.get_by_username(username)
        if existing is None:
            store.create_user(
                username=username,
                password=password,
                tenant_id=tenant,
                principal_id=principal_id,
                display_name=name,
                workspace_roles=roles,
                group_ids=groups,
                principal_type=ptype,
            )
            created.append(username)
        elif reset_passwords:
            # admin-only maintenance path: set password via direct hash update
            with store._session() as db:  # noqa: SLF001
                from sqlalchemy import select

                from app.infrastructure.persistence.auth_store_pg import AuthUserRow

                row = db.scalar(select(AuthUserRow).where(AuthUserRow.username == username))
                if row is not None:
                    from datetime import UTC, datetime

                    row.password_hash = hash_password(password)
                    row.password_updated_at = datetime.now(UTC)
                    row.updated_at = datetime.now(UTC)
                    db.commit()
            created.append(f"{username}(password-reset)")
    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed auth users into PostgreSQL")
    parser.add_argument(
        "--reset-passwords",
        action="store_true",
        help="Reset seeded users' passwords back to defaults",
    )
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL")
    args = parser.parse_args(argv)

    store = create_auth_store(args.database_url)
    if store is None:
        url = args.database_url or primary_database_url()
        print(f"DATABASE_URL not configured: {url}", file=sys.stderr)
        return 2

    # smoke: hashing never leaves plaintext
    sample = hash_password("Platform@123")
    assert "Platform@123" not in sample

    try:
        created = seed(store, reset_passwords=args.reset_passwords)
    except AgentEngineError as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        return 1

    users = store.list_users("t-demo")
    print(f"seeded/updated: {', '.join(created) if created else '(no changes)'}")
    print(f"users in t-demo: {len(users)}")
    for u in users:
        print(f"  - {u['username']}  roles={','.join(u['workspace_roles'])}")  # type: ignore[index]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
