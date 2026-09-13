import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useApp } from "../App";
import { PageShell } from "../components/PageShell";
import { canPublish } from "../config";
import type { IdentityDefinition, IdentityVersion } from "./types";

export function AgentDetailPage({ mode }: { mode: "create" | "detail" }) {
  const { definitionId } = useParams();
  const { principal, toast } = useApp();
  const navigate = useNavigate();
  const [definition, setDefinition] = useState<IdentityDefinition | null>(null);
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [version, setVersion] = useState("1.0.0");
  const [systemPrompt, setSystemPrompt] = useState("你是企业内的业务助手。");
  const [versions, setVersions] = useState<IdentityVersion[]>([]);
  const [error, setError] = useState<string | null>(null);

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
        if (mode === "detail" && definitionId && ws) {
          const identities = await api.get<IdentityDefinition[]>(
            `/api/v1/tenants/${principal.tenantId}/workspaces/${ws}/identities`,
            principal,
          );
          const found = identities.find((i) => i.definition_id === definitionId) || null;
          if (!cancelled) setDefinition(found);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [principal, definitionId, mode]);

  async function createVersion(publish: boolean) {
    if (!workspaceId || !definitionId) {
      toast("缺少 workspace 或 definition", "danger");
      return;
    }
    try {
      const created = await api.post<IdentityVersion>(
        `/api/v1/tenants/${principal.tenantId}/workspaces/${workspaceId}/identities/${definitionId}/versions`,
        principal,
        {
          version,
          model_profile: "mock",
          system_prompt: systemPrompt,
          skill_bindings: [{ skill_id: "talking-video", version: "0.1.0" }],
          tool_bindings: [],
        },
      );
      setVersions((prev) => [created, ...prev]);
      toast(`已创建草稿 ${created.version}`, "success");
      if (publish) {
        const published = await api.post<IdentityVersion>(
          `/api/v1/tenants/${principal.tenantId}/workspaces/${workspaceId}/identity-versions/${created.version_id}/publish`,
          principal,
        );
        setVersions((prev) =>
          prev.map((v) => (v.version_id === published.version_id ? published : v)),
        );
        toast("已发布（可授权）", "success");
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "danger");
    }
  }

  async function grantVersion(versionId: string) {
    if (!workspaceId) return;
    try {
      await api.post(
        `/api/v1/tenants/${principal.tenantId}/workspaces/${workspaceId}/grants`,
        principal,
        {
          identity_version_id: versionId,
          grantee_type: "group",
          grantee_id: "all-staff",
        },
      );
      toast("已授权用户组 all-staff", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "danger");
    }
  }

  if (mode === "create") {
    return (
      <PageShell
        crumb="管理控制台 / 智能体 / 创建"
        title="创建智能体"
        desc="先在列表创建 Definition，再配置版本与授权。"
      >
        <div className="card">
          <div className="card-body">
            <p className="hint">
              1.0.1 将向导拆为：列表创建 Definition → 详情创建 Version → 发布 → Grant。
            </p>
            <button className="btn btn-primary" onClick={() => navigate("/console/agents")}>
              去创建 Definition
            </button>
          </div>
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell
      crumb={`管理控制台 / 智能体 / ${definition?.name || definitionId}`}
      title={definition?.name || "智能体详情"}
      desc={definition ? `key=${definition.key}` : "加载中…"}
      actions={
        <>
          <button className="btn" onClick={() => createVersion(false)}>
            保存草稿版本
          </button>
          <button
            className="btn btn-primary"
            disabled={!canPublish(principal)}
            onClick={() => createVersion(true)}
          >
            创建并发布
          </button>
        </>
      }
    >
      {error ? <div className="error-box">{error}</div> : null}
      <div className="card" style={{ marginBottom: 12 }}>
        <div className="card-header">
          <h2 className="card-title">版本配置</h2>
        </div>
        <div className="card-body">
          <div className="form-grid">
            <div className="form-field">
              <label>版本号</label>
              <input value={version} onChange={(e) => setVersion(e.target.value)} />
            </div>
            <div className="form-field">
              <label>模型 Profile</label>
              <input value="mock" disabled />
            </div>
            <div className="form-field full">
              <label>System Prompt</label>
              <textarea value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} />
            </div>
          </div>
        </div>
      </div>
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">版本列表</h2>
        </div>
        <div className="card-body tight">
          {versions.length === 0 ? (
            <div className="empty">
              <div className="empty-title">尚未创建版本</div>
              点击右上角保存草稿或创建并发布
            </div>
          ) : (
            <table className="data">
              <thead>
                <tr>
                  <th>版本</th>
                  <th>状态</th>
                  <th>version_id</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {versions.map((v) => (
                  <tr key={v.version_id}>
                    <td>{v.version}</td>
                    <td>
                      <span
                        className={`pill ${
                          v.status === "published" ? "pill-success" : "pill-warning"
                        }`}
                      >
                        {v.status}
                      </span>
                    </td>
                    <td className="mono">{v.version_id.slice(0, 8)}…</td>
                    <td className="actions">
                      <button
                        className="btn btn-sm"
                        disabled={v.status !== "published"}
                        onClick={() => grantVersion(v.version_id)}
                      >
                        授权 all-staff
                      </button>
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
