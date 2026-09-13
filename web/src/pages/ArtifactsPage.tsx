import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { useApp } from "../App";
import { PageShell } from "../components/PageShell";
import type { ArtifactMeta, MeArtifactDir } from "./types";

export function ArtifactsPage({ userOnly = false }: { userOnly?: boolean }) {
  const { principal, toast } = useApp();
  const [dir, setDir] = useState<MeArtifactDir | null>(null);
  const [path, setPath] = useState("/");
  const [preview, setPreview] = useState<string | null>(null);
  const [adminItems, setAdminItems] = useState<ArtifactMeta[]>([]);
  const [elevateOwner, setElevateOwner] = useState("");
  const [elevateReason, setElevateReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const q = encodeURIComponent(path === "/" ? "/" : path);
      const data = await api.get<MeArtifactDir>(`/api/v1/me/artifacts?path=${q}`, principal);
      setDir(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setDir(null);
    }
  }, [principal, path]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (userOnly) return;
    let cancelled = false;
    (async () => {
      try {
        const list = await api.get<{ tenant_workspace_id: string }[]>(
          `/api/v1/tenants/${principal.tenantId}/workspaces`,
          principal,
        );
        const ws = list[0]?.tenant_workspace_id;
        if (!ws || cancelled) return;
        const items = await api.get<ArtifactMeta[]>(
          `/api/v1/tenants/${principal.tenantId}/workspaces/${ws}/artifacts`,
          principal,
        );
        if (!cancelled) setAdminItems(items);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [principal, userOnly]);

  async function elevate() {
    try {
      const list = await api.get<{ tenant_workspace_id: string }[]>(
        `/api/v1/tenants/${principal.tenantId}/workspaces`,
        principal,
      );
      const ws = list[0]?.tenant_workspace_id;
      if (!ws) throw new Error("workspace missing");
      await api.post(
        `/api/v1/tenants/${principal.tenantId}/workspaces/${ws}/artifact-elevations`,
        principal,
        {
          owner_principal_id: elevateOwner,
          reason: elevateReason,
          path_prefix: "",
        },
      );
      toast("提权成功，已写审计", "success");
      setElevateReason("");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "danger");
    }
  }

  return (
    <PageShell
      crumb={userOnly ? "用户工作台 / 我的产出物" : "管理控制台 / 产出物目录"}
      title={userOnly ? "我的产出物" : "产出物目录"}
      desc="按 owner 目录隔离；/api/v1/me/artifacts 仅返回本人树。"
    >
      {error ? <div className="error-box">{error}</div> : null}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">{path}</h2>
          <button className="btn btn-sm" onClick={() => setPath("/")}>
            回根目录
          </button>
        </div>
        <div className="card-body">
          <div className="file-explorer">
            <div className="card" style={{ margin: 0 }}>
              <div className="card-header">
                <h2 className="card-title">目录</h2>
              </div>
              <div className="card-body">
                {(dir?.folders || []).map((f) => (
                  <button
                    key={f}
                    type="button"
                    className="tree-node"
                    onClick={() => setPath((path === "/" ? "" : path) + "/" + f)}
                  >
                    📁 {f}
                  </button>
                ))}
                {dir && dir.folders.length === 0 && dir.files.length === 0 ? (
                  <div className="empty">
                    <div className="empty-title">目录为空</div>
                    运行 Skill 且带 Principal 头后，产物会自动登记
                  </div>
                ) : null}
              </div>
            </div>
            <div className="card" style={{ margin: 0 }}>
              <div className="card-header">
                <h2 className="card-title">文件</h2>
                <span className="hint">owner={principal.principalId}</span>
              </div>
              <div className="card-body tight">
                <table className="data">
                  <thead>
                    <tr>
                      <th>名称</th>
                      <th>类型</th>
                      <th>大小</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {(dir?.files || []).map((f) => (
                      <tr key={f.artifact_id}>
                        <td>{f.name}</td>
                        <td>{f.media_type}</td>
                        <td>{f.size_bytes}</td>
                        <td className="actions">
                          <button
                            className="btn btn-sm"
                            onClick={async () => {
                              try {
                                const meta = await api.get<{ logical_path: string }>(
                                  `/api/v1/me/artifacts/${f.artifact_id}`,
                                  principal,
                                );
                                setPreview(meta.logical_path);
                              } catch (e) {
                                toast(e instanceof Error ? e.message : String(e), "danger");
                              }
                            }}
                          >
                            预览元数据
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {preview ? <div className="card-body mono">logical_path: {preview}</div> : null}
              </div>
            </div>
          </div>
        </div>
      </div>

      {!userOnly ? (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="card-header">
            <h2 className="card-title">管理元数据 / 提权</h2>
          </div>
          <div className="card-body">
            <table className="data">
              <thead>
                <tr>
                  <th>Owner</th>
                  <th>路径</th>
                  <th>大小</th>
                </tr>
              </thead>
              <tbody>
                {adminItems.map((a) => (
                  <tr key={a.artifact_id}>
                    <td className="mono">{a.owner_principal_id}</td>
                    <td className="mono">{a.logical_path}</td>
                    <td>{a.size_bytes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="form-grid" style={{ marginTop: 12 }}>
              <div className="form-field">
                <label>Owner Principal</label>
                <input
                  value={elevateOwner}
                  onChange={(e) => setElevateOwner(e.target.value)}
                  placeholder="u_alice"
                />
              </div>
              <div className="form-field">
                <label>原因（必填）</label>
                <input
                  value={elevateReason}
                  onChange={(e) => setElevateReason(e.target.value)}
                  placeholder="INC-101"
                />
              </div>
            </div>
            <div style={{ marginTop: 12 }}>
              <button className="btn" onClick={elevate} disabled={!elevateOwner || !elevateReason}>
                申请提权读取
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </PageShell>
  );
}
