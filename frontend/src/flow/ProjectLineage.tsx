import {
  Background,
  Controls,
  Handle,
  NodeProps,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useState } from "react";
import type { LineageGraph, LineageNode } from "../api";
import { Button } from "../components/StudioPrimitives";
import { ui, uiLanguage, uiStatus } from "../design/language";

const kindNames: Record<string, string> = { project: "Проект", dataset: "Данные", training_run: "Обученная модель", study: "Эксперимент", evaluation: "Оценка на проверочных данных", explanation: "Объяснение", explanation_check: "Проверка объяснения", decision_threshold: "Порог решения", calibration: "Калибровка", selective_policy: "Правило проверки", final_test_evaluation: "Итоговый тест", study_stability: "Устойчивость модели", stability_gate_policy: "Правило устойчивости", fis: "Нечёткая модель", fis_revision: "Версия нечёткой модели", behavior_spec: "Требование", behavior_spec_result: "Результат требования", behavior_revision_comparison: "Сравнение версий", transform_pipeline: "Подготовка данных", preprocessing: "Преобразование признаков", leakage_audit: "Проверка разделения данных", split_contract: "Разбиение данных", tree_path: "Путь дерева", assurance_case: "Сводка проверок", verification_bundle: "Архив результатов" };
function kindLabel(kind: string) { return ui(kind.replaceAll("_", " "), kindNames[kind] ?? "Сохранённый объект"); }
function objectLabel(item: LineageNode) {
  const models: Record<string, string> = { flat_neuro_fuzzy: "Нейро-нечёткая модель", logistic_regression: "Логистическая регрессия", linear_regression: "Линейная регрессия", decision_tree: "Дерево решений", random_forest: "Случайный лес", gradient_boosting: "Градиентный бустинг", mlp: "Нейросеть MLP" };
  const model = Object.entries(models).find(([key]) => item.label.includes(key));
  return ui(item.label, model ? `${kindLabel(item.kind)}: ${model[1]}` : kindLabel(item.kind));
}

function LineageCanvasNode({ data, selected }: NodeProps<Node<{ node: LineageNode }>>) {
  const item = data.node;
  return (
    <div
      className={`lineage-node lineage-${item.kind} ${selected ? "selected" : ""}`}
      aria-label={`${item.kind}: ${item.label}`}
      title={item.detail ?? item.label}
    >
      <Handle type="target" position={Position.Left} />
      <small>{kindLabel(item.kind)}</small>
      <strong>{objectLabel(item)}</strong>
      {item.detail && uiLanguage === "en" && <span>{item.detail}</span>}
      {item.status && <em>{uiStatus(item.status)}</em>}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

const nodeTypes = { lineage: LineageCanvasNode };
const targetColumns: Record<LineageNode["target"], number> = {
  PROJECT: 0,
  DATA: 0,
  MODELS: 230,
  STUDIES: 460,
  ANALYSES: 690,
  EVIDENCE: 920,
};

export function ProjectLineage({
  graph,
  status,
  error,
  objectError = null,
  onRetryObject,
  onRetry,
  onOpen,
}: {
  graph: LineageGraph | null;
  status: "idle" | "loading" | "loaded" | "error";
  error: string | null;
  objectError?: string | null;
  onRetryObject?: () => void;
  onRetry: () => void;
  onOpen: (node: LineageNode) => void;
}) {
  const [view, setView] = useState<"list" | "graph">(uiLanguage === "ru" ? "list" : "graph");
  const [metadata, setMetadata] = useState<LineageNode | null>(null);
  const openObject = (item: LineageNode) => {
    if (["project", "preprocessing"].includes(item.kind)) setMetadata(item);
    else { setMetadata(null); onOpen(item); }
  };
  if (status === "loading" || status === "idle") {
    return <div className="lineage-empty" role="status">{status === "loading" ? ui("Loading persisted project lineage…", "Загрузка связей проекта…") : ui("Project lineage has not been checked yet.", "Связи проекта ещё не проверены.")}</div>;
  }
  if (status === "error") {
    return <div className="error" role="alert"><strong>{ui("Could not load persisted project lineage.", "Не удалось загрузить связи проекта.")}</strong><p>{error ?? ui("No empty lineage state is inferred from this failure.", "Состояние связей неизвестно.")}</p><Button view="outlined" onClick={onRetry}>{ui("Retry lineage", "Повторить")}</Button></div>;
  }
  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="lineage-empty">
        {ui("Lineage will appear as persisted datasets, runs, analyses and evidence are created.", "Здесь появятся связи после сохранения данных, моделей и результатов.")}
      </div>
    );
  }

  const counters = new Map<number, number>();
  const nodes: Node<{ node: LineageNode }>[] = graph.nodes.map((item) => {
    const x = targetColumns[item.target];
    const ordinal = counters.get(x) ?? 0;
    counters.set(x, ordinal + 1);
    return {
      id: item.id,
      type: "lineage",
      position: { x, y: ordinal * 210 },
      data: { node: item },
      draggable: false,
    };
  });
  const edges: Edge[] = graph.edges.map((edge, index) => ({
    id: `${edge.source}-${edge.target}-${index}`,
    source: edge.source,
    target: edge.target,
    label: edge.relation.replaceAll("_", " "),
    className: "lineage-edge",
  }));

  return (
    <div>
      <div className="form-actions"><Button view={view === "list" ? "action" : "outlined"} onClick={() => setView("list")}>{ui("Object list", "Список объектов")}</Button><Button view={view === "graph" ? "action" : "outlined"} onClick={() => setView("graph")}>{ui("Relationship graph", "Граф связей")}</Button><small>{graph.nodes.length} {ui("saved objects", "сохранённых объектов")}</small></div>
      {objectError && <div className="error" role="alert" data-testid="lineage-object-load-error"><strong>{ui("Could not reopen the selected saved object.", "Не удалось открыть выбранный объект.")}</strong><p>{objectError}</p>{onRetryObject && <Button view="outlined" onClick={onRetryObject}>{ui("Retry selected object", "Повторить")}</Button>}</div>}
      {metadata && graph.nodes.some((item) => item.id === metadata.id) && <div className="trace-card" data-testid="lineage-metadata"><strong>{objectLabel(metadata)}</strong><p>{ui("Metadata from the saved relationship graph; no model artifact is executed.", "Сведения из сохранённой схемы связей. Модель не запускается.")}</p><details open={uiLanguage === "en"}><summary>{ui("Technical details", "Технические сведения")}</summary><p>{metadata.label}</p><p>{metadata.detail}</p><code>{metadata.object_id}</code></details></div>}
      {view === "list" ? <div className="lineage-object-list" data-testid="lineage-object-list">{graph.nodes.map((item, index) => <div key={item.id}><button type="button" data-lineage-object-id={item.object_id ?? item.id} onClick={() => openObject(item)}><strong>{objectLabel(item)} · {index + 1}</strong>{item.status && <span>{uiStatus(item.status)}</span>}</button><details><summary>{ui("Object details", "Сведения об объекте")}</summary><p>{item.label}</p><p>{item.detail}</p><code>{item.object_id}</code></details></div>)}</div> : <div className="project-lineage" aria-label={ui("Project lineage graph", "Граф связей проекта")}>
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.03}
          fitViewOptions={{ padding: .15, minZoom: .03, maxZoom: 1 }}
          nodesDraggable={false}
          nodesConnectable={false}
          onNodeClick={(_, node) => {
            const item = (node.data as { node: LineageNode }).node;
            openObject(item);
          }}
        >
          <Background gap={18} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </ReactFlowProvider>
      </div>}
    </div>
  );
}
