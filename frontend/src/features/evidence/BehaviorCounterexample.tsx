import type { BehaviorSpec, BehaviorSpecResult } from "../../api";

function expectedCondition(spec: BehaviorSpec, minimum = spec.minimum, maximum = spec.maximum): string {
  switch (spec.kind) {
    case "monotonic_pair":
    case "required_order": return `${spec.expected_direction ?? "declared order"} within tolerance ${spec.tolerance}`;
    case "invariance_pair":
    case "symmetry_pair":
    case "categorical_invariance": return `outputs differ by no more than ${spec.tolerance}`;
    case "bounded_perturbation": return `output difference at most ${spec.maximum_delta} plus tolerance ${spec.tolerance}`;
    case "forbidden_region": return `output outside [${minimum}, ${maximum}] with tolerance ${spec.tolerance}`;
    default: return `output in [${minimum ?? "−∞"}, ${maximum ?? "+∞"}] with tolerance ${spec.tolerance}`;
  }
}

function SampleValues({ sample, label }: { sample: Record<string, number>; label: string }) {
  return <div><strong>{label}</strong><div className="data-table-wrap"><table className="data-table"><thead><tr><th>feature</th><th>value</th></tr></thead><tbody>{Object.entries(sample).sort(([a], [b]) => a.localeCompare(b)).map(([feature, value]) => <tr key={feature}><td>{feature}</td><td>{value}</td></tr>)}</tbody></table></div></div>;
}

export function BehaviorCounterexample({ spec, result }: { spec: BehaviorSpec; result: BehaviorSpecResult }) {
  if (result.status !== "FAIL" || result.spec_id !== spec.spec_id) return null;
  const failedCases = spec.kind === "batch_regression_suite"
    ? (result.observations ?? []).filter((item) => item.status === "FAIL").map((item) => ({ observation: item, case: spec.cases?.find((candidate) => candidate.name === item.name) }))
    : [];
  return <div className="trace-card" data-testid="behavior-counterexample">
    <div className="evidence-check-header"><strong>Actionable counterexample</strong><span>Persisted BehaviorSpec failure</span></div>
    <p>Expected: {spec.kind === "batch_regression_suite" ? "each named case satisfies its declared output range" : expectedCondition(spec)}</p>
    {spec.kind === "batch_regression_suite" ? failedCases.map(({ observation, case: failedCase }) => <div key={observation.name}>
      <p><strong>{observation.name}</strong> · expected {expectedCondition(spec, failedCase?.minimum, failedCase?.maximum)} · observed {observation.output}</p>
      {failedCase && <SampleValues sample={failedCase.sample} label="Failed case input" />}
    </div>) : <>
      <p>Observed output: {result.observed_output}{result.comparison_output !== null ? ` → ${result.comparison_output}` : ""}</p>
      <SampleValues sample={spec.sample} label="Input" />
      {spec.comparison_sample && <SampleValues sample={spec.comparison_sample} label="Comparison input" />}
    </>}
    <small>{result.run_id ? `TrainingRun ${result.run_id} · model artifact ${result.model_artifact_sha256}` : `FIS ${result.fis_id} · semantic revision ${result.fis_semantic_hash}`}</small>
    <p className="property-description">This reports only the evaluated, revision-bound requirement. No exact computation trace is persisted with this BehaviorSpec result.</p>
  </div>;
}
