import { describe, expect, it } from "vitest";
import { FISEvaluation, FISSpec } from "../../api";
import { exactFisEvaluationMatchesCurrent } from "./exactFisEvaluation";

const spec = { fis_id: "fis-1", semantic_hash: "hash-1" } as FISSpec;
const evaluation = {
  evaluation: {
    trace: {
      fis_id: "fis-1",
      semantic_hash: "hash-1",
      input_values: { temperature: 20, torque: 50 },
    },
  },
} as unknown as FISEvaluation;

describe("exactFisEvaluationMatchesCurrent", () => {
  it("requires the exact model revision and run-input values", () => {
    expect(exactFisEvaluationMatchesCurrent(spec, evaluation, { temperature: "20.0", torque: "50" })).toBe(true);
    expect(exactFisEvaluationMatchesCurrent(spec, evaluation, { temperature: "21", torque: "50" })).toBe(false);
    expect(exactFisEvaluationMatchesCurrent({ ...spec, semantic_hash: null }, evaluation, { temperature: "20", torque: "50" })).toBe(false);
    expect(exactFisEvaluationMatchesCurrent(spec, null, { temperature: "20", torque: "50" })).toBe(false);
  });
});
