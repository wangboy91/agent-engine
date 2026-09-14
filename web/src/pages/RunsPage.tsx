import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useApp } from "../App";
import { PageShell } from "../components/PageShell";
import { DataTable, ErrorBox, StatusPill } from "../components/ui";
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
      <ErrorBox message={error} />
      <div className="card">
        <div className="card-body tight">
          <DataTable
            columns={[
              { key: "run_id", title: "Run", render: (r) => <span className="mono">{r.run_id.slice(0, 12)}…</span> },
              { key: "skill_id", title: "Skill" },
              { key: "status", title: "状态", render: (r) => <StatusPill status={r.status} /> },
              {
                key: "owner",
                title: "Owner",
                render: (r) => (
                  <span className="mono">
                    {(r.context as { owner_principal_id?: string } | null)?.owner_principal_id || "—"}
                  </span>
                ),
              },
            ]}
            rows={runs}
            rowKey={(r) => r.run_id}
            emptyTitle="暂无 Run"
            emptyHint="通过 CLI 或 /skills/{id}/runs 产生运行记录"
          />
        </div>
      </div>
    </PageShell>
  );
}
