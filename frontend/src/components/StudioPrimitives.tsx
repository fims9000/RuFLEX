import { Button, TextInput } from "@gravity-ui/uikit";
import { ReactNode } from "react";

export { Button, TextInput };

export function PanelHeader({ title, detail, actions }: { title: string; detail?: string; actions?: ReactNode }) {
  return <div className="panel-header"><strong>{title}</strong>{detail && <span>{detail}</span>}<div className="panel-header-actions">{actions}</div></div>;
}

export function StatusBadge({ tone = "info", children }: { tone?: "info" | "success" | "warning" | "danger"; children: ReactNode }) {
  return <span className={`status-badge status-${tone}`}><span aria-hidden="true">●</span>{children}</span>;
}

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return <div className="empty-state"><strong>{title}</strong><span>{children}</span></div>;
}
