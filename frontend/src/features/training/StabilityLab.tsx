import { useEffect, useMemo, useState } from "react";
import { EChartsOption } from "echarts";
import { ProjectSummary, StabilityGatePolicy, StudyStabilityAnalysis, TrainingStudy, studioApi } from "../../api";
import { ChartSurface } from "../../charts/ChartSurface";
import { Button, EmptyState, StatusBadge } from "../../components/StudioPrimitives";
import { StudioTheme } from "../../design/tokens";

const confidence = (p: number) => Math.max(p, 1 - p);
const mapOption = (a: StudyStabilityAnalysis): EChartsOption => ({
  tooltip: { trigger: "item" }, grid: { left: 54, right: 18, top: 32, bottom: 44 },
  xAxis: { type: "value", name: "selected confidence", min: .5, max: 1 }, yAxis: { type: "value", name: "selected-run agreement", min: .5, max: 1 },
  visualMap: { show: false, dimension: 2, pieces: [{ lte: 0, color: "#c84040" }, { gt: 0, color: "#2d7f68" }] },
  series: [{ type: "scatter", symbolSize: 9, data: a.cases.map((c) => [confidence(c.selected_run_probability), c.selected_run_agreement ?? 0, confidence(c.selected_run_probability) >= a.high_confidence_threshold && (c.selected_run_agreement ?? 1) < a.unstable_agreement_threshold ? 0 : 1]) }],
});
const riskOption = (p: StabilityGatePolicy): EChartsOption => ({
  tooltip: { trigger: "axis" }, grid: { left: 54, right: 18, top: 32, bottom: 42 },
  xAxis: { type: "category", name: "policy", data: p.risk_coverage.map((x) => x.policy.replaceAll("_", " ")) }, yAxis: { type: "value", name: "accepted risk", min: 0, max: 1 },
  series: [{ type: "bar", data: p.risk_coverage.map((x) => x.accepted_risk) }],
});

