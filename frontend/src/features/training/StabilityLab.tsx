import { useEffect, useMemo, useRef, useState } from "react";
import { EChartsOption } from "echarts";
import { AnalysisEvaluation, DecisionThresholdPolicy, ProductApiError, ProjectSummary, StabilityGatePolicy, StudyStabilityAnalysis, TrainingStudy, studioApi } from "../../api";
import { ChartSurface } from "../../charts/ChartSurface";
import { Button, EmptyState, StatusBadge } from "../../components/StudioPrimitives";
import { StudioTheme } from "../../design/tokens";
import { ui, uiLanguage, uiStatus } from "../../design/language";
import { isActiveStudyStabilityAnalysis, isActiveStudyStabilityGate } from "./stabilityBinding";

const confidence = (p: number) => Math.max(p, 1 - p);
const mapOption = (a: StudyStabilityAnalysis): EChartsOption => ({
  tooltip: { trigger: "item" }, grid: { left: 54, right: 18, top: 32, bottom: 44 },
  xAxis: { type: "value", name: ui("selected confidence", "Уверенность модели"), min: .5, max: 1 }, yAxis: { type: "value", name: ui("selected-run agreement", "Поддержка решения"), min: 0, max: 1 },
  visualMap: { show: false, dimension: 2, pieces: [{ lte: 0, color: "#c84040" }, { gt: 0, color: "#2d7f68" }] },
  series: [{ type: "scatter", symbolSize: 9, data: a.cases.filter((c) => c.selected_run_agreement !== null).map((c) => [confidence(c.selected_run_probability), c.selected_run_agreement!, confidence(c.selected_run_probability) >= a.high_confidence_threshold && c.selected_run_agreement! < a.unstable_agreement_threshold ? 0 : 1]) }],
});
const riskOption = (p: StabilityGatePolicy): EChartsOption => ({
  tooltip: { trigger: "axis" }, grid: { left: 54, right: 18, top: 32, bottom: 42 },
  xAxis: { type: "category", name: ui("policy", "Правило"), data: p.risk_coverage.map((x) => ui(x.policy.replaceAll("_", " "), policyLabel(x.policy))) }, yAxis: { type: "value", name: ui("accepted risk", "Доля ошибок"), min: 0, max: 1 },
  series: [{ type: "bar", data: p.risk_coverage.map((x) => x.accepted_risk) }],
});
type StabilityBuildRequest = { studyId: string; runId: string; evaluationId?: string; thresholdId?: string };
const policyLabels: Record<string, string> = { NO_REVIEW: "Без проверки", CONFIDENCE_ONLY: "По уверенности", STABILITY_GATE: "По устойчивости", STABILITY_AWARE: "По устойчивости", RANDOM: "Случайный отбор", RANDOM_REVIEW: "Случайный отбор" };
const policyLabel = (value: string) => policyLabels[value] ?? value;

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
  const mutationInFlightRef = useRef(false);
  const onAnalysisChangeRef = useRef(onAnalysisChange);
  const onPolicyChangeRef = useRef(onPolicyChange);
  onAnalysisChangeRef.current = onAnalysisChange;
  onPolicyChangeRef.current = onPolicyChange;
  const activeAnalysis = isActiveStudyStabilityAnalysis(analysis, study) ? analysis : null;
  const activePolicy = isActiveStudyStabilityGate(policy, activeAnalysis, study) ? policy : null;
  useEffect(() => {
    if (analysisLoadState !== "loading") onAnalysisChangeRef.current?.(analysisLoadState === "loaded" ? activeAnalysis : null);
  }, [analysisLoadState, activeAnalysis]);
  useEffect(() => {
    if (analysisLoadState !== "loading" && policyLoadState !== "loading") onPolicyChangeRef.current?.(analysisLoadState === "loaded" && policyLoadState === "loaded" ? activePolicy : null);
  }, [analysisLoadState, policyLoadState, activePolicy]);
  function beginMutation(): boolean {
    if (mutationInFlightRef.current) return false;
    mutationInFlightRef.current = true;
    setBusy(true);
    return true;
  }
  function endMutation() {
    mutationInFlightRef.current = false;
    setBusy(false);
  }
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
      setAnalysisLoadState("loaded");
    }).catch((reason: unknown) => {
      if (!active) return;
      setAnalysis(null);
      setAnalysisLoadError(reason instanceof Error ? reason.message : "Saved StudyStabilityAnalysis could not be verified.");
      setAnalysisLoadState("error");
    });
    studioApi.listStabilityGatePolicies(project.session_id).then((items) => {
      if (!active) return;
      const latest = items.filter((item) => item.study_id === study?.study_id && item.selected_run_id === study.selected_run_id).at(-1) ?? null;
      setPolicy(latest);
      setPolicyLoadState("loaded");
    }).catch((reason: unknown) => {
      if (!active) return;
      setPolicy(null);
      setPolicyLoadError(reason instanceof Error ? reason.message : "Saved StabilityGatePolicy could not be verified.");
      setPolicyLoadState("error");
    });
    return () => { active = false; };
  }, [project.session_id, reload, study?.study_id, study?.selected_run_id]);
  const selected = useMemo(() => activeAnalysis?.cases.find((x) => x.case_id === caseId) ?? activeAnalysis?.cases[0] ?? null, [activeAnalysis, caseId]);
  const decision = selected ? activePolicy?.decisions.find((x) => x.case_id === selected.case_id) : undefined;
  const applicable = activeAnalysis?.applicability === "APPLICABLE";
  const protocolNote = study?.randomness_protocol === "TRAINING_VARIABILITY"
    ? ui("Training variability fixes split membership and changes only the declared training seed; case-level agreement is fully aligned.", "Одни и те же примеры, разные случайные состояния обучения. Решения моделей можно сравнивать по каждому примеру.")
    : study?.randomness_protocol === "SPLIT_VARIABILITY"
      ? ui("Split variability fixes the training seed but changes split membership; only explicitly aligned case evidence is eligible for case-level analysis.", "Меняется разбиение данных. Сравнение решений допустимо только для сопоставимых примеров с известной поддержкой.")
      : ui("Combined variability changes both split and training seeds; observed variability mixes data-partition and training effects.", "Меняются и разбиение, и случайность обучения. Их влияние здесь не разделено.")

  async function createAnalysis() {
    if (!study || analysis || buildRecoveryRequest || !beginMutation()) return;
    let request: StabilityBuildRequest = { studyId: study.study_id, runId: study.selected_run_id };
    setError(null);
    try {
      const evaluation = await studioApi.createAnalysisEvaluation(project.session_id, request.runId);
      request = { ...request, evaluationId: evaluation.evaluation_id };
      const threshold = await studioApi.selectAnalysisThreshold(project.session_id, evaluation.evaluation_id);
      request = { ...request, thresholdId: threshold.threshold_id };
      const next = await studioApi.createStudyStabilityAnalysis(project.session_id, request.studyId, evaluation.evaluation_id, threshold.threshold_id);
      setAnalysis(next); setAnalysisLoadState("loaded"); setCaseId(next.cases[0]?.case_id ?? "");
      setBuildRecoveryRequest(null); setBuildRecoveryError(null); setBuildRecoveryNotFound(false);
    }
    catch (reason) {
      setBuildRecoveryRequest(request);
      setBuildRecoveryError(reason instanceof Error ? reason.message : "Could not confirm the frozen analysis chain.");
      setBuildRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : "Could not create stability analysis");
    }
    finally { endMutation(); }
  }

  function completeAnalysisBuild(next: StudyStabilityAnalysis) {
    setAnalysis(next); setAnalysisLoadState("loaded"); setCaseId(next.cases[0]?.case_id ?? "");
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
    if (!original || !beginMutation()) return;
    setError(null);
    try {
      let request = { ...original };
      if (!request.evaluationId) {
        let evaluation: AnalysisEvaluation;
        try { evaluation = await studioApi.getLatestAnalysisEvaluationForRun(project.session_id, request.runId); }
        catch (reason) {
          if (reason instanceof ProductApiError && reason.status === 404) {
            setBuildRecoveryNotFound(true); setBuildRecoveryError("No validation Evaluation is persisted for this exact run yet. Retry lookup later, or explicitly continue the same frozen run chain."); return;
          }
          throw reason;
        }
        if (evaluation.run_id !== request.runId) {
          setBuildRecoveryNotFound(true); setBuildRecoveryError("The run-bound Evaluation lookup returned another TrainingRun; no replacement was created."); return;
        }
        request = { ...request, evaluationId: evaluation.evaluation_id };
        setBuildRecoveryRequest(request);
      }
      if (!request.thresholdId) {
        let threshold: DecisionThresholdPolicy;
        try { threshold = await studioApi.getLatestAnalysisThresholdForEvaluation(project.session_id, request.evaluationId!, null); }
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
    } finally { endMutation(); }
  }

  async function explicitlyContinueAnalysisBuild() {
    if (!buildRecoveryRequest || !buildRecoveryNotFound || !beginMutation()) return;
    setError(null);
    try { await continueAnalysisBuild(buildRecoveryRequest); }
    catch (reason) {
      setBuildRecoveryError(reason instanceof Error ? reason.message : "The explicitly continued Stability Analysis chain could not be confirmed.");
      setBuildRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { endMutation(); }
  }
  async function createGate() {
    if (!activeAnalysis || activeAnalysis.study_id !== study?.study_id || activeAnalysis.selected_run_id !== study.selected_run_id) return;
    if (activePolicy || gateRecoveryRequest || buildRecoveryRequest || !beginMutation()) return;
    if (!activeAnalysis.evaluation_id) { endMutation(); setError("Create threshold-bound validation stability evidence first."); return; }
    const request = { analysisId: activeAnalysis.analysis_id, evaluationId: activeAnalysis.evaluation_id };
    setError(null);
    try { await submitGate(request); }
    catch (reason) { setGateRecoveryRequest(request); setGateRecoveryError(reason instanceof Error ? reason.message : "The saved Stability Gate could not be confirmed."); setGateRecoveryNotFound(false); setError(reason instanceof Error ? reason.message : "Could not freeze Stability Gate"); }
    finally { endMutation(); }
  }

  async function submitGate(request: { analysisId: string; evaluationId: string }) {
    const next = await studioApi.createStabilityGatePolicy(project.session_id, request.analysisId, request.evaluationId, .9, .8, .15);
    setPolicy(next); setPolicyLoadState("loaded"); setGateRecoveryRequest(null); setGateRecoveryError(null); setGateRecoveryNotFound(false);
  }

  async function recoverGate() {
    if (!gateRecoveryRequest || !beginMutation()) return;
    setError(null);
    try {
      const policies = await studioApi.listStabilityGatePolicies(project.session_id);
      const saved = policies.find((item) => item.stability_analysis_id === gateRecoveryRequest.analysisId && item.evaluation_id === gateRecoveryRequest.evaluationId && item.min_confidence === .9 && item.min_class_agreement === .8 && item.max_probability_std === .15 && item.probability_source === "raw");
      if (!saved) { setGateRecoveryNotFound(true); setGateRecoveryError("No saved gate with this exact analysis and criteria is visible yet. Retry lookup later, or explicitly freeze this same gate."); return; }
      setPolicy(saved); setPolicyLoadState("loaded"); setGateRecoveryRequest(null); setGateRecoveryError(null); setGateRecoveryNotFound(false);
    } catch (reason) {
      setGateRecoveryError(reason instanceof Error ? reason.message : "Could not recover the exact Stability Gate.");
      setGateRecoveryNotFound(false); setError(reason instanceof Error ? reason.message : String(reason));
    } finally { endMutation(); }
  }

  async function explicitlyFreezeGate() {
    if (!gateRecoveryRequest || !gateRecoveryNotFound || !beginMutation()) return;
    setError(null);
    try { await submitGate(gateRecoveryRequest); }
    catch (reason) { setGateRecoveryError(reason instanceof Error ? reason.message : "The repeated Stability Gate request could not be confirmed."); setGateRecoveryNotFound(false); setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { endMutation(); }
  }
  if (!study) return <section className="feature-workspace"><EmptyState title={ui("No multi-run study", "Нет серии обучений")}>{ui("Create a multi-run study before measuring aggregate variability. Case-level evidence requires a fixed split.", "Сначала запустите серию обучений. Для сравнения решений по отдельным примерам используйте одно фиксированное разбиение.")}</EmptyState></section>;

  return <section className="feature-workspace stability-workspace">
    <div className="feature-toolbar"><div><span className="eyebrow">{ui("STABILITY LAB", "УСТОЙЧИВОСТЬ")}</span><h2>{ui("Independent-fit evidence and stability-aware review", "Насколько согласованы решения моделей")}</h2><p>{ui("Aggregate quality, one-run confidence, prediction stability, and explanation stability remain separate evidence channels.", "Качество модели, уверенность прогноза и согласие разных обучений — разные характеристики.")}</p></div><StatusBadge tone={analysisLoadState === "error" || policyLoadState === "error" ? "danger" : activeAnalysis ? (applicable ? "success" : "warning") : "info"}>{analysisLoadState === "loading" || policyLoadState === "loading" ? ui("Loading saved stability evidence", "Загрузка результатов") : analysisLoadState === "error" || policyLoadState === "error" ? ui("Saved evidence unavailable", "Результаты недоступны") : activeAnalysis ? (applicable ? ui("Persisted validation evidence", "Результаты сохранены") : ui("Case-level evidence not applicable", "Примеры несопоставимы")) : ui("Ready", "Готово к расчёту")}</StatusBadge></div>
    {analysisLoadState === "error" && <div className="error" role="alert" data-testid="stability-analysis-load-error"><strong>{ui("Saved StudyStabilityAnalysis could not be verified.", "Не удалось загрузить анализ устойчивости.")}</strong><p>{analysisLoadError}</p><Button view="outlined" onClick={() => setReload((current) => current + 1)}>{ui("Retry Stability Analysis", "Повторить загрузку анализа")}</Button></div>}
    {analysis && !activeAnalysis && <div className="error" role="alert" data-testid="stability-analysis-provenance-error">Saved StudyStabilityAnalysis does not match the selected Study's model, dataset revision, protocol, or exact run set. It is not usable here; inspect project integrity before creating new stability evidence.<Button view="outlined" onClick={() => setReload((current) => current + 1)}>Retry Stability Analysis</Button></div>}
    {policyLoadState === "error" && <div className="error" role="alert" data-testid="stability-policy-load-error"><strong>{ui("Saved StabilityGatePolicy could not be verified.", "Не удалось загрузить сохранённое правило проверки.")}</strong><p>{policyLoadError}</p><Button view="outlined" onClick={() => setReload((current) => current + 1)}>{ui("Retry Stability Gate", "Повторить загрузку правила")}</Button></div>}
    {(analysisLoadState === "loading" || policyLoadState === "loading") && <p role="status">{ui("Resolving saved Stability Lab evidence before enabling new analysis or policy actions…", "Проверяем ранее сохранённые результаты…")}</p>}
    {buildRecoveryRequest && <div className="error" role="alert" data-testid="stability-analysis-recovery"><strong>Stability Analysis chain outcome is uncertain; recover the same study/run before creating another.</strong><p>{buildRecoveryError}</p><Button view="outlined" disabled={busy} onClick={recoverAnalysisBuild}>Retry saved chain lookup</Button>{buildRecoveryNotFound && <Button view="outlined" disabled={busy} onClick={explicitlyContinueAnalysisBuild}>Continue this chain explicitly</Button>}</div>}
    <div className="feature-toolbar compact-toolbar"><div><strong>{ui(study.randomness_protocol, study.randomness_protocol === "TRAINING_VARIABILITY" ? "Разные обучения, одни данные" : study.randomness_protocol === "SPLIT_VARIABILITY" ? "Разные разбиения данных" : "Разные обучения и разбиения")}</strong><details open={uiLanguage === "en"}><summary>{ui("Randomness settings", "Случайные состояния")}</summary>split seeds {study.seed_runs.map((x) => x.split_seed).join(", ")} · training seeds {study.training_seeds.join(", ")}</details><p className="property-description">{protocolNote}</p></div><Button view="action" disabled={busy || !!analysis || !!buildRecoveryRequest || project.read_only || analysisLoadState !== "loaded" || policyLoadState !== "loaded"} onClick={createAnalysis} data-ruflex-action="stability.analysis.create">{busy ? ui("Building…", "Рассчитываем…") : activeAnalysis ? ui("Stability Analysis saved", "Анализ сохранён") : ui("Create Study Stability Analysis", "Сравнить решения моделей")}</Button></div>
    {activeAnalysis?.applicability === "NOT_APPLICABLE" && <div className="error" role="status">{activeAnalysis.applicability_reason} Aggregate distributions remain available; RuFLEX deliberately does not display HCIR or a Stability Gate for this protocol.</div>}
    {activeAnalysis && policy && !activePolicy && <p role="status">A saved Stability Gate exists, but its frozen run, validation, threshold, dataset, or criteria provenance does not match this analysis; it is not shown as active.</p>}
    {activeAnalysis?.warnings.map((warning) => <p key={warning} className="muted">Warning: {warning}</p>)}
    {activeAnalysis && <div className="run-summary-strip"><div><span>{ui("Validation cases", "Проверочных примеров")}</span><strong>{activeAnalysis.case_count}</strong></div><div><span>{ui("Frozen raw class threshold", "Сохранённый порог класса")}</span><strong>{activeAnalysis.decision_threshold === null ? ui("Not bound", "Не задан") : activeAnalysis.decision_threshold.toFixed(4)}</strong></div><div><span>{ui("HC instability rate (raw)", "Нестабильных среди уверенных")}</span><strong>{activeAnalysis.high_confidence_instability_rate === null ? "N/A" : `${(activeAnalysis.high_confidence_instability_rate * 100).toFixed(1)}%`}</strong></div><div><span>{ui("High-confidence denominator", "Уверенных прогнозов")}</span><strong>{activeAnalysis.high_confidence_case_count}</strong></div><div><span>{ui("Unstable among them", "Из них нестабильных")}</span><strong>{activeAnalysis.high_confidence_unstable_case_count}</strong></div></div>}
    {activeAnalysis && <div className="data-table-wrap"><table className="data-table"><thead><tr><th>{ui("metric", "Метрика")}</th><th>{ui("mean", "Среднее")}</th><th>{ui("std", "Станд. отклонение")}</th><th>{ui("median", "Медиана")}</th><th title={ui("Interquartile range", "Межквартильный размах")}>IQR</th></tr></thead><tbody>{Object.entries(activeAnalysis.metric_distributions).map(([metric, values]) => <tr key={metric}><td>{metric}</td><td>{values.mean.toFixed(4)}</td><td>{values.std.toFixed(4)}</td><td>{values.median.toFixed(4)}</td><td>{values.iqr.toFixed(4)}</td></tr>)}</tbody></table></div>}
    {activeAnalysis && applicable && <><ChartSurface title={ui("Case Stability Map · selected-run agreement; red = high-confidence unstable", "Уверенность и поддержка решения другими моделями")} option={mapOption(activeAnalysis)} theme={theme}/>{uiLanguage === "ru" && <p className="property-description">Красным отмечены уверенные, но нестабильные решения. Неопределённая поддержка не изображается как ноль.</p>}{activeAnalysis.cases.some((caseEvidence) => caseEvidence.selected_run_agreement === null) && <p className="property-description">{ui("Cases without defined selected-run agreement are omitted from the map, not plotted as zero support.", "Примеры без определённой поддержки решения не показаны на графике.")}</p>}</>}
    {activeAnalysis && applicable && <section className="comparison-card">
      <div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">{ui("STABILITY-AWARE REVIEW GATE", "ПРАВИЛО РУЧНОЙ ПРОВЕРКИ")}</span><p>{ui("Validation-derived raw probabilities: confidence < 0.90, agreement < 0.80, or probability std > 0.15 ⇒ REVIEW. This is a capability comparison, not an A01 effectiveness result.", "Пример направляется на проверку, если уверенность ниже 90%, поддержка решения ниже 80% или разброс вероятностей выше 0,15. Используются исходные вероятности на валидации; это не доказательство снижения риска.")}</p></div>
        <Button view="outlined" disabled={!activeAnalysis || !!activePolicy || busy || !!gateRecoveryRequest || !!buildRecoveryRequest || project.read_only || analysisLoadState !== "loaded" || policyLoadState !== "loaded"} onClick={createGate} data-ruflex-action="stability.freeze">{activePolicy ? ui("Stability Gate frozen", "Правило сохранено") : ui("Freeze Stability Gate", "Зафиксировать правило проверки")}</Button></div>
      {gateRecoveryRequest && <div className="error" role="alert" data-testid="stability-gate-recovery"><strong>{ui("Stability Gate outcome is uncertain; recover by the exact analysis and frozen criteria.", "Ответ о сохранении не получен. Сначала проверьте, было ли правило сохранено.")}</strong><p>{gateRecoveryError}</p><Button view="outlined" disabled={busy} onClick={recoverGate}>{ui("Retry saved gate lookup", "Найти сохранённое правило")}</Button>{gateRecoveryNotFound && <Button view="outlined" disabled={busy} onClick={explicitlyFreezeGate}>{ui("Freeze this gate explicitly", "Повторить сохранение этого правила")}</Button>}</div>}
      {activePolicy && <><ChartSurface title={ui("Validation policy operating points (descriptive)", "Ошибки среди принятых прогнозов на валидации")} option={riskOption(activePolicy)} theme={theme}/><p className="property-description">{ui("No-review uses full coverage. Confidence-only and random references accept the same number of validation cases as the Stability Gate; they are descriptive, not a frozen A01 comparator.", "Без проверки принимаются все прогнозы. Отбор по уверенности и случайный отбор принимают столько же примеров, сколько правило устойчивости. Это описательное сравнение, не финальный результат A01.")}</p>
        <div className="data-table-wrap"><table className="data-table"><thead><tr><th>{ui("policy", "Правило")}</th><th>{ui("coverage", "Доля принятых")}</th><th>{ui("accepted risk", "Доля ошибок среди принятых")}</th></tr></thead><tbody>{activePolicy.risk_coverage.map((x) => <tr key={x.policy}><td>{ui(x.policy, policyLabel(x.policy))}</td><td>{(x.coverage * 100).toFixed(1)}%</td><td>{x.accepted_risk === null ? "—" : `${(x.accepted_risk * 100).toFixed(1)}%`}</td></tr>)}</tbody></table></div></>}
    </section>}
    {activeAnalysis && applicable && <section className="comparison-card"><span className="eyebrow">{ui("CASE INSPECTOR", "ОТДЕЛЬНЫЙ ПРИМЕР")}</span><select aria-label={ui("Stability case", "Пример для сравнения решений")} value={selected?.case_id ?? ""} onChange={(event) => setCaseId(event.target.value)}>{activeAnalysis.cases.map((x) => <option key={x.case_id} value={x.case_id}>{x.case_id}</option>)}</select>{selected && <>
      <p><strong>{ui("Selected run", "Выбранная модель")}: {selected.selected_run_class ?? "N/A"} · {ui("confidence", "уверенность")} {confidence(selected.selected_run_probability).toFixed(2)}</strong> · {ui("selected decision supported by", "Решение поддержали")} {selected.selected_run_agreement === null ? "N/A" : `${Math.round(selected.selected_run_agreement * selected.run_support_count)}/${selected.run_support_count}${ui(" independent fits", "")}`} · {ui("selected-run agreement", "поддержка решения")} {selected.selected_run_agreement === null ? "N/A" : `${(selected.selected_run_agreement * 100).toFixed(0)}%`} · {ui("majority consensus", "согласие с большинством")} {selected.majority_class_agreement === null ? "N/A" : `${(selected.majority_class_agreement * 100).toFixed(0)}%`} · {ui("std", "разброс")} {selected.std_probability.toFixed(3)}</p>
      {decision && <p><strong>{uiStatus(decision.disposition)}</strong> · {decision.reasons.map(uiStatus).join(", ") || ui("all frozen criteria met", "все сохранённые критерии выполнены")}</p>}
      <details open={uiLanguage === "en"}><summary>{ui("Independent fits", "Прогнозы всех обучений")}</summary><div className="data-table-wrap"><table className="data-table"><thead><tr><th>{ui("training run", "Обучение")}</th><th>{ui("probability", "Вероятность")}</th><th>{ui("class at frozen threshold", "Класс по сохранённому порогу")}</th></tr></thead><tbody>{Object.entries(selected.run_probabilities).map(([runId, probability]) => <tr key={runId}><td>{runId.slice(0, 12)}</td><td>{probability.toFixed(4)}</td><td>{selected.run_labels[runId]}</td></tr>)}</tbody></table></div></details></>}
    </section>}
    {activeAnalysis && <details open={uiLanguage === "en"}><summary>{ui("Scientific scope", "Научные ограничения")}</summary><small>{activeAnalysis.scientific_note}</small></details>}
    {error && <div className="error" role="alert">{error}</div>}
  </section>;
}
