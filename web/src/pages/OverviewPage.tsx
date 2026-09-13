import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useApp } from "../App";
import { PageShell } from "../components/PageShell";

interface Tenant {
  tenant_id: string;
  name: string;
}
interface AuditEvent {
  event_id: string;
  action: string;
  target: string;
  created_at: string;
}

export function OverviewPage() {
  const { principal } = useApp();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [audits, setAudits] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const t = await api.get<Tenant[]>("/api/v1/tenants", principal);
        if (!cancelled) setTenants(t);
        const a = await api.get<AuditEvent[]>(
          `/api/v1/tenants/${principal.tenantId}/audit-events`,
          principal,
        );
        if (!cancelled) setAudits(a.slice(0, 5));
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [principal]);

  return (
    <PageShell
      crumb="管理控制台 / 总览"
      title="总览"
      desc={`角色：${principal.label} · 数据来自 engine /api/v1`}
    >
      <div className="grid-metrics">
        <div className="card metric">
          <div className="metric-label">租户</div>
          <div className="metric-value">{tenants.length}</div>
          <div className="metric-hint">当前 Principal 可见</div>
        </div>
        <div className="card metric">
          <div className="metric-label">审计事件</div>
          <div className="metric-value">{audits.length}</div>
          <div className="metric-hint">最近若干条</div>
        </div>
      </div>
      {error ? <div className="error-box">{error}</div> : null}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">最近审计</h2>
          <Link to="/console/settings">设置</Link>
        </div>
        <div className="card-body tight">
          {audits.length === 0 ? (
            <div className="empty">
              <div className="empty-title">暂无审计</div>
              发布 Identity 或提权读取产物后会出现记录
            </div>
          ) : (
            <table className="data">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>动作</th>
                  <th>对象</th>
                </tr>
              </thead>
              <tbody>
                {audits.map((a) => (
                  <tr key={a.event_id}>
                    <td>{new Date(a.created_at).toLocaleString()}</td>
                    <td>{a.action}</td>
                    <td className="mono">{a.target}</td>
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
