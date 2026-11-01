import type { AnalysisEvaluation, TrainingRun } from "../../api";
import type { StudioTheme } from "../../design/tokens";
import { ChartSurface } from "../../charts/ChartSurface";
import { ui } from "../../design/language";

export function probabilityBins(rows: TrainingRun["prediction_preview"]) {
  const counts = [Array(10).fill(0), Array(10).fill(0)];
  let plotted = 0;
  for (const row of rows) {
    const p = row.probability;
    if (p === null || p === undefined || !Number.isFinite(p) || p < 0 || p > 1 || ![0, 1].includes(row.target)) continue;
    counts[row.target][Math.min(9, Math.floor(p * 10))] += 1;
    plotted++;
  }
  return { counts, plotted };
}

export function PredictionDistribution({ run, evaluation, theme }: { run: TrainingRun; evaluation: AnalysisEvaluation | null; theme: StudioTheme }) {
  const rows = evaluation?.prediction_preview ?? run.prediction_preview;
  if (!rows.length) return null;
  const classification = run.task === "binary_classification";
  const { counts, plotted } = probabilityBins(rows);
  return <section data-testid="prediction-distribution"><ChartSurface theme={theme}
    title={classification ? ui("Probability distribution by true class", "Вероятности по известным классам") : ui("Actual and predicted values", "Фактические значения и прогноз")}
    option={classification ? {
      tooltip: { trigger: "axis" }, legend: { data: ["Класс 0", "Класс 1"] },
      grid: { left: 50, right: 20, bottom: 48, top: 40 },
      xAxis: { type: "category", name: "Вероятность", nameLocation: "middle", nameGap: 30, data: Array.from({ length: 10 }, (_, i) => `${(i / 10).toFixed(1)}–${((i + 1) / 10).toFixed(1)}`) },
      yAxis: { type: "value", name: "Примеры", minInterval: 1 },
      series: counts.map((data, i) => ({ type: "bar", name: `Класс ${i}`, data })),
    } : {
      tooltip: { trigger: "item" }, grid: { left: 60, right: 25, bottom: 48, top: 30 },
      xAxis: { type: "value", name: "Фактическое значение", nameLocation: "middle", nameGap: 30 },
      yAxis: { type: "value", name: "Прогноз" },
      series: [{ type: "scatter", symbolSize: 8, data: rows.map((row) => [row.target, row.prediction]) }],
    }} />
    <p>{classification ? `${plotted} примеров с сохранённой вероятностью.` : `${rows.length} сохранённых прогнозов.`} {evaluation ? "Проверочная выборка; финальный тест здесь не используется." : "Предпросмотр запуска. Сохраните оценку для просмотра всей проверочной выборки."}</p>
  </section>;
}
