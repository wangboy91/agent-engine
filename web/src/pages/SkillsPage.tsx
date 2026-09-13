import { useEffect, useState } from "react";
import { PageShell } from "../components/PageShell";

interface SkillDto {
  id: string;
  name: string;
  description?: string;
}

export function SkillsPage() {
  const [items, setItems] = useState<SkillDto[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/skills");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as SkillDto[];
        if (!cancelled) setItems(data);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <PageShell crumb="管理控制台 / Skill" title="Skill" desc="来自 engine 技能注册表">
      {error ? <div className="error-box">{error}</div> : null}
      <div className="card">
        <div className="card-body tight">
          {items.length === 0 && !error ? (
            <div className="empty">
              <div className="empty-title">暂无 Skill</div>
              先在 engine 注册资源
            </div>
          ) : (
            <table className="data">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>名称</th>
                  <th>描述</th>
                </tr>
              </thead>
              <tbody>
                {items.map((s) => (
                  <tr key={s.id}>
                    <td className="mono">{s.id}</td>
                    <td>{s.name}</td>
                    <td>{s.description || "—"}</td>
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
