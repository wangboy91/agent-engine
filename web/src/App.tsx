import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import {
  DEV_ROLE_SWITCHER,
  ROLES,
  type PrincipalProfile,
  type PrincipalRole,
  canApprove,
  canCreateAgent,
  canManageMembers,
} from "./config";
import { AgentsPage } from "./pages/AgentsPage";
import { AgentDetailPage } from "./pages/AgentDetailPage";
import { ArtifactsPage } from "./pages/ArtifactsPage";
import { ApprovalsPage } from "./pages/ApprovalsPage";
import { OverviewPage } from "./pages/OverviewPage";
import { RunsPage } from "./pages/RunsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SkillsPage } from "./pages/SkillsPage";
import { WorkbenchChatPage } from "./pages/WorkbenchChatPage";
import { WorkbenchHomePage } from "./pages/WorkbenchHomePage";

interface AppCtx {
  principal: PrincipalProfile;
  setRole: (role: PrincipalRole) => void;
  tenant: string;
  setTenant: (v: string) => void;
  toast: (msg: string, kind?: "success" | "danger") => void;
}

const Ctx = createContext<AppCtx | null>(null);

export function useApp(): AppCtx {
  const value = useContext(Ctx);
  if (!value) throw new Error("AppCtx missing");
  return value;
}

function Toasts({ items }: { items: { id: number; msg: string; kind?: string }[] }) {
  return (
    <div className="toast-host">
      {items.map((t) => (
        <div key={t.id} className={`toast ${t.kind || ""}`}>
          {t.msg}
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const [role, setRoleState] = useState<PrincipalRole>("ws_admin");
  const [tenant, setTenant] = useState("t-demo");
  const [toasts, setToasts] = useState<{ id: number; msg: string; kind?: string }[]>([]);
  const navigate = useNavigate();

  const principal = useMemo(() => {
    const base = ROLES[role];
    return { ...base, tenantId: tenant } satisfies PrincipalProfile;
  }, [role, tenant]);

  const toast = useCallback((msg: string, kind?: "success" | "danger") => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, msg, kind }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 2600);
  }, []);

  const setRole = useCallback(
    (next: PrincipalRole) => {
      setRoleState(next);
      const mode = ROLES[next].mode;
      navigate(mode === "workbench" ? "/app/my-agents" : "/console/overview");
      toast(`已切换角色：${ROLES[next].label}`);
    },
    [navigate, toast],
  );

  const isConsole = principal.mode === "console";

  const consoleNav = [
    { section: "概览" },
    { to: "/console/overview", label: "总览", show: true },
    { section: "业务" },
    { to: "/console/agents", label: "智能体", show: true },
    { to: "/console/agents/new", label: "创建智能体", show: canCreateAgent(principal) },
    { to: "/console/skills", label: "Skill", show: true },
    { section: "运行" },
    { to: "/console/runs", label: "Run", show: true },
    { to: "/console/artifacts", label: "产出物目录", show: true },
    { to: "/console/approvals", label: "审批", show: canApprove(principal) },
    { section: "治理" },
    { to: "/console/settings", label: "工作空间设置", show: canManageMembers(principal) },
  ];

  const workbenchNav = [
    { to: "/app/my-agents", label: "我的智能体", show: true },
    { to: "/app/chat", label: "会话", show: true },
    { to: "/app/artifacts", label: "我的产出物", show: true },
  ];

  return (
    <Ctx.Provider value={{ principal, setRole, tenant, setTenant, toast }}>
      <div className="app">
        <header className="topbar">
          <div className="topbar-left">
            <div className="brand">
              <span className="brand-mark" />
              <span>Agent Engine</span>
              <span className="version-chip">1.0.1</span>
            </div>
            <select
              className="scope-select"
              value={tenant}
              onChange={(e) => {
                setTenant(e.target.value);
                toast("已切换租户，缓存已清空");
              }}
              aria-label="租户"
            >
              <option value="t-demo">演示租户 · Acme</option>
              <option value="t-beta">试点租户 · Contoso</option>
            </select>
            <span className="pill pill-success">生产</span>
          </div>
          <div className="topbar-right">
            {DEV_ROLE_SWITCHER && (
              <select
                className="scope-select role-select"
                value={role}
                onChange={(e) => setRole(e.target.value as PrincipalRole)}
                aria-label="演示角色"
              >
                {(Object.keys(ROLES) as PrincipalRole[]).map((r) => (
                  <option key={r} value={r}>
                    {ROLES[r].label}
                  </option>
                ))}
              </select>
            )}
            <div className="user-chip">
              <span className="avatar">{principal.displayName.slice(0, 1)}</span>
              <span className="user-meta">
                <span className="user-name">{principal.displayName}</span>
                <span className="user-role">{principal.label}</span>
              </span>
            </div>
          </div>
        </header>

        <div className="perm-banner">
          Principal：{principal.displayName} · {principal.label} · tenant=
          {principal.tenantId} · principal={principal.principalId}。列表与产物默认仅本人或角色可见范围。
        </div>

        <div className="shell">
          <nav className="sidenav">
            {(isConsole ? consoleNav : workbenchNav).map((item, idx) =>
              "section" in item ? (
                <div className="nav-section" key={`s-${idx}`}>
                  {item.section}
                </div>
              ) : item.show ? (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) => `nav-item${isActive ? " is-active" : ""}`}
                >
                  {item.label}
                </NavLink>
              ) : null,
            )}
            <div className="nav-section">切换入口</div>
            {isConsole ? (
              <NavLink to="/app/my-agents" className="nav-item">
                用户工作台
              </NavLink>
            ) : (
              <NavLink to="/console/overview" className="nav-item">
                管理控制台
              </NavLink>
            )}
          </nav>

          <main className="main">
            <Routes>
              <Route path="/" element={<Navigate to="/console/overview" replace />} />
              <Route path="/console" element={<Navigate to="/console/overview" replace />} />
              <Route path="/console/overview" element={<OverviewPage />} />
              <Route path="/console/agents" element={<AgentsPage />} />
              <Route path="/console/agents/new" element={<AgentDetailPage mode="create" />} />
              <Route path="/console/agents/:definitionId" element={<AgentDetailPage mode="detail" />} />
              <Route path="/console/skills" element={<SkillsPage />} />
              <Route path="/console/runs" element={<RunsPage />} />
              <Route path="/console/artifacts" element={<ArtifactsPage />} />
              <Route path="/console/approvals" element={<ApprovalsPage />} />
              <Route path="/console/settings" element={<SettingsPage />} />
              <Route path="/app" element={<Navigate to="/app/my-agents" replace />} />
              <Route path="/app/my-agents" element={<WorkbenchHomePage />} />
              <Route path="/app/chat" element={<WorkbenchChatPage />} />
              <Route path="/app/artifacts" element={<ArtifactsPage userOnly />} />
              <Route path="*" element={<Navigate to="/console/overview" replace />} />
            </Routes>
          </main>
        </div>
        <Toasts items={toasts} />
      </div>
    </Ctx.Provider>
  );
}
