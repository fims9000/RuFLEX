import type { BehaviorSpec, BehaviorSpecResult, FISTrace } from "../../api";
import { ui } from "../../design/language";

function traceLabel(key: string, spec: BehaviorSpec): string {
  if (key === "primary") return ui("Primary input", "Исходный пример");
  if (key === "comparison") return ui("Comparison input", "Пример для сравнения");
  if (key.startsWith("case:")) return `${ui("Case", "Пример")} ${spec.cases?.[Number(key.slice(5))]?.name ?? key.slice(5)}`;
  return key;
}

function TraceDetails({ label, trace }: { label: string; trace: FISTrace }) {
  return <details data-testid="behavior-exact-trace"><summary>{label} · {ui("exact FIS computation · output", "точный нечёткий расчёт · выход")} {trace.final_output}</summary>
    <p>FIS revision {trace.semantic_hash} · reconstruction error {trace.reconstruction_error}</p>
    <div className="data-table-wrap"><table className="data-table"><thead><tr><th>{ui("input", "Вход")}</th><th>{ui("value", "Значение")}</th><th>{ui("memberships", "Степени принадлежности")}</th></tr></thead><tbody>{trace.memberships.map((item) => <tr key={item.variable}><td>{item.variable}</td><td>{item.value}</td><td>{Object.entries(item.memberships).map(([term, value]) => `${term}: ${value.toFixed(6)}`).join(" · ")}</td></tr>)}</tbody></table></div>
    <div className="data-table-wrap"><table className="data-table"><thead><tr><th>{ui("rule", "Правило")}</th><th>{ui("firing strength", "Сила срабатывания")}</th><th>{ui("weighted firing", "С учётом веса")}</th><th>{ui("consequent", "Заключение")}</th></tr></thead><tbody>{trace.rules.map((rule) => <tr key={rule.rule_id}><td>{rule.name}</td><td>{rule.firing_strength.toFixed(6)}</td><td>{rule.weighted_firing_strength.toFixed(6)}</td><td>{rule.consequent_value ?? rule.output_term}</td></tr>)}</tbody></table></div>
    <p className="property-description">{ui("Exact fuzzy execution evidence for this saved requirement and input; it is not a causal explanation.", "Точный расчёт для сохранённого требования и примера. Это не доказательство причинной связи.")}</p>
  </details>;
}

export function BehaviorExactTrace({ spec, result }: { spec: BehaviorSpec; result: BehaviorSpecResult }) {
  if (spec.spec_id !== result.spec_id || !result.fis_id) return null;
  const entries = Object.entries(result.exact_fis_traces ?? {}).sort(([left], [right]) => left.localeCompare(right));
  if (!entries.length) return <p className="property-description" data-testid="behavior-legacy-trace">{ui("This saved legacy BehaviorSpec result has no persisted exact FIS trace.", "В старом результате не сохранён точный нечёткий расчёт.")}</p>;
  return <div className="trace-card" data-testid="behavior-exact-traces"><strong>{ui(`Persisted exact FIS trace${entries.length === 1 ? "" : "s"}`, "Точный расчёт нечёткой модели")}</strong>{entries.map(([key, trace]) => <TraceDetails key={key} label={traceLabel(key, spec)} trace={trace} />)}</div>;
}
