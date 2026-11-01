import { expect, it } from "vitest";
import { probabilityBins } from "./PredictionDistribution";
import type { TrainingRun } from "../../api";

it("counts raw probabilities by true class, including exactly zero and one", () => {
  const rows = [{ target: 0, probability: 0 }, { target: 1, probability: 1 }, { target: 1, probability: .51 }] as TrainingRun["prediction_preview"];
  const result = probabilityBins(rows);
  expect(result.plotted).toBe(3);
  expect(result.counts[0][0]).toBe(1);
  expect(result.counts[1][9]).toBe(1);
  expect(result.counts[1][5]).toBe(1);
});
it("does not silently plot missing/invalid probabilities or nonbinary truth", () => {
  const rows = [{ target: 0, probability: null }, { target: 0, probability: NaN }, { target: 0, probability: 2 }, { target: 2, probability: .5 }] as TrainingRun["prediction_preview"];
  const result = probabilityBins(rows);
  expect(result.plotted).toBe(0);
  expect(result.counts.flat().reduce((a, b) => a + b, 0)).toBe(0);
});
