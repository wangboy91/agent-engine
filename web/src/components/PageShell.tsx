import type { ReactNode } from "react";

export function PageShell(props: {
  crumb: string;
  title: string;
  desc?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <>
      <div className="page-header">
        <div>
          <div className="breadcrumb">{props.crumb}</div>
          <h1 className="page-title">{props.title}</h1>
          {props.desc ? <p className="page-desc">{props.desc}</p> : null}
        </div>
        <div className="page-actions">{props.actions}</div>
      </div>
      {props.children}
    </>
  );
}
