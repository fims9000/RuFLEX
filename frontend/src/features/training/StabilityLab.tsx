import { useEffect, useMemo, useRef, useState } from "react";
import { EChartsOption } from "echarts";
import { AnalysisEvaluation, DecisionThresholdPolicy, ProductApiError, ProjectSummary, StabilityGatePolicy, StudyStabilityAnalysis, TrainingStudy, studioApi } from "../../api";
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
type StabilityBuildRequest = { studyId: string; runId: string; evaluationId?: string; thresholdId?: string };

export function StabilityLab({ project, study, theme, onAnalysisChange, onPolicyChange }: { project: ProjectSummary; study: TrainingStudy | null; theme: StudioTheme; onAnalysisChange?: (value: StudyStabilityAnalysis | null) => void; onPolicyChange?: (value: StabilityGatePolicy | null) => void }) {
  const [analysis, setAnalysis] = useState<StudyStabilityAnalysis | null>(null);
  const [policy, setPolicy] = useState<StabilityGatePolicy | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisLoadState, setAnalysisLoadState] = useState<"loading" | "loaded" | "error">("loading");
  const [analysisLoadError, setAnalysisLoadError] = useState<string | null>(null);
  const [policyLoadState, setPolicyLoadState] = useState<"loading" | "loaded" | "error">("loading");
  const [policyLoadError, setPolicyLoadError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [caseId, setCaseId] = useState("");
  const [buildRecoveryRequest, setBuildRecoveryRequest] = useState<StabilityBuildRequest | null>(null);
  const [buildRecoveryError, setBuildRecoveryError] = useState<string | null>(null);
  const [buildRecoveryNotFound, setBuildRecoveryNotFound] = useState(false);
  const [gateRecoveryRequest, setGateRecoveryRequest] = useState<{ analysisId: string; evaluationId: string } | null>(null);
  const [gateRecoveryError, setGateRecoveryError] = useState<string | null>(null);
  const [gateRecoveryNotFound, setGateRecoveryNotFound] = useState(false);
  const onAnalysisChangeRef = useRef(onAnalysisChange);
  const onPolicyChangeRef = useRef(onPolicyChange);
  onAnalysisChangeRef.current = onAnalysisChange;
  onPolicyChangeRef.current = onPolicyChange;
  const activeAnalysis = analysis && study && analysis.study_id === study.study_id && analysis.selected_run_id === study.selected_run_id ? analysis : null;
  const activePolicy = activeAnalysis && study && policy && policy.study_id === study.study_id && policy.selected_run_id === study.selected_run_id && policy.stability_analysis_id === activeAnalysis.analysis_id && policy.evaluation_id === activeAnalysis.evaluation_id && policy.class_threshold_id === activeAnalysis.class_threshold_id ? policy : null;
  useEffect(() => {
    let active = true;
    setAnalysisLoadState("loading");
    setAnalysisLoadError(null);
    setPolicyLoadState("loading");
    setPolicyLoadError(null);
    studioApi.listStudyStabilityAnalyses(project.session_id).then((items) => {
      if (!active) return;
      const latest = items.filter((item) => item.study_id === study?.study_id && item.selected_run_id === study.selected_run_id).at(-1) ?? null;
      setAnalysis(latest);
      onAnalysisChangeRef.current?.(latest);
      setAnalysisLoadState("loaded");
    }).catch((reason: unknown) => {
      if (!active) return;
      setAnalysis(null);
      onAnalysisChangeRef.current?.(null);
      setAnalysisLoadError(reason instanceof Error ? reason.message : "Saved StudyStabilityAnalysis could not be verified.");
      setAnalysisLoadState("error");
    });
    studioApi.listStabilityGatePolicies(project.session_id).then((items) => {
      if (!active) return;
      const latest = items.filter((item) => item.study_id === study?.study_id && item.selected_run_id === study.selected_run_id).at(-1) ?? null;
      setPolicy(latest);
      onPolicyChangeRef.current?.(latest);
      setPolicyLoadState("loaded");
    }).catch((reason: unknown) => {
      if (!active) return;
      setPolicy(null);
      onPolicyChangeRef.current?.(null);
      setPolicyLoadError(reason instanceof Error ? reason.message : "Saved StabilityGatePolicy could not be verified.");
      setPolicyLoadState("error");
    });
    return () => { active = false; };
  }, [project.session_id, reload, study?.study_id, study?.selected_run_id]);
  const selected = useMemo(() => activeAnalysis?.cases.find((x) => x.case_id === caseId) ?? activeAnalysis?.cases[0] ?? null, [activeAnalysis, caseId]);
  const decision = selected ? activePolicy?.decisions.find((x) => x.case_id === selected.case_id) : undefined;
  const applicable = activeAnalysis?.applicability === "APPLICABLE";
  const protocolNote = study?.randomness_protocol === "TRAINING_VARIABILITY"
    ? "Training variability fixes split membership and changes only the declared training seed; case-level agreement is fully aligned."
    : study?.randomness_protocol === "SPLIT_VARIABILITY"
      ? "Split variability fixes the training seed but changes split membership; only explicitly aligned case evidence is eligible for case-level analysis."
      : "Combined variability changes both split and training seeds; observed variability mixes data-partition and training effects."

  async function createAnalysis() {
    if (!study) return;
    let request: StabilityBuildRequest = { studyId: study.study_id, runId: study.selected_run_id };
    setBusy(true); setError(null);
    try {
      const evaluation = await studioApi.createAnalysisEvaluation(project.session_id, request.runId);
      request = { ...request, evaluationId: evaluation.evaluation_id };
      const threshold = await studioApi.selectAnalysisThreshold(project.session_id, evaluation.evaluation_id);
      request = { ...request, thresholdId: threshold.threshold_id };
      const next = await studioApi.createStudyStabilityAnalysis(project.session_id, request.studyId, evaluation.evaluation_id, threshold.threshold_id);
      setAnalysis(next); onAnalysisChange?.(next); setAnalysisLoadState("loaded"); setCaseId(next.cases[0]?.case_id ?? "");
      setBuildRecoveryRequest(null); setBuildRecoveryError(null); setBuildRecoveryNotFound(false);
    }
    catch (reason) {
      setBuildRecoveryRequest(request);
      setBuildRecoveryError(reason instanceof Error ? reason.message : "Could not confirm the frozen analysis chain.");
      setBuildRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : "Could not create stability analysis");
    }
    finally { setBusy(false); }
  }

  function completeAnalysisBuild(next: StudyStabilityAnalysis) {
    setAnalysis(next); onAnalysisChange?.(next); setAnalysisLoadState("loaded"); setCaseId(next.cases[0]?.case_id ?? "");
    setBuildRecoveryRequest(null); setBuildRecoveryError(null); setBuildRecoveryNotFound(false);
  }

  async function continueAnalysisBuild(request: StabilityBuildRequest) {
    let evaluation: AnalysisEvaluation;
    if (request.evaluationId) evaluation = await studioApi.getAnalysisEvaluation(project.session_id, request.evaluationId);
    else evaluation = await studioApi.createAnalysisEvaluation(project.session_id, request.runId);
    if (evaluation.run_id !== request.runId) throw new Error("Recovered AnalysisEvaluation is bound to another TrainingRun.");
    request = { ...request, evaluationId: evaluation.evaluation_id };
    let threshold: DecisionThresholdPolicy;
    if (request.thresholdId) threshold = await studioApi.getAnalysisThreshold(project.session_id, request.thresholdId);
    else threshold = await studioApi.selectAnalysisThreshold(project.session_id, evaluation.evaluation_id);
    if (threshold.evaluation_id !== evaluation.evaluation_id || threshold.calibration_id !== null || threshold.probability_source !== "raw") throw new Error("Recovered Stability threshold is not the exact raw validation threshold for this Evaluation.");
    request = { ...request, thresholdId: threshold.threshold_id };
    const next = await studioApi.createStudyStabilityAnalysis(project.session_id, request.studyId, evaluation.evaluation_id, threshold.threshold_id);
    completeAnalysisBuild(next);
  }

  async function recoverAnalysisBuild() {
    const original = buildRecoveryRequest;
    if (!original) return;
    setBusy(true); setError(null);
    try {
      let request = { ...original };
      if (!request.evaluationId) {
        let evaluation: AnalysisEvaluation;
        try { evaluation = await studioApi.getLatestAnalysisEvaluation(project.session_id); }
        catch (reason) {
          if (reason instanceof ProductApiError && reason.status === 404) {
            setBuildRecoveryNotFound(true); setBuildRecoveryError("No Evaluation is visible yet. Retry lookup later, or explicitly continue the same frozen run chain."); return;
          }
          throw reason;
        }
        if (evaluation.run_id !== request.runId) {
          setBuildRecoveryNotFound(true); setBuildRecoveryError("The latest Evaluation belongs to another run; no replacement was created."); return;
        }
        request = { ...request, evaluationId: evaluation.evaluation_id };
        setBuildRecoveryRequest(request);
      }
      if (!request.thresholdId) {
        let threshold: DecisionThresholdPolicy;
        try { threshold = await studioApi.getLatestAnalysisThreshold(project.session_id); }
        catch (reason) {
          if (reason instanceof ProductApiError && reason.status === 404) {
            setBuildRecoveryNotFound(true); setBuildRecoveryError("The exact Evaluation is recovered, but no threshold is visible yet. Retry lookup later, or explicitly continue this chain."); return;
          }
          throw reason;
        }
        if (threshold.evaluation_id !== request.evaluationId || threshold.calibration_id !== null || threshold.probability_source !== "raw") {
          setBuildRecoveryNotFound(true); setBuildRecoveryError("The latest threshold is not bound to this Evaluation as raw validation evidence."); return;
        }
        request = { ...request, thresholdId: threshold.threshold_id };
        setBuildRecoveryRequest(request);
      }
      const analyses = await studioApi.listStudyStabilityAnalyses(project.session_id);
      const existing = analyses.find((item) => item.study_id === request.studyId && item.evaluation_id === request.evaluationId && item.class_threshold_id === request.thresholdId);
      if (existing) { completeAnalysisBuild(existing); return; }
      setBuildRecoveryNotFound(true); setBuildRecoveryError("The exact Evaluation and threshold are saved, but no matching Stability Analysis is visible yet. Retry lookup later, or explicitly continue this same chain.");
    } catch (reason) {
      setBuildRecoveryError(reason instanceof Error ? reason.message : "Could not recover the exact Stability Analysis chain.");
      setBuildRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  async function explicitlyContinueAnalysisBuild() {
    if (!buildRecoveryRequest || !buildRecoveryNotFound) return;
    setBusy(true); setError(null);
    try { await continueAnalysisBuild(buildRecoveryRequest); }
    catch (reason) {
      setBuildRecoveryError(reason instanceof Error ? reason.message : "The explicitly continued Stability Analysis chain could not be confirmed.");
      setBuildRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }
  async function createGate() {
    if (!activeAnalysis || activeAnalysis.study_id !== study?.study_id || activeAnalysis.selected_run_id !== study.selected_run_id) return;
    if (!activeAnalysis.evaluation_id) { setError("Create threshold-bound validation stability evidence first."); return; }
    const request = { analysisId: activeAnalysis.analysis_id, evaluationId: activeAnalysis.evaluation_id };
    setBusy(true); setError(null);
    try { await submitGate(request); }
    catch (reason) { setGateRecoveryRequest(request); setGateRecoveryError(reason instanceof Error ? reason.message : "The saved Stability Gate could not be confirmed."); setGateRecoveryNotFound(false); setError(reason instanceof Error ? reason.message : "Could not freeze Stability Gate"); }
    finally { setBusy(false); }
  }

  async function submitGate(request: { analysisId: string; evaluationId: string }) {
    const next = await studioApi.createStabilityGatePolicy(project.session_id, request.analysisId, request.evaluationId, .9, .8, .15);
    setPolicy(next); onPolicyChange?.(next); setPolicyLoadState("loaded"); setGateRecoveryRequest(null); setGateRecoveryError(null); setGateRecoveryNotFound(false);
  }

  async function recoverGate() {
    if (!gateRecoveryRequest) return;
    setBusy(true); setError(null);
    try {
      const policies = await studioApi.listStabilityGatePolicies(project.session_id);
      const saved = policies.find((item) => item.stability_analysis_id === gateRecoveryRequest.analysisId && item.evaluation_id === gateRecoveryRequest.evaluationId && item.min_confidence === .9 && item.min_class_agreement === .8 && item.max_probability_std === .15 && item.probability_source === "raw");
      if (!saved) { setGateRecoveryNotFound(true); setGateRecoveryError("No saved gate with this exact analysis and criteria is visible yet. Retry lookup later, or explicitly freeze this same gate."); return; }
      setPolicy(saved); onPolicyChange?.(saved); setPolicyLoadState("loaded"); setGateRecoveryRequest(null); setGateRecoveryError(null); setGateRecoveryNotFound(false);
    } catch (reason) {
      setGateRecoveryError(reason instanceof Error ? reason.message : "Could not recover the exact Stability Gate.");
      setGateRecoveryNotFound(false); setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  async function explicitlyFreezeGate() {
    if (!gateRecoveryRequest || !gateRecoveryNotFound) return;
    setBusy(true); setError(null);
    try { await submitGate(gateRecoveryRequest); }
    catch (reason) { setGateRecoveryError(reason instanceof Error ? reason.message : "The repeated Stability Gate request could not be confirmed."); setGateRecoveryNotFound(false); setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }
  if (!study) return <section className="feature-workspace"><EmptyState title="No multi-run study">Create a multi-run study before measuring aggregate variability. Case-level evidence requires a fixed split.</EmptyState></section>;

  return <section className="feature-workspace">
    <div className="feature-toolbar"><div><span className="eyebrow">STABILITY LAB</span><h2>Independent-fit evidence and stability-aware review</h2><p>Aggregate quality, one-run confidence, prediction stability, and explanation stability remain separate evidence channels.</p></div><StatusBadge tone={analysisLoadState === "error" || policyLoadState === "error" ? "danger" : activeAnalysis ? (applicable ? "success" : "warning") : "info"}>{analysisLoadState === "loading" || policyLoadState === "loading" ? "Loading saved stability evidence" : analysisLoadState === "error" || policyLoadState === "error" ? "Saved evidence unavailable" : activeAnalysis ? (applicable ? "Persisted validation evidence" : "Case-level evidence not applicable") : "Ready"}</StatusBadge></div>
    {analysisLoadState === "error" && <div className="error" role="alert" data-testid="stability-analysis-load-error"><strong>Saved StudyStabilityAnalysis could not be verified.</strong><p>{analysisLoadError}</p><Button view="outlined" onClick={() => setReload((current) => current + 1)}>Retry Stability Analysis</Button></div>}
    {policyLoadState === "error" && <div className="error" role="alert" data-testid="stability-policy-load-error"><strong>Saved StabilityGatePolicy could not be verified.</strong><p>{policyLoadError}</p><Button view="outlined" onClick={() => setReload((current) => current + 1)}>Retry Stability Gate</Button></div>}
    {(analysisLoadState === "loading" || policyLoadState === "loading") && <p role="status">Resolving saved Stability Lab evidence before enabling new analysis or policy actions…</p>}
    {buildRecoveryRequest && <div className="error" role="alert" data-testid="stability-analysis-recovery"><strong>Stability Analysis chain outcome is uncertain; recover the same study/run before creating another.</strong><p>{buildRecoveryError}</p><Button view="outlined" disabled={busy} onClick={recoverAnalysisBuild}>Retry saved chain lookup</Button>{buildRecoveryNotFound && <Button view="outlined" disabled={busy} onClick={explicitlyContinueAnalysisBuild}>Continue this chain explicitly</Button>}</div>}
    <div className="feature-toolbar compact-toolbar"><div><strong>{study.randomness_protocol}</strong> · split seeds {study.seed_runs.map((x) => x.split_seed).join(", ")} · training seeds {study.training_seeds.join(", ")}<p className="property-description">{protocolNote}</p></div><Button view="action" disabled={busy || !!buildRecoveryRequest || project.read_only || analysisLoadState !== "loaded" || policyLoadState !== "loaded"} onClick={createAnalysis} data-ruflex-action="stability.analysis.create">{busy ? "Building…" : "Create Study Stability Analysis"}</Button></div>
    {activeAnalysis?.applicability === "NOT_APPLICABLE" && <div className="error" role="status">{activeAnalysis.applicability_reason} Aggregate distributions remain available; RuFLEX deliberately does not display HCIR or a Stability Gate for this protocol.</div>}
    {activeAnalysis?.warnings.map((warning) => <p key={warning} className="muted">Warning: {warning}</p>)}
    {activeAnalysis && <div className="run-summary-strip"><div><span>Validation cases</span><strong>{activeAnalysis.case_count}</strong></div><div><span>Frozen raw class threshold</span><strong>{activeAnalysis.decision_threshold === null ? "Not bound" : activeAnalysis.decision_threshold.toFixed(4)}</strong></div><div><span>HC instability rate (raw)</span><strong>{activeAnalysis.high_confidence_instability_rate === null ? "N/A" : `${(activeAnalysis.high_confidence_instability_rate * 100).toFixed(1)}%`}</strong></div><div><span>High-confidence denominator</span><strong>{activeAnalysis.high_confidence_case_count}</strong></div><div><span>Unstable among them</span><strong>{activeAnalysis.high_confidence_unstable_case_count}</strong></div></div>}
    {activeAnalysis && <div className="data-table-wrap"><table className="data-table"><thead><tr><th>metric</th><th>mean</th><th>std</th><th>median</th><th>IQR</th></tr></thead><tbody>{Object.entries(activeAnalysis.metric_distributions).map(([metric, values]) => <tr key={metric}><td>{metric}</td><td>{values.mean.toFixed(4)}</td><td>{values.std.toFixed(4)}</td><td>{values.median.toFixed(4)}</td><td>{values.iqr.toFixed(4)}</td></tr>)}</tbody></table></div>}
    {activeAnalysis && applicable && <ChartSurface title="Case Stability Map · selected-run agreement; red = high-confidence unstable" option={mapOption(activeAnalysis)} theme={theme}/>}
    {activeAnalysis && applicable && <section className="comparison-card"><div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">STABILITY-AWARE REVIEW GATE</span><p>Validation-derived raw probabilities: confidence &lt; 0.90, agreement &lt; 0.80, or probability std &gt; 0.15 ⇒ REVIEW. This is a capability comparison, not an A01 effectiveness result.</p></div><Button view="outlined" disabled={!activeAnalysis || busy || !!gateRecoveryRequest || !!buildRecoveryRequest || project.read_only || analysisLoadState !== "loaded" || policyLoadState !== "loaded"} onClick={createGate} data-ruflex-action="stability.freeze">{activePolicy ? "Create frozen Stability Gate" : "Freeze Stability Gate"}</Button></div>{gateRecoveryRequest && <div className="error" role="alert" data-testid="stability-gate-recovery"><strong>Stability Gate outcome is uncertain; recover by the exact analysis and frozen criteria.</strong><p>{gateRecoveryError}</p><Button view="outlined" disabled={busy} onClick={recoverGate}>Retry saved gate lookup</Button>{gateRecoveryNotFound && <Button view="outlined" disabled={busy} onClick={explicitlyFreezeGate}>Freeze this gate explicitly</Button>}</div>}{activePolicy && <><ChartSurface title="Risk–coverage comparison (same coverage)" option={riskOption(activePolicy)} theme={theme}/><div className="data-table-wrap"><table className="data-table"><thead><tr><th>policy</th><th>coverage</th><th>accepted risk</th></tr></thead><tbody>{activePolicy.risk_coverage.map((x) => <tr key={x.policy}><td>{x.policy}</td><td>{(x.coverage * 100).toFixed(1)}%</td><td>{x.accepted_risk === null ? "—" : `${(x.accepted_risk * 100).toFixed(1)}%`}</td></tr>)}</tbody></table></div></>}</section>}
    {activeAnalysis && applicable && <section className="comparison-card"><span className="eyebrow">CASE INSPECTOR</span><select aria-label="Stability case" value={selected?.case_id ?? ""} onChange={(event) => setCaseId(event.target.value)}>{activeAnalysis.cases.map((x) => <option key={x.case_id} value={x.case_id}>{x.case_id}</option>)}</select>{selected && <><p><strong>Selected run: {selected.selected_run_class} at {confidence(selected.selected_run_probability).toFixed(2)} confidence</strong> · selected decision supported by {Math.round((selected.selected_run_agreement ?? 0) * selected.run_support_count)}/{selected.run_support_count} independent fits · selected-run agreement {((selected.selected_run_agreement ?? 0) * 100).toFixed(0)}% · majority consensus {((selected.majority_class_agreement ?? 0) * 100).toFixed(0)}% · std {selected.std_probability.toFixed(3)}</p>{decision && <p><strong>{decision.disposition}</strong> · reason: {decision.reasons.join(", ") || "all frozen criteria met"}</p>}<div className="data-table-wrap"><table className="data-table"><thead><tr><th>training run</th><th>probability</th><th>class at frozen threshold</th></tr></thead><tbody>{Object.entries(selected.run_probabilities).map(([runId, probability]) => <tr key={runId}><td>{runId.slice(0, 12)}</td><td>{probability.toFixed(4)}</td><td>{selected.run_labels[runId]}</td></tr>)}</tbody></table></div></>}</section>}
    {activeAnalysis && <small>{activeAnalysis.scientific_note}</small>}
    {error && <div className="error" role="alert">{error}</div>}
  </section>;
}
