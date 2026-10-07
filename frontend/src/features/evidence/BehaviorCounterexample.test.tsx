import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { BehaviorSpec, BehaviorSpecResult } from "../../api";
import { BehaviorCounterexample } from "./BehaviorCounterexample";

const spec: BehaviorSpec = {
  spec_id: "spec-1", run_id: "run-1", model_artifact_sha256: "a".repeat(64), fis_id: null, fis_semantic_hash: null,
  name: "Declared range", kind: "output_range", sample: { z: 2, a: 1 }, comparison_sample: null,
  minimum: 2, maximum: 3, expected_direction: null, tolerance: 1e-9, rationale: "Test a declared range",
};
const result: BehaviorSpecResult = {
  result_id: "result-1", spec_id: "spec-1", run_id: "run-1", model_artifact_sha256: "a".repeat(64),
  fis_id: null, fis_semantic_hash: null, status: "FAIL", observed_output: 0.4,
  comparison_output: null, detail: "Output outside declared range.",
};

describe("BehaviorCounterexample", () => {
  it("shows declared inputs, expected condition, actual output and exact binding", () => {
    render(<BehaviorCounterexample spec={spec} result={result} />);
    const card = screen.getByTestId("behavior-counterexample");
    expect(card).toHaveTextContent("Expected: output in [2, 3]");
    expect(card).toHaveTextContent("Observed output: 0.4");
    expect(card).toHaveTextContent("TrainingRun run-1");
    expect(card).toHaveTextContent("model artifact");
    expect(screen.getAllByRole("row").slice(1).map((row) => row.textContent)).toEqual(["a1", "z2"]);
  });

  it("does not attach a result to the wrong or passing requirement", () => {
    const { rerender } = render(<BehaviorCounterexample spec={spec} result={{ ...result, spec_id: "other" }} />);
    expect(screen.queryByTestId("behavior-counterexample")).not.toBeInTheDocument();
    rerender(<BehaviorCounterexample spec={spec} result={{ ...result, status: "PASS" }} />);
    expect(screen.queryByTestId("behavior-counterexample")).not.toBeInTheDocument();
  });

  it("shows the failed case rather than the first case of a batch", () => {
    const batch: BehaviorSpec = {
      ...spec, kind: "batch_regression_suite", sample: { a: 1 }, minimum: null, maximum: null,
      cases: [
        { name: "passes", sample: { a: 1 }, minimum: 0, maximum: 1 },
        { name: "fails", sample: { a: 9 }, minimum: 2, maximum: 3 },
      ],
    };
    render(<BehaviorCounterexample spec={batch} result={{ ...result, observed_output: 0.4, observations: [
      { name: "passes", output: 0.4, status: "PASS", detail: "within range" },
      { name: "fails", output: 0.2, status: "FAIL", detail: "outside range" },
    ] }} />);
    const card = screen.getByTestId("behavior-counterexample");
    expect(card).toHaveTextContent("fails · expected output in [2, 3]");
    expect(card).toHaveTextContent("observed 0.2");
    expect(card).toHaveTextContent("a9");
    expect(card).not.toHaveTextContent("passes · expected");
  });

  it("shows both inputs and outputs for a failed pairwise requirement", () => {
    render(<BehaviorCounterexample spec={{ ...spec, kind: "monotonic_pair", minimum: null, maximum: null, expected_direction: "nondecreasing", comparison_sample: { a: 7, z: 8 } }} result={{ ...result, observed_output: 0.8, comparison_output: 0.2 }} />);
    const card = screen.getByTestId("behavior-counterexample");
    expect(card).toHaveTextContent("Expected: nondecreasing within tolerance");
    expect(card).toHaveTextContent("Observed output: 0.8 → 0.2");
    expect(card).toHaveTextContent("Comparison input");
    expect(card).toHaveTextContent("a7");
  });
});
