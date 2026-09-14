"""Seed demo users via application service."""

from __future__ import annotations

import sys

from app.application.auth_service import AuthService
from app.domain import AccountError, User, new_user_id
from app.domain.passwords import hash_password
from app.infrastructure.db import init_db, make_engine, make_session_factory
from app.infrastructure.repositories import SqlUserRepository

SEED = [
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


def main() -> int:
    engine = make_engine()
    init_db(engine)
    sessions = make_session_factory(engine)
    repo = SqlUserRepository(sessions)
    actor = {
        "principal_type": "platform_operator",
        "workspace_roles": ["platform_admin"],
        "tenant_id": "t-demo",
    }
    service = AuthService(users=repo)
    created: list[str] = []
    try:
        for username, password, tenant, pid, name, roles, groups, ptype in SEED:
            if repo.get_by_username(username) is not None:
                continue
            user = User(
                user_id=pid or new_user_id(),
                username=username,
                password_hash=hash_password(password),
                tenant_id=tenant,
                display_name=name,
                workspace_roles=roles,
                group_ids=groups,
                principal_type=ptype,  # type: ignore[arg-type]
            )
            repo.create_user(user)
            created.append(username)
        print(f"seeded: {', '.join(created) if created else '(all exist)'}")
        print(f"users: {len(service.list_users_for(actor))}")
        return 0
    except AccountError as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"seed failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
