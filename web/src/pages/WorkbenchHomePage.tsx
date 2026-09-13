import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useApp } from "../App";
import { PageShell } from "../components/PageShell";

interface MyIdentity {
  definition_id: string;
  key: string;
  name: string;
  description: string | null;
  identity_version_id: string;
  version: string;
}

export function WorkbenchHomePage() {
  const { principal, toast } = useApp();
  const navigate = useNavigate();
  const [items, setItems] = useState<MyIdentity[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api.get<MyIdentity[]>("/api/v1/me/identities", principal);
        if (!cancelled) setItems(data);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [principal]);

  async function startSession(identityVersionId: string) {
    try {
      await api.post(`/api/v1/me/identities/${identityVersionId}/sessions`, principal, {});
      toast("会话已创建", "success");
      navigate("/app/chat");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "danger");
    }
  }

  return (
    <PageShell
      crumb="用户工作台 / 我的智能体"
      title="我的智能体"
      desc="仅显示 IdentityGrant 授权给你的已发布智能体"
    >
      {error ? <div className="error-box">{error}</div> : null}
      {items.length === 0 && !error ? (
        <div className="card">
          <div className="empty">
            <div className="empty-title">暂无授权智能体</div>
            请管理员发布 IdentityVersion 并创建 Grant
          </div>
        </div>
      ) : (
        <div className="agent-cards">
          {items.map((a) => (
            <article key={a.identity_version_id} className="card agent-card">
              <h3>{a.name}</h3>
              <p>{a.description || a.key}</p>
              <div style={{ marginTop: 12, display: "flex", justifyContent: "space-between" }}>
                <span className="hint">{a.version}</span>
                <button
                  className="btn btn-sm btn-primary"
                  onClick={() => startSession(a.identity_version_id)}
                >
                  开始会话
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </PageShell>
  );
}
