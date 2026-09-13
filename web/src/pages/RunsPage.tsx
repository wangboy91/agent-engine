import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useApp } from "../App";
import { PageShell } from "../components/PageShell";
import type { RunResultDto } from "./types";

export function RunsPage() {
  const { principal } = useApp();
  const [runs, setRuns] = useState<RunResultDto[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api.get<RunResultDto[]>("/api/v1/me/runs", principal);
        if (!cancelled) setRuns(data);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [principal]);

  return (
    <PageShell crumb="管理控制台 / Run" title="Run" desc="按 Principal 过滤 /api/v1/me/runs">
      {error ? <div className="error-box">{error}</div> : null}
      <div className="card">
        <div className="card-body tight">
          {runs.length === 0 && !error ? (
            <div className="empty">
              <div className="empty-title">暂无 Run</div>
              通过 CLI 或 /skills/{"{id}"}/runs 产生运行记录
            </div>
          ) : (
            <table className="data">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Skill</th>
                  <th>状态</th>
                  <th>Owner</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => {
                  const owner =
                    (r.context as { owner_principal_id?: string } | null)?.owner_principal_id ||
                    "—";
                  return (
                    <tr key={r.run_id}>
                      <td className="mono">{r.run_id.slice(0, 12)}…</td>
                      <td>{r.skill_id}</td>
                      <td>
                        <span
                          className={`pill ${
                            r.status === "succeeded"
                              ? "pill-success"
                              : r.status === "failed"
                                ? "pill-danger"
                                : "pill-info"
                          }`}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td className="mono">{owner}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </PageShell>
  );
}
