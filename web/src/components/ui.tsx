import type { ReactNode } from "react";

export function Pill({
  tone = "muted",
  children,
}: {
  tone?: "success" | "warning" | "danger" | "info" | "muted";
  children: ReactNode;
}) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

export function StatusPill({ status }: { status: string }) {
  const map: Record<string, { tone: "success" | "warning" | "danger" | "info" | "muted"; label: string }> = {
    published: { tone: "success", label: "已发布" },
    draft: { tone: "warning", label: "草稿" },
    succeeded: { tone: "success", label: "成功" },
    failed: { tone: "danger", label: "失败" },
    running: { tone: "info", label: "运行中" },
    waiting_approval: { tone: "warning", label: "待审批" },
  };
  const hit = map[status] || { tone: "muted" as const, label: status };
  return <Pill tone={hit.tone}>{hit.label}</Pill>;
}

export function ErrorBox({ message }: { message: string | null }) {
  if (!message) return null;
  return <div className="error-box">{message}</div>;
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-title">{title}</div>
      {children}
    </div>
  );
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  emptyTitle,
  emptyHint,
  renderActions,
}: {
  columns: { key: string; title: string; render?: (row: T) => ReactNode }[];
  rows: T[];
  rowKey: (row: T) => string;
  emptyTitle: string;
  emptyHint?: string;
  renderActions?: (row: T) => ReactNode;
}) {
  if (!rows.length) {
    return <EmptyState title={emptyTitle}>{emptyHint}</EmptyState>;
  }
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key}>{c.title}</th>
            ))}
            {renderActions ? <th></th> : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((c) => (
                <td key={c.key}>{c.render ? c.render(row) : String((row as Record<string, unknown>)[c.key] ?? "—")}</td>
              ))}
              {renderActions ? <td className="actions">{renderActions(row)}</td> : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
