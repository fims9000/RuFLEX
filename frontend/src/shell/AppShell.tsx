import { ReactNode, useEffect } from "react";
import { StudioTheme } from "../design/tokens";
import { PanelHeader, StatusBadge } from "../components/StudioPrimitives";

type Props = {
  children: ReactNode;
  inspector: ReactNode;
  explorer: ReactNode;
  theme: StudioTheme;
  setTheme: (theme: StudioTheme) => void;
  active: string;
  setActive: (section: string) => void;
  explorerCollapsed: boolean;
  toggleExplorer: () => void;
  inspectorCollapsed: boolean;
  toggleInspector: () => void;
  bottomCollapsed: boolean;
  toggleBottom: () => void;
  projectName?: string;
  status: string;
  error?: string | null;
  onSave?: () => void;
  onClose?: () => void;
  readOnly?: boolean;
};
const workbenches = ["PROJECT", "MODELS", "STUDIES", "ANALYSES", "EVIDENCE"];
export function AppShell({
  children,
  inspector,
  explorer,
  theme,
  setTheme,
  active,
  setActive,
  explorerCollapsed,
  toggleExplorer,
  inspectorCollapsed,
  toggleInspector,
  bottomCollapsed,
  toggleBottom,
  projectName,
  status,
  error,
  onSave,
  onClose,
  readOnly,
}: Props) {
  useEffect(() => {
    document.documentElement.dataset.ruflexTheme = theme;
    localStorage.setItem("ruflex.theme", theme);
  }, [theme]);
  return (
    <main
      className={`app-shell ${explorerCollapsed ? "explorer-collapsed" : ""} ${inspectorCollapsed ? "inspector-collapsed" : ""} ${bottomCollapsed ? "bottom-collapsed" : ""}`}
    >
      <header className="command-bar">
        <div className="brand">
          <span className="brand-mark">R</span>
          <strong>RuFLEX Studio</strong>
          <span className="version">P0</span>
        </div>
        <div className="project-identity">
          {projectName ? (
            <>
              PROJECT <strong>{projectName}</strong>
              {readOnly && <StatusBadge tone="warning">Read only</StatusBadge>}
            </>
          ) : (
            "No project open"
          )}
        </div>
        <div className="command-actions">
          <button
            className="icon-button"
            aria-label="Toggle theme"
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
          >
            {theme === "light" ? "◐" : "◑"}
          </button>
          {projectName && (
            <button
              className="tool-button"
              disabled={readOnly}
              onClick={onSave}
            >
              Save
            </button>
          )}
          {projectName && (
            <button className="tool-button" onClick={onClose}>
              Close
            </button>
          )}
        </div>
      </header>
      <nav className="activity-rail" aria-label="Workbench navigation">
        {workbenches.map((section) => (
          <button
            key={section}
            className={active === section ? "active" : ""}
            onClick={() => setActive(section)}
            title={section}
          >
            {section.slice(0, 1)}
          </button>
        ))}
      </nav>
      <aside className="tool-window explorer">
        <PanelHeader
          title="PROJECT EXPLORER"
          actions={
            <button
              className="icon-button"
              aria-label="Collapse explorer"
              onClick={toggleExplorer}
            >
              ‹
            </button>
          }
        />
        <div className="explorer-body">{explorer}</div>
      </aside>
      <section className="workspace">{children}</section>
      <aside className="tool-window inspector">
        <PanelHeader
          title="PROPERTIES"
          actions={
            <button
              className="icon-button"
              aria-label="Collapse properties"
              onClick={toggleInspector}
            >
              ›
            </button>
          }
        />
        <div className="inspector-body">{inspector}</div>
      </aside>
      <section className="tool-window bottom-panel">
        <PanelHeader
          title="JOBS & PROBLEMS"
          detail="local worker"
          actions={
            <button
              className="icon-button"
              aria-label="Collapse jobs panel"
              onClick={toggleBottom}
            >
              ⌄
            </button>
          }
        />
        <div className="bottom-body">
          <StatusBadge tone={error ? "danger" : "success"}>
            {error ? "1 problem" : "No active jobs"}
          </StatusBadge>
          <span>{error ?? "Ready for an evidence-producing action."}</span>
        </div>
      </section>
      <footer className="status-strip">
        <span className="connection-indicator">●</span>
        <span>{status}</span>
        <span>Jobs 0</span>
        <span>Warnings {error ? 1 : 0}</span>
        <span className="status-spacer" />
        <span>Local</span>
      </footer>
    </main>
  );
}
