import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useApp } from "../App";
import { PageShell } from "../components/PageShell";
import { canCreateAgent } from "../config";

interface Tenant {
  tenant_id: string;
  name: string;
}
interface Workspace {
  tenant_workspace_id: string;
  workspace_key: string;
  name: string;
}

export function SettingsPage() {
  const { principal, toast } = useApp();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [tenantId, setTenantId] = useState(principal.tenantId);
  const [tenantName, setTenantName] = useState("Acme");
  const [wsKey, setWsKey] = useState("content");
  const [wsName, setWsName] = useState("内容生产工作区");
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      const t = await api.get<Tenant[]>("/api/v1/tenants", principal);
      setTenants(t);
      const w = await api.get<Workspace[]>(
        `/api/v1/tenants/${principal.tenantId}/workspaces`,
        principal,
      );
      setWorkspaces(w);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [principal.tenantId]);

  async function ensureTenant() {
    try {
      await api.post("/api/v1/tenants", principal, {
        tenant_id: tenantId,
        name: tenantName,
      });
      toast("租户已创建", "success");
      await refresh();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "danger");
    }
  }

  async function ensureWorkspace() {
    try {
      await api.post(`/api/v1/tenants/${principal.tenantId}/workspaces`, principal, {
        workspace_key: wsKey,
        name: wsName,
      });
      toast("工作空间已创建", "success");
      await refresh();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "danger");
    }
  }

  return (
    <PageShell
      crumb="管理控制台 / 设置"
      title="工作空间设置"
      desc="初始化租户与 TenantWorkspace"
    >
      {error ? <div className="error-box">{error}</div> : null}
      <div className="card" style={{ marginBottom: 12 }}>
        <div className="card-header">
          <h2 className="card-title">确保租户</h2>
        </div>
        <div className="card-body">
          <div className="form-grid">
            <div className="form-field">
              <label>Tenant ID</label>
              <input value={tenantId} onChange={(e) => setTenantId(e.target.value)} />
            </div>
            <div className="form-field">
              <label>名称</label>
              <input value={tenantName} onChange={(e) => setTenantName(e.target.value)} />
            </div>
          </div>
          <div style={{ marginTop: 12 }}>
            <button
              className="btn btn-primary"
              onClick={ensureTenant}
              disabled={!canCreateAgent(principal)}
            >
              创建 / 确保租户
            </button>
          </div>
          <div className="hint" style={{ marginTop: 8 }}>
            现有：{tenants.map((t) => t.tenant_id).join(", ") || "无"}
          </div>
        </div>
      </div>
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">确保工作空间</h2>
        </div>
        <div className="card-body">
          <div className="form-grid">
            <div className="form-field">
              <label>workspace_key</label>
              <input value={wsKey} onChange={(e) => setWsKey(e.target.value)} />
            </div>
            <div className="form-field">
              <label>名称</label>
              <input value={wsName} onChange={(e) => setWsName(e.target.value)} />
            </div>
          </div>
          <div style={{ marginTop: 12 }}>
            <button
              className="btn btn-primary"
              onClick={ensureWorkspace}
              disabled={!canCreateAgent(principal)}
            >
              创建工作空间
            </button>
          </div>
          <div className="hint" style={{ marginTop: 8 }}>
            现有：
            {workspaces
              .map((w) => `${w.workspace_key}(${w.tenant_workspace_id.slice(0, 8)})`)
              .join(", ") || "无"}
          </div>
        </div>
      </div>
    </PageShell>
  );
}
