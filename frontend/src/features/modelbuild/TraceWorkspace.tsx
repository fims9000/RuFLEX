import { FISEvaluation, TreePathEvidence } from "../../api";
import { ChartSurface } from "../../charts/ChartSurface";
import { EmptyState, StatusBadge } from "../../components/StudioPrimitives";
import { StudioTheme } from "../../design/tokens";

export function TraceWorkspace({
  evaluation,
  previousEvaluation,
  treeEvidence,
  theme,
}: {
  evaluation: FISEvaluation | null;
  previousEvaluation: FISEvaluation | null;
  treeEvidence: TreePathEvidence | null;
  theme: StudioTheme;
}) {
  if (!evaluation && !treeEvidence)
    return (
      <section className="feature-workspace">
        <EmptyState title="No exact trace yet">
          Run the active FIS in Build to inspect its actual computation path.
        </EmptyState>
      </section>
    );
  if (!evaluation && treeEvidence) return <section className="feature-workspace trace-workspace"><div className="feature-toolbar"><div><span className="eyebrow">EXACT TREE EXECUTION PATH</span><h2>Leaf {treeEvidence.leaf_id} → {treeEvidence.prediction.toFixed(5)}</h2><p>This is the exact structural path executed by the persisted Decision Tree. It is not SHAP or a post-hoc attribution.</p></div><StatusBadge tone="success">exact structural evidence</StatusBadge></div><section className="trace-card"><strong>Input sample</strong>{Object.entries(treeEvidence.input_sample).map(([name, value]) => <div key={name}><span>{name}</span><code>{value.toFixed(6)}</code></div>)}</section><section className="trace-card"><strong>Execution nodes</strong>{treeEvidence.steps.map((step) => <div key={step.node_id}><span>Node {step.node_id}: {step.feature_name} ≤ {step.threshold.toFixed(6)}</span><code>{step.value.toFixed(6)} → {step.decision.toUpperCase()}</code></div>)}<div><span>Leaf {treeEvidence.leaf_id}</span><code>prediction {treeEvidence.prediction.toFixed(6)}</code></div></section>{treeEvidence.class_probabilities && <section className="trace-card"><strong>Class probabilities</strong>{Object.entries(treeEvidence.class_probabilities).map(([name, value]) => <div key={name}><span>{name}</span><code>{value.toFixed(6)}</code></div>)}</section>}</section>;
  const trace = evaluation!.evaluation.trace;
  const previousTrace = previousEvaluation?.evaluation.trace ?? null;
  const membershipChanges = previousTrace ? trace.memberships.flatMap((item) => {
    const before = previousTrace.memberships.find((candidate) => candidate.variable === item.variable);
    return Object.entries(item.memberships).flatMap(([term, value]) => {
      const prior = before?.memberships[term];
      return prior === undefined || Math.abs(prior - value) < 1e-9 ? [] : [{ label: `${item.variable}.${term}`, before: prior, after: value }];
    });
  }) : [];
  const firingChanges = previousTrace ? trace.rules.flatMap((rule) => {
    const prior = previousTrace.rules.find((candidate) => candidate.rule_id === rule.rule_id);
    return !prior || Math.abs(prior.weighted_firing_strength - rule.weighted_firing_strength) < 1e-9 ? [] : [{ label: rule.name, before: prior.weighted_firing_strength, after: rule.weighted_firing_strength }];
  }) : [];
  const outputOption = {
    grid: { left: 42, right: 16, top: 18, bottom: 28 },
    xAxis: { type: "value" as const },
    yAxis: { type: "value" as const, min: 0, max: 1 },
    series: [
      {
        type: "line" as const,
        showSymbol: false,
        areaStyle: {},
        data: trace.output_grid.map((x, index) => [
          x,
          trace.aggregated_membership[index],
        ]),
      },
    ],
  };
  return (
    <section className="feature-workspace trace-workspace">
      <div className="feature-toolbar">
        <div>
          <span className="eyebrow">E4 · EXACT COMPUTATIONAL TRACE</span>
          <h2>
            {evaluation!.evaluation.output_name}:{" "}
            {evaluation!.evaluation.output.toFixed(5)}
          </h2>
          <p>
            This view reports the actual fuzzy computation. It is not a causal
            explanation or post-hoc attribution.
          </p>
        </div>
        <StatusBadge
          tone={trace.reconstruction_error < 1e-10 ? "success" : "danger"}
        >
          Reconstruction {trace.reconstruction_error.toExponential(2)}
        </StatusBadge>
      </div>
      <div className="trace-grid">
        <div>
          <h3>1 · Input memberships</h3>
          {trace.memberships.map((item) => (
            <div className="trace-card" key={item.variable}>
              <strong>
                {item.variable} = {item.value}
              </strong>
              {Object.entries(item.memberships).map(([term, value]) => (
                <div key={term}>
                  <span>{term}</span>
                  <code>{value.toFixed(6)}</code>
                </div>
              ))}
            </div>
          ))}
        </div>
        <div>
          <h3>2 · Rule firing</h3>
          {trace.rules.map((rule, index) => (
            <div className="trace-card" key={rule.rule_id}>
              <strong>
                Rule {index + 1} · {rule.output_term}
              </strong>
              <div>
                <span>firing</span>
                <code>{rule.firing_strength.toFixed(6)}</code>
              </div>
              <div>
                <span>weight</span>
                <code>{rule.weight.toFixed(3)}</code>
              </div>
              <div>
                <span>weighted</span>
                <code>{rule.weighted_firing_strength.toFixed(6)}</code>
              </div>
              {rule.consequent_value !== null && (
                <div>
                  <span>Sugeno consequent</span>
                  <code>{rule.consequent_value.toFixed(6)}</code>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
      {trace.inference_kind === "mamdani" ? (
        <><ChartSurface
          title="3 · Aggregated consequent membership"
          option={outputOption}
          theme={theme}
        /><div className="trace-footer"><span>Centroid · {trace.centroid_sampling === "midpoint_cells" ? "Midpoint cells" : "Inclusive nodes (legacy RuFLEX)"}</span><strong>Resolution {trace.centroid_resolution} · Δx {trace.centroid_dx?.toPrecision(6)}</strong></div></>
      ) : (
        <div className="trace-footer">
          <span>3 · normalized weighted Sugeno output</span>
          <strong>{trace.final_output.toFixed(6)}</strong>
        </div>
      )}
      <div className="trace-footer">
        <span>
          {trace.inference_kind === "mamdani"
            ? "4 · centroid"
            : "4 · exact reconstruction"}
        </span>
        <strong>{trace.final_output.toFixed(6)}</strong>
        <span className="mono">
          semantic hash {trace.semantic_hash.slice(0, 18)}…
        </span>
      </div>
      {previousTrace && <section className="trace-comparison"><div><span className="eyebrow">TRACE BEFORE / AFTER</span><h3>Actual computation change</h3><p>Previous output {previousTrace.final_output.toFixed(6)} → current output {trace.final_output.toFixed(6)}</p></div><div className="trace-change-grid"><div><strong>Membership changes</strong>{membershipChanges.length ? membershipChanges.map((change) => <p key={change.label}><span>{change.label}</span><code>{change.before.toFixed(5)} → {change.after.toFixed(5)}</code></p>) : <p>No membership degrees changed.</p>}</div><div><strong>Rule firing changes</strong>{firingChanges.length ? firingChanges.map((change) => <p key={change.label}><span>{change.label}</span><code>{change.before.toFixed(5)} → {change.after.toFixed(5)}</code></p>) : <p>No weighted rule firing changed.</p>}</div></div></section>}
    </section>
  );
}
