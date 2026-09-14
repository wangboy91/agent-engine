"""End-to-end smoke: account login → engine Principal APIs."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

ACCOUNT = "http://127.0.0.1:8051"
ENGINE = "http://127.0.0.1:8050"


def req(method: str, url: str, body: dict | None = None, headers: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("content-type", "application/json")
    for k, v in (headers or {}).items():
        r.add_header(k, v)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return e.code, {"detail": raw}


def main() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool, extra: str = "") -> None:
        if cond:
            print(f"  OK  {name}")
        else:
            failures.append(f"{name} {extra}")
            print(f"  FAIL {name} {extra}")

    print("== account health ==")
    st, body = req("GET", f"{ACCOUNT}/health")
    check("account /health", st == 200 and body and body.get("service") == "account", str(body))

    print("== engine health ==")
    st, body = req("GET", f"{ENGINE}/health")
    check("engine /health", st == 200, str(body))

    print("== login tenant.admin (bootstrap) ==")
    st, login = req(
        "POST",
        f"{ACCOUNT}/auth/login",
        {"username": "tenant.admin", "password": "Tenant@123"},
    )
    check("login tenant.admin", st == 200 and login and login.get("access_token"), str(login)[:200])
    token = (login or {}).get("access_token", "")
    auth = {"Authorization": f"Bearer {token}"}

    print("== account me / users ==")
    st, me = req("GET", f"{ACCOUNT}/auth/me", headers=auth)
    check("account me", st == 200 and me and me.get("principal_id") == "u_tenant_admin", str(me))
    st, users = req("GET", f"{ACCOUNT}/auth/users", headers=auth)
    check("list users", st == 200 and isinstance(users, list) and len(users) >= 7, str(users)[:120])

    print("== engine accepts bearer ==")
    st, tenants = req("GET", f"{ENGINE}/api/v1/tenants", headers=auth)
    check("engine tenants with bearer", st == 200, str(tenants)[:200])

    print("== ensure tenant/workspace via bearer ==")
    st, t = req(
        "POST",
        f"{ENGINE}/api/v1/tenants",
        {"tenant_id": "t-demo", "name": "Acme"},
        headers=auth,
    )
    check("create/ensure tenant", st in (200, 400), f"{st} {t}")  # 400 if exists is ok if code is ALREADY
    st, wss = req("GET", f"{ENGINE}/api/v1/tenants/t-demo/workspaces", headers=auth)
    check("list workspaces", st == 200, str(wss)[:200])
    if st == 200 and isinstance(wss, list) and not wss:
        st, ws = req(
            "POST",
            f"{ENGINE}/api/v1/tenants/t-demo/workspaces",
            {"workspace_key": "content", "name": "内容生产工作区"},
            headers=auth,
        )
        check("create workspace", st == 200, str(ws)[:200])
        ws_id = (ws or {}).get("tenant_workspace_id")
    elif st == 200 and isinstance(wss, list):
        ws_id = wss[0].get("tenant_workspace_id")
    else:
        ws_id = None
    check("have workspace", bool(ws_id), str(ws_id))

    print("== identity publish grant ==")
    if ws_id:
        st, idef = req(
            "POST",
            f"{ENGINE}/api/v1/tenants/t-demo/workspaces/{ws_id}/identities",
            {"key": "smoke-plan", "name": "联调发展规划助手"},
            headers=auth,
        )
        check("create identity (or exists)", st == 200 or st == 400, str(idef)[:200])
        def_id = (idef or {}).get("definition_id")
        if not def_id:
            st, ids = req(
                "GET",
                f"{ENGINE}/api/v1/tenants/t-demo/workspaces/{ws_id}/identities",
                headers=auth,
            )
            if st == 200 and isinstance(ids, list):
                for item in ids:
                    if item.get("key") == "smoke-plan":
                        def_id = item.get("definition_id")
        if def_id:
            st, ver = req(
                "POST",
                f"{ENGINE}/api/v1/tenants/t-demo/workspaces/{ws_id}/identities/{def_id}/versions",
                {
                    "version": f"1.0.{int(__import__('time').time()) % 100000}",
                    "model_profile": "mock",
                    "system_prompt": "help",
                },
                headers=auth,
            )
            check("create version", st == 200, str(ver)[:200])
            ver_id = (ver or {}).get("version_id")
            if ver_id:
                st, pub = req(
                    "POST",
                    f"{ENGINE}/api/v1/tenants/t-demo/workspaces/{ws_id}/identity-versions/{ver_id}/publish",
                    headers=auth,
                )
                check("publish", st == 200, str(pub)[:200])
                st, grant = req(
                    "POST",
                    f"{ENGINE}/api/v1/tenants/t-demo/workspaces/{ws_id}/grants",
                    {
                        "identity_version_id": ver_id,
                        "grantee_type": "group",
                        "grantee_id": "all-staff",
                    },
                    headers=auth,
                )
                check("grant all-staff", st == 200, str(grant)[:200])

    print("== employee login sees agent ==")
    st, emp = req(
        "POST",
        f"{ACCOUNT}/auth/login",
        {"username": "user.gu", "password": "User@123"},
    )
    check("employee login", st == 200, str(emp)[:120])
    eauth = {"Authorization": f"Bearer {(emp or {}).get('access_token','')}"}
    st, mine = req("GET", f"{ENGINE}/api/v1/me/identities", headers=eauth)
    check("me/identities", st == 200 and isinstance(mine, list) and len(mine) >= 1, str(mine)[:200])

    print("== session isolation ==")
    if mine:
        iv = mine[0]["identity_version_id"]
        st, sess = req(
            "POST",
            f"{ENGINE}/api/v1/me/identities/{iv}/sessions",
            {"session_id": "smoke-s1"},
            headers=eauth,
        )
        check("create session", st == 200 and sess and sess.get("owner_principal_id") == "u_alice", str(sess)[:200])
        st, other = req(
            "POST",
            f"{ACCOUNT}/auth/login",
            {"username": "user.ye", "password": "User@123"},
        )
        oauth = {"Authorization": f"Bearer {(other or {}).get('access_token','')}"}
        st, denied = req("GET", f"{ENGINE}/api/v1/me/sessions/smoke-s1", headers=oauth)
        check("cross-user session 404", st == 404, str(denied)[:200])
        st, own = req("GET", f"{ENGINE}/api/v1/me/sessions/smoke-s1", headers=eauth)
        check("own session 200", st == 200, str(own)[:200])

    print("== skill run with principal ==")
    st, run = req(
        "POST",
        f"{ENGINE}/skills/talking-video/runs",
        {"input": {"topic": "smoke", "platform": "xiaohongshu", "duration_seconds": 30}},
        headers=eauth,
    )
    check("run skill", st == 200 and run and run.get("status") in ("succeeded", "failed", "waiting_approval"), str(run)[:200])
    ctx = (run or {}).get("context") or {}
    check("run owner", ctx.get("owner_principal_id") == "u_alice", str(ctx)[:200])
    check("run tenant", ctx.get("tenant_id") == "t-demo", str(ctx)[:200])

    print("== artifacts me ==")
    st, arts = req("GET", f"{ENGINE}/api/v1/me/artifacts?path=/", headers=eauth)
    check("me artifacts", st == 200 and arts and "folders" in arts, str(arts)[:200])

    print("== employee cannot create tenant ==")
    st, forbid = req(
        "POST",
        f"{ENGINE}/api/v1/tenants",
        {"tenant_id": "t-x", "name": "X"},
        headers=eauth,
    )
    check("end_user create tenant 403", st == 403, f"{st} {forbid}")

    print()
    if failures:
        print("FAILURES:")
        for f in failures:
            print(" -", f)
        return 1
    print("ALL SMOKE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