export function StabilityLab({ project, study, theme }: { project: ProjectSummary; study: TrainingStudy | null; theme: StudioTheme }) {
  const [analysis, setAnalysis] = useState<StudyStabilityAnalysis | null>(null);
  const [policy, setPolicy] = useState<StabilityGatePolicy | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [caseId, setCaseId] = useState("");
  useEffect(() => {
    studioApi.listStudyStabilityAnalyses(project.session_id).then((x) => setAnalysis(x.at(-1) ?? null)).catch(() => setAnalysis(null));
    studioApi.listStabilityGatePolicies(project.session_id).then((x) => setPolicy(x.at(-1) ?? null)).catch(() => setPolicy(null));
  }, [project.session_id]);
  const selected = useMemo(() => analysis?.cases.find((x) => x.case_id === caseId) ?? analysis?.cases[0] ?? null, [analysis, caseId]);
  const decision = selected ? policy?.decisions.find((x) => x.case_id === selected.case_id) : undefined;
  const applicable = analysis?.applicability === "APPLICABLE";

  async function createAnalysis() {
    if (!study) return;
    setBusy(true); setError(null);
    try { const evaluation = await studioApi.createAnalysisEvaluation(project.session_id, study.selected_run_id); const threshold = await studioApi.selectAnalysisThreshold(project.session_id, evaluation.evaluation_id); const next = await studioApi.createStudyStabilityAnalysis(project.session_id, study.study_id, evaluation.evaluation_id, threshold.threshold_id); setAnalysis(next); setCaseId(next.cases[0]?.case_id ?? ""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not create stability analysis"); }
    finally { setBusy(false); }
  }
  async function createGate() {
    if (!analysis) return;
    setBusy(true); setError(null);
    try { if (!analysis.evaluation_id) throw new Error("Create threshold-bound validation stability evidence first."); setPolicy(await studioApi.createStabilityGatePolicy(project.session_id, analysis.analysis_id, analysis.evaluation_id, .9, .8, .15)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not freeze Stability Gate"); }
    finally { setBusy(false); }
  }
  if (!study) return <section className="feature-workspace"><EmptyState title="No multi-run study">Create a multi-run study before measuring aggregate variability. Case-level evidence requires a fixed split.</EmptyState></section>;

  return <section className="feature-workspace">
    <div className="feature-toolbar"><div><span className="eyebrow">STABILITY LAB</span><h2>Independent-fit evidence and stability-aware review</h2><p>Aggregate quality, one-run confidence, prediction stability, and explanation stability remain separate evidence channels.</p></div><StatusBadge tone={analysis ? (applicable ? "success" : "warning") : "info"}>{analysis ? (applicable ? "Persisted validation evidence" : "Case-level evidence not applicable") : "Ready"}</StatusBadge></div>
    <div className="feature-toolbar compact-toolbar"><div><strong>{study.randomness_protocol}</strong> · split seeds {study.seed_runs.map((x) => x.split_seed).join(", ")} · training seeds {study.training_seeds.join(", ")}</div><Button view="action" disabled={busy || project.read_only} onClick={createAnalysis}>{busy ? "Building…" : "Create Study Stability Analysis"}</Button></div>
    {analysis?.applicability === "NOT_APPLICABLE" && <div className="error" role="status">{analysis.applicability_reason} Aggregate distributions remain available; RuFLEX deliberately does not display HCIR or a Stability Gate for this protocol.</div>}
    {analysis?.warnings.map((warning) => <p key={warning} className="muted">Warning: {warning}</p>)}
    {analysis && <div className="run-summary-strip"><div><span>Validation cases</span><strong>{analysis.case_count}</strong></div><div><span>Frozen raw class threshold</span><strong>{analysis.decision_threshold === null ? "Not bound" : analysis.decision_threshold.toFixed(4)}</strong></div><div><span>HC instability rate (raw)</span><strong>{analysis.high_confidence_instability_rate === null ? "N/A" : `${(analysis.high_confidence_instability_rate * 100).toFixed(1)}%`}</strong></div><div><span>High-confidence denominator</span><strong>{analysis.high_confidence_case_count}</strong></div><div><span>Unstable among them</span><strong>{analysis.high_confidence_unstable_case_count}</strong></div></div>}
    {analysis && <div className="data-table-wrap"><table className="data-table"><thead><tr><th>metric</th><th>mean</th><th>std</th><th>median</th><th>IQR</th></tr></thead><tbody>{Object.entries(analysis.metric_distributions).map(([metric, values]) => <tr key={metric}><td>{metric}</td><td>{values.mean.toFixed(4)}</td><td>{values.std.toFixed(4)}</td><td>{values.median.toFixed(4)}</td><td>{values.iqr.toFixed(4)}</td></tr>)}</tbody></table></div>}
    {analysis && applicable && <ChartSurface title="Case Stability Map · selected-run agreement; red = high-confidence unstable" option={mapOption(analysis)} theme={theme}/>}
    {analysis && applicable && <section className="comparison-card"><div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">STABILITY-AWARE REVIEW GATE</span><p>Validation-derived raw probabilities: confidence &lt; 0.90, agreement &lt; 0.80, or probability std &gt; 0.15 ⇒ REVIEW. This is a capability comparison, not an A01 effectiveness result.</p></div><Button view="outlined" disabled={busy || project.read_only} onClick={createGate}>{policy ? "Create frozen Stability Gate" : "Freeze Stability Gate"}</Button></div>{policy && <><ChartSurface title="Risk–coverage comparison (same coverage)" option={riskOption(policy)} theme={theme}/><div className="data-table-wrap"><table className="data-table"><thead><tr><th>policy</th><th>coverage</th><th>accepted risk</th></tr></thead><tbody>{policy.risk_coverage.map((x) => <tr key={x.policy}><td>{x.policy}</td><td>{(x.coverage * 100).toFixed(1)}%</td><td>{x.accepted_risk === null ? "—" : `${(x.accepted_risk * 100).toFixed(1)}%`}</td></tr>)}</tbody></table></div></>}</section>}
    {analysis && applicable && <section className="comparison-card"><span className="eyebrow">CASE INSPECTOR</span><select aria-label="Stability case" value={selected?.case_id ?? ""} onChange={(event) => setCaseId(event.target.value)}>{analysis.cases.map((x) => <option key={x.case_id} value={x.case_id}>{x.case_id}</option>)}</select>{selected && <><p><strong>Selected run: {selected.selected_run_class} at {confidence(selected.selected_run_probability).toFixed(2)} confidence</strong> · selected decision supported by {Math.round((selected.selected_run_agreement ?? 0) * selected.run_support_count)}/{selected.run_support_count} independent fits · selected-run agreement {((selected.selected_run_agreement ?? 0) * 100).toFixed(0)}% · majority consensus {((selected.majority_class_agreement ?? 0) * 100).toFixed(0)}% · std {selected.std_probability.toFixed(3)}</p>{decision && <p><strong>{decision.disposition}</strong> · reason: {decision.reasons.join(", ") || "all frozen criteria met"}</p>}<div className="data-table-wrap"><table className="data-table"><thead><tr><th>training run</th><th>probability</th><th>class at frozen threshold</th></tr></thead><tbody>{Object.entries(selected.run_probabilities).map(([runId, probability]) => <tr key={runId}><td>{runId.slice(0, 12)}</td><td>{probability.toFixed(4)}</td><td>{selected.run_labels[runId]}</td></tr>)}</tbody></table></div></>}</section>}
    {analysis && <small>{analysis.scientific_note}</small>}
    {error && <div className="error" role="alert">{error}</div>}
  </section>;
}
