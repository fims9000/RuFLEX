import type { BehaviorSpec, BehaviorSpecResult } from "../../api";
import { ui } from "../../design/language";

export function behaviorName(name: string) {
  return name === "Output remains in declared range" ? ui(name, "Выход модели в допустимых пределах") : name;
}

export function behaviorKindLabel(kind: BehaviorSpec["kind"]) {
  const names: Record<BehaviorSpec["kind"], string> = { output_range: "Допустимый диапазон", monotonic_pair: "Направление изменения", invariance_pair: "Неизменность выхода", symmetry_pair: "Симметрия", bounded_perturbation: "Ограниченное изменение", categorical_invariance: "Неизменность при смене категории", forbidden_region: "Запрещённый диапазон", required_order: "Порядок значений", domain_constraint: "Предметное ограничение", regression_case: "Контрольный пример", batch_regression_suite: "Набор контрольных примеров" };
  return ui(kind.replaceAll("_", " "), names[kind]);
}

export function BehaviorResultSummary({ spec, result }: { spec: BehaviorSpec; result: BehaviorSpecResult }) {
  if (result.spec_id !== spec.spec_id) return <p role="alert">{ui("Result belongs to another requirement.", "Результат относится к другому требованию.")}</p>;
  const output = result.observed_output;
  const low = spec.minimum;
  const high = spec.maximum;
  const isRange = spec.kind === "output_range";
  const canPlot = isRange && low !== null && high !== null && high > low && Number.isFinite(output);
  const position = canPlot ? 10 + 80 * Math.max(0, Math.min(1, (output - low) / (high - low))) : 50;
  return <div data-testid="behavior-readable-result" style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr)", gap: 8, width: "100%" }}>
    <p>{ui(`Model output: ${output.toLocaleString(undefined, { maximumFractionDigits: 5 })}.`, `Модель выдала: ${output.toLocaleString("ru-RU", { maximumFractionDigits: 5 })}.`)} {isRange && ui(`Allowed range: ${low ?? "−∞"} to ${high ?? "+∞"}.`, `Допустимые значения: от ${low ?? "−∞"} до ${high ?? "+∞"}.`)} {ui(result.status === "PASS" ? "Requirement satisfied for this input." : "Requirement violated for this input.", result.status === "PASS" ? "На этом примере требование выполнено." : "На этом примере требование нарушено.")}</p>
    {canPlot && <svg viewBox="0 0 100 22" role="img" aria-label={ui(`Output ${output}; allowed range ${low} to ${high}`, `Выход ${output}; допустимый диапазон от ${low} до ${high}`)} style={{ width: "100%", maxWidth: 420, height: 90 }}>
      <line x1="10" x2="90" y1="8" y2="8" stroke="currentColor" strokeWidth=".6" />
      <line x1="10" x2="10" y1="6" y2="10" stroke="currentColor" strokeWidth=".6" />
      <line x1="90" x2="90" y1="6" y2="10" stroke="currentColor" strokeWidth=".6" />
      <circle cx={position} cy="8" r="1.6" fill={result.status === "PASS" ? "#225cb6" : "#b83232"} />
      <text x="10" y="16" fontSize="3.6" textAnchor="middle" fill="currentColor">{low}</text>
      <text x="90" y="16" fontSize="3.6" textAnchor="middle" fill="currentColor">{high}</text>
    </svg>}
    <small>{ui("This checks one declared input, not the model's behavior on all possible data.", "Проверен один заданный пример, а не поведение модели на любых данных.")}</small>
    <details><summary>{ui("Technical result", "Технический результат")}</summary><p>{result.detail}</p><code>{result.run_id ?? result.fis_semantic_hash}</code></details>
  </div>;
}
