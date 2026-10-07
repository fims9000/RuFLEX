import type { BehaviorSpec, BehaviorSpecResult, FISTrace } from "../../api";

function traceLabel(key: string, spec: BehaviorSpec): string {
  if (key === "primary") return "Primary input";
  if (key === "comparison") return "Comparison input";
  if (key.startsWith("case:")) return `Case ${spec.cases?.[Number(key.slice(5))]?.name ?? key.slice(5)}`;
  return key;
}

function TraceDetails({ label, trace }: { label: string; trace: FISTrace }) {
  return <details data-testid="behavior-exact-trace"><summary>{label} · exact FIS computation · output {trace.final_output}</summary>
    <p>FIS revision {trace.semantic_hash} · reconstruction error {trace.reconstruction_error}</p>
    <div className="data-table-wrap"><table className="data-table"><thead><tr><th>input</th><th>value</th><th>memberships</th></tr></thead><tbody>{trace.memberships.map((item) => <tr key={item.variable}><td>{item.variable}</td><td>{item.value}</td><td>{Object.entries(item.memberships).map(([term, value]) => `${term}: ${value.toFixed(6)}`).join(" · ")}</td></tr>)}</tbody></table></div>
    <div className="data-table-wrap"><table className="data-table"><thead><tr><th>rule</th><th>firing strength</th><th>weighted firing</th><th>consequent</th></tr></thead><tbody>{trace.rules.map((rule) => <tr key={rule.rule_id}><td>{rule.name}</td><td>{rule.firing_strength.toFixed(6)}</td><td>{rule.weighted_firing_strength.toFixed(6)}</td><td>{rule.consequent_value ?? rule.output_term}</td></tr>)}</tbody></table></div>
    <p className="property-description">Exact fuzzy execution evidence for this saved requirement and input; it is not a causal explanation.</p>
  </details>;
}

export function BehaviorExactTrace({ spec, result }: { spec: BehaviorSpec; result: BehaviorSpecResult }) {
  if (spec.spec_id !== result.spec_id || !result.fis_id) return null;
  const entries = Object.entries(result.exact_fis_traces ?? {}).sort(([left], [right]) => left.localeCompare(right));
  if (!entries.length) return <p className="property-description" data-testid="behavior-legacy-trace">This saved legacy BehaviorSpec result has no persisted exact FIS trace.</p>;
  return <div className="trace-card" data-testid="behavior-exact-traces"><strong>Persisted exact FIS trace{entries.length === 1 ? "" : "s"}</strong>{entries.map(([key, trace]) => <TraceDetails key={key} label={traceLabel(key, spec)} trace={trace} />)}</div>;
}
