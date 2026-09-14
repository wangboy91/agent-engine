import { useState } from "react";
import { accountApi, saveSession } from "../api/client";
import { PageShell } from "../components/PageShell";
import { ROLES, type PrincipalRole } from "../config";
import { useApp } from "../App";

const QUICK: { label: string; username: string; password: string; role: PrincipalRole }[] = [
  { label: "空间管理员", username: "ws.admin", password: "WsAdmin@123", role: "ws_admin" },
  { label: "开发者", username: "dev.lin", password: "Dev@12345", role: "developer" },
  { label: "运营", username: "ops.li", password: "Ops@12345", role: "operator" },
  { label: "员工 顾南", username: "user.gu", password: "User@123", role: "end_user" },
  { label: "员工 叶清", username: "user.ye", password: "User@123", role: "end_user" },
];

export function LoginPage() {
  const { toast, setRole } = useApp();
  const [username, setUsername] = useState("ws.admin");
  const [password, setPassword] = useState("WsAdmin@123");
  const [loading, setLoading] = useState(false);

  async function doLogin(u: string, p: string) {
    setLoading(true);
    try {
      const res = await accountApi.login(u, p);
      saveSession(res.access_token, res.principal);
      const roles = (res.principal.workspace_roles as string[]) || [];
      let role: PrincipalRole = "end_user";
      if (roles.includes("platform_admin")) role = "platform_admin";
      else if (roles.includes("tenant_admin")) role = "tenant_admin";
      else if (roles.includes("ws_admin")) role = "ws_admin";
      else if (roles.includes("developer")) role = "developer";
      else if (roles.includes("operator")) role = "operator";
      else if (roles.includes("auditor")) role = "auditor";
      setRole(role);
      toast(`登录成功：${String(res.profile.display_name || u)}`, "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "danger");
    } finally {
      setLoading(false);
    }
  }

  return (
    <PageShell
      crumb="账号权限服务"
      title="登录"
      desc="登录走独立账号服务（:8001）；智能体数据仍打引擎（:8000）。"
    >
      <div className="card" style={{ maxWidth: 480 }}>
        <div className="card-body">
          <div className="form-grid" style={{ gridTemplateColumns: "1fr" }}>
            <div className="form-field">
              <label>用户名</label>
              <input value={username} onChange={(e) => setUsername(e.target.value)} />
            </div>
            <div className="form-field">
              <label>密码</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>
          <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
            <button
              className="btn btn-primary"
              disabled={loading}
              onClick={() => void doLogin(username, password)}
            >
              登录
            </button>
          </div>
          <div className="hint" style={{ marginTop: 16 }}>
            快捷账号（联调，详见 docs/测试账号.md）：
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
            {QUICK.map((q) => (
              <button
                key={q.username}
                type="button"
                className="btn btn-sm"
                disabled={loading}
                onClick={() => {
                  setUsername(q.username);
                  setPassword(q.password);
                  void doLogin(q.username, q.password);
                }}
              >
                {q.label}
              </button>
            ))}
          </div>
          <p className="hint" style={{ marginTop: 16 }}>
            当前角色切换器（{Object.keys(ROLES).length} 种）仍可用于无登录联调。
          </p>
        </div>
      </div>
    </PageShell>
  );
}
