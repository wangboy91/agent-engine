import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useApp } from "../App";
import { PageShell } from "../components/PageShell";
import type { IdentityDefinition } from "./types";

export function AgentsPage() {
  const { principal, toast } = useApp();
  const [items, setItems] = useState<IdentityDefinition[]>([]);
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [key, setKey] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await api.get<{ tenant_workspace_id: string }[]>(
          `/api/v1/tenants/${principal.tenantId}/workspaces`,
          principal,
        );
        if (cancelled) return;
        const ws = list[0]?.tenant_workspace_id || null;
        setWorkspaceId(ws);
        if (!ws) {
          setItems([]);
          return;
        }
        const identities = await api.get<IdentityDefinition[]>(
          `/api/v1/tenants/${principal.tenantId}/workspaces/${ws}/identities`,
          principal,
        );
        if (!cancelled) setItems(identities);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [principal]);

  async function createIdentity() {
    if (!workspaceId) {
      toast("请先在设置中创建工作空间", "danger");
      return;
    }
    if (!key.trim() || !name.trim()) {
      toast("请填写编码与名称", "danger");
      return;
    }
    try {
      const created = await api.post<IdentityDefinition>(
        `/api/v1/tenants/${principal.tenantId}/workspaces/${workspaceId}/identities`,
        principal,
        { key: key.trim(), name: name.trim() },
      );
      setItems((prev) => [...prev, created]);
      setName("");
      setKey("");
      toast("已创建 Identity Definition", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "danger");
    }
  }

  return (
    <PageShell
      crumb="管理控制台 / 智能体"
      title="智能体"
      desc="Identity Definition。版本与发布在详情页完成。"
    >
      {error ? <div className="error-box">{error}</div> : null}
      <div className="card" style={{ marginBottom: 12 }}>
        <div className="card-header">
          <h2 className="card-title">新建 Definition</h2>
          <span className="hint">workspace={workspaceId || "未创建"}</span>
        </div>
        <div className="card-body">
          <div className="form-grid">
            <div className="form-field">
              <label>编码 key</label>
              <input
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder="plan-helper"
              />
            </div>
            <div className="form-field">
              <label>名称</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="发展规划助手"
              />
            </div>
          </div>
          <div style={{ marginTop: 12 }}>
            <button className="btn btn-primary" onClick={createIdentity}>
              创建
            </button>
          </div>
        </div>
      </div>
      <div className="card">
        <div className="card-body tight">
          {items.length === 0 ? (
            <div className="empty">
              <div className="empty-title">还没有智能体</div>
              使用上方表单创建，或在设置中初始化租户/工作空间
            </div>
          ) : (
            <table className="data">
              <thead>
                <tr>
                  <th>名称</th>
                  <th>编码</th>
                  <th>描述</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {items.map((a) => (
                  <tr key={a.definition_id}>
                    <td>
                      <strong>{a.name}</strong>
                    </td>
                    <td className="mono">{a.key}</td>
                    <td>{a.description || "—"}</td>
                    <td className="actions">
                      <Link className="btn btn-sm" to={`/console/agents/${a.definition_id}`}>
                        配置
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </PageShell>
  );
}
