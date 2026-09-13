import { useEffect, useState } from "react";
import { useApp } from "../App";
import { PageShell } from "../components/PageShell";

interface RunLegacy {
  run_id: string;
  status: string;
  pending_approval?: { tool_id?: string } | null;
}

export function ApprovalsPage() {
  const { principal, toast } = useApp();
  const [items, setItems] = useState<RunLegacy[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/runs");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const all = (await res.json()) as RunLegacy[];
        if (cancelled) return;
        setItems(all.filter((r) => r.status === "waiting_approval" || r.pending_approval));
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [principal]);

  async function decide(runId: string, approve: boolean) {
    try {
      const res = await fetch(`/runs/${runId}/resume`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(approve ? { approve: true } : { reject: true }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      toast(approve ? "已批准并恢复" : "已处理", "success");
      setItems((prev) => prev.filter((r) => r.run_id !== runId));
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "danger");
    }
  }

  return (
    <PageShell crumb="管理控制台 / 审批" title="审批" desc="waiting_approval 队列">
      {error ? <div className="error-box">{error}</div> : null}
      <div className="card">
        <div className="card-body tight">
          {items.length === 0 && !error ? (
            <div className="empty">
              <div className="empty-title">审批队列为空</div>
              Tool policy=ask 时会出现在这里
            </div>
          ) : (
            <table className="data">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>工具</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.run_id}>
                    <td className="mono">{r.run_id.slice(0, 12)}…</td>
                    <td>{r.pending_approval?.tool_id || "—"}</td>
                    <td className="actions">
                      <button
                        className="btn btn-sm btn-primary"
                        onClick={() => decide(r.run_id, true)}
                      >
                        批准
                      </button>
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={() => decide(r.run_id, false)}
                      >
                        拒绝
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
