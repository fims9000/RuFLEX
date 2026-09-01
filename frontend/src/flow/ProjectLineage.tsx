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
import type { LineageGraph, LineageNode } from "../api";

function LineageCanvasNode({ data, selected }: NodeProps<Node<{ node: LineageNode }>>) {
  const item = data.node;
  return (
    <div
      className={`lineage-node lineage-${item.kind} ${selected ? "selected" : ""}`}
      aria-label={`${item.kind}: ${item.label}`}
      title={item.detail ?? item.label}
    >
      <Handle type="target" position={Position.Left} />
      <small>{item.kind.replaceAll("_", " ")}</small>
      <strong>{item.label}</strong>
      {item.detail && <span>{item.detail}</span>}
      {item.status && <em>{item.status}</em>}
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
  onOpen,
}: {
  graph: LineageGraph | null;
  onOpen: (node: LineageNode) => void;
}) {
  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="lineage-empty">
        Lineage will appear as persisted datasets, runs, analyses and evidence are created.
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
      position: { x, y: ordinal * 128 },
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
    <div className="project-lineage" aria-label="Project lineage graph">
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          nodesDraggable={false}
          nodesConnectable={false}
          onNodeClick={(_, node) => {
            const item = (node.data as { node: LineageNode }).node;
            onOpen(item);
          }}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={18} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}
