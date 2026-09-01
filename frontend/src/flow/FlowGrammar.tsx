import { Background, Controls, Handle, NodeProps, Position, ReactFlow, ReactFlowProvider, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

type FlowKind = "input" | "model" | "operator" | "output" | "evidence";
function CanvasNode({ data, selected }: NodeProps<Node<{ label: string; kind: FlowKind; state?: string }>>) {
  return <div className={`flow-node flow-${data.kind} ${data.state ?? ""} ${selected ? "selected" : ""}`} tabIndex={0} aria-label={`${data.kind} node: ${data.label}`}>
    <Handle type="target" position={Position.Left} /><span className="flow-node-marker" aria-hidden="true" />
    <div><small>{data.kind}</small><strong>{data.label}</strong></div><Handle type="source" position={Position.Right} />
  </div>;
}
const nodeTypes = { ruflex: CanvasNode };
const nodes: Node[] = [
  { id: "data", type: "ruflex", position: { x: 0, y: 64 }, data: { label: "Input data", kind: "input" } },
  { id: "model", type: "ruflex", position: { x: 185, y: 64 }, data: { label: "FIS model", kind: "model", state: "selected" } },
  { id: "operator", type: "ruflex", position: { x: 370, y: 64 }, data: { label: "Aggregation", kind: "operator", state: "running" } },
  { id: "output", type: "ruflex", position: { x: 555, y: 64 }, data: { label: "Output", kind: "output" } },
  { id: "evidence", type: "ruflex", position: { x: 370, y: 175 }, data: { label: "Check pending", kind: "evidence", state: "warning" } },
];
const edges: Edge[] = [
  { id: "data-model", source: "data", target: "model", className: "edge-data" }, { id: "model-operator", source: "model", target: "operator", className: "edge-data" }, { id: "operator-output", source: "operator", target: "output", className: "edge-data" }, { id: "operator-evidence", source: "operator", target: "evidence", className: "edge-evidence", animated: true },
];
export function FlowGrammar() { return <div className="flow-grammar" aria-label="RuFLEX workflow canvas"><ReactFlowProvider><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView nodesDraggable={false} nodesConnectable={false} elementsSelectable><Background gap={16} size={1} /><Controls showInteractive={false} /></ReactFlow></ReactFlowProvider></div>; }
