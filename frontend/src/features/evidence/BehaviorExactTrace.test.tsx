import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { BehaviorSpec, BehaviorSpecResult, FISTrace } from "../../api";
import { BehaviorExactTrace } from "./BehaviorExactTrace";

const spec: BehaviorSpec = {
  spec_id: "spec-1", run_id: null, model_artifact_sha256: null, fis_id: "fis-1", fis_semantic_hash: "revision-1",
  name: "Requirement", kind: "output_range", sample: { temperature: 25 }, comparison_sample: null,
  minimum: 2, maximum: 3, expected_direction: null, cases: [], tolerance: 1e-9, rationale: "Expected range",
};
const result: BehaviorSpecResult = {
  result_id: "result-1", spec_id: "spec-1", run_id: null, model_artifact_sha256: null, fis_id: "fis-1", fis_semantic_hash: "revision-1",
  status: "FAIL", observed_output: 0.4, comparison_output: null, detail: "Outside expected range",
};
const trace: FISTrace = {
  fis_id: "fis-1", semantic_hash: "revision-1", input_values: { temperature: 25 },
  final_output: 0.4, reconstruction_output: 0.4, reconstruction_error: 0,
  memberships: [{ variable: "temperature", value: 25, memberships: { Low: 0.75 } }],
  rules: [{ rule_id: "rule-1", name: "Rule one", enabled: true, connector: "and", clause_values: {}, firing_strength: 0.75, weight: 0.8, weighted_firing_strength: 0.6, consequent_value: null, output_term: "High" }],
  output_grid: [], aggregated_membership: [], defuzzification: "centroid", output_domain: null,
  centroid_resolution: null, centroid_sampling: null, centroid_dx: null, centroid_sample_count: null, inference_kind: "mamdani",
};

describe("BehaviorExactTrace", () => {
  it("shows a typed exact computation for the matching persisted result", () => {
    render(<BehaviorExactTrace spec={spec} result={{ ...result, exact_fis_traces: { primary: trace } }} />);
    fireEvent.click(screen.getByText("Primary input · exact FIS computation · output 0.4"));
    expect(screen.getByTestId("behavior-exact-traces")).toHaveTextContent("revision-1");
    expect(screen.getByTestId("behavior-exact-trace")).toHaveTextContent("temperature");
    expect(screen.getByTestId("behavior-exact-trace")).toHaveTextContent("Rule one");
    expect(screen.getByTestId("behavior-exact-trace")).toHaveTextContent("not a causal explanation");
  });

  it("labels legacy absence and refuses an unrelated result", () => {
    const { rerender } = render(<BehaviorExactTrace spec={spec} result={result} />);
    expect(screen.getByTestId("behavior-legacy-trace")).toHaveTextContent("no persisted exact FIS trace");
    rerender(<BehaviorExactTrace spec={spec} result={{ ...result, spec_id: "other", exact_fis_traces: { primary: trace } }} />);
    expect(screen.queryByTestId("behavior-exact-traces")).not.toBeInTheDocument();
  });
});
