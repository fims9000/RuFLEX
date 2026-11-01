import { ReactNode, useEffect } from "react";
import { ChartBar, Cube, Database, Flask, House, ShieldCheck } from "@gravity-ui/icons";
import { StudioTheme } from "../design/tokens";
import { ui } from "../design/language";
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
  saving?: boolean;
  saveDisabled?: boolean;
  closeDisabled?: boolean;
};
const workbenches = ["PROJECT", "DATA", "MODELS", "STUDIES", "ANALYSES", "EVIDENCE"] as const;
const workbenchIcons = { PROJECT: House, DATA: Database, MODELS: Cube, STUDIES: Flask, ANALYSES: ChartBar, EVIDENCE: ShieldCheck };
const workbenchLabels = { PROJECT: "Проект", DATA: "Данные", MODELS: "Модели", STUDIES: "Обучение", ANALYSES: "Анализ", EVIDENCE: "Доказательства" };
const workbenchRailLabels = { ...workbenchLabels, EVIDENCE: "Проверки" };
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
  saving = false,
  saveDisabled = false,
  closeDisabled = false,
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
          <span className="version">V1.3 Alpha</span>
        </div>
        <div className="project-identity">
          {projectName ? (
            <>
              {ui("PROJECT", "ПРОЕКТ")} <strong>{projectName}</strong>
              {readOnly && <StatusBadge tone="warning">{ui("Read only", "Только чтение")}</StatusBadge>}
            </>
          ) : (
            ui("No project open", "Проект не открыт")
          )}
        </div>
        <div className="command-actions">
          <button className="tool-button panel-toggle" aria-label={explorerCollapsed ? ui("Show project explorer", "Показать дерево проекта") : ui("Hide project explorer", "Скрыть дерево проекта")} aria-pressed={!explorerCollapsed} onClick={toggleExplorer}>{ui("Tree", "Дерево")}</button>
          <button className="tool-button panel-toggle" aria-label={inspectorCollapsed ? ui("Show properties", "Показать свойства") : ui("Hide properties", "Скрыть свойства")} aria-pressed={!inspectorCollapsed} onClick={toggleInspector}>{ui("Details", "Свойства")}</button>
          <button className="tool-button panel-toggle" aria-label={bottomCollapsed ? ui("Show jobs panel", "Показать задачи") : ui("Hide jobs panel", "Скрыть задачи")} aria-pressed={!bottomCollapsed} onClick={toggleBottom}>{ui("Jobs", "Задачи")}</button>
          <button
            className="icon-button"
            aria-label={ui("Toggle theme", "Сменить тему")}
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
          >
            {theme === "light" ? "◐" : "◑"}
          </button>
          {projectName && (
            <button
              className="tool-button"
              disabled={readOnly || saveDisabled}
              onClick={onSave}
            >
              {saving ? ui("Saving…", "Сохранение…") : ui("Save", "Сохранить")}
            </button>
          )}
          {projectName && (
            <button className="tool-button" disabled={closeDisabled} onClick={onClose}>
              {ui("Close", "Закрыть")}
            </button>
          )}
        </div>
      </header>
      <nav className="activity-rail" aria-label={ui("Workbench navigation", "Разделы Studio")}>
        {workbenches.map((section) => {
          const Icon = workbenchIcons[section];
          return (
            <button
              key={section}
              className={active === section ? "active" : ""}
              onClick={() => setActive(section)}
              title={ui(section, workbenchLabels[section])}
              aria-label={ui(section.slice(0, 1), workbenchLabels[section])}
              aria-description={ui(`Open ${section.toLowerCase()} workspace`, `Открыть раздел «${workbenchLabels[section]}»`)}
              aria-current={active === section ? "page" : undefined}
            >
              <Icon className="rail-icon" aria-hidden="true" />
              <span className="rail-label" aria-hidden="true">{ui(section.slice(0, 1) + section.slice(1).toLowerCase(), workbenchRailLabels[section])}</span>
            </button>
          );
        })}
      </nav>
      <aside className="tool-window explorer">
        <PanelHeader
          title={ui("PROJECT EXPLORER", "ДЕРЕВО ПРОЕКТА")}
          actions={
            <button
              className="icon-button"
              aria-label={ui("Collapse explorer", "Свернуть дерево проекта")}
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
          title={ui("PROPERTIES", "СВОЙСТВА")}
          actions={
            <button
              className="icon-button"
              aria-label={ui("Collapse properties", "Свернуть свойства")}
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
          title={ui("JOBS & PROBLEMS", "ЗАДАЧИ И ПРОБЛЕМЫ")}
          detail={ui("local worker", "локальное выполнение")}
          actions={
            <button
              className="icon-button"
              aria-label={ui("Collapse jobs panel", "Свернуть задачи")}
              onClick={toggleBottom}
            >
              ⌄
            </button>
          }
        />
        <div className="bottom-body" role={error ? "alert" : "status"}>
          {error ?? ui("No active jobs", "Нет активных задач")}
        </div>
      </section>
      <footer className="status-strip">
        <span>{status}</span>
        <span className="status-spacer" />
      </footer>
    </main>
  );
}
