import { EChartsOption } from "echarts";
import { useMemo, useState } from "react";
import {
  AnalysisComparison,
  AnalysisEvaluation,
  CalibrationTransform,
  DecisionThresholdPolicy,
  FinalTestEvaluation,
  DatasetState,
  FISSpec,
  ProjectSummary,
  SliceAnalysis,
  SelectivePredictionPolicy,
  SliceDefinition,
  TrainingRun,
  TrainingStudy,
  studioApi,
} from "../../api";
import { ChartSurface } from "../../charts/ChartSurface";
import { Button, EmptyState, StatusBadge } from "../../components/StudioPrimitives";
import { StudioTheme } from "../../design/tokens";

function calibrationOption(
  run: TrainingRun,
  evaluation: AnalysisEvaluation | null,
  calibration: CalibrationTransform | null,
): EChartsOption {
  const rawBins = evaluation?.calibration_bins ?? run.calibration;
  const calibratedBins = calibration?.calibration_bins ?? [];
  return {
    tooltip: { trigger: "axis" },
    legend: { data: calibratedBins.length ? ["raw", "calibrated", "ideal"] : ["raw", "ideal"] },
    grid: { left: 50, right: 20, top: 38, bottom: 34 },
    xAxis: { type: "value", min: 0, max: 1, name: "mean predicted probability" },
    yAxis: { type: "value", min: 0, max: 1, name: "observed rate" },
    series: [
      { name: "raw", type: "scatter", symbolSize: 10, data: rawBins.map((bin) => [bin.mean_probability, bin.observed_positive_rate]) },
      ...(calibratedBins.length
        ? [{ name: "calibrated", type: "scatter" as const, symbolSize: 10, data: calibratedBins.map((bin) => [bin.mean_probability, bin.observed_positive_rate]) }]
        : []),
      { name: "ideal", type: "line", showSymbol: false, data: [[0, 0], [1, 1]] },
    ],
  };
}

function regressionOption(run: TrainingRun): EChartsOption {
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 52, right: 20, top: 24, bottom: 34 },
    xAxis: { type: "value", name: "target", scale: true },
    yAxis: { type: "value", name: "prediction", scale: true },
    series: [{ type: "scatter", symbolSize: 8, data: run.prediction_preview.map((row) => [row.target, row.prediction]) }],
  };
}

function comparisonOption(comparison: AnalysisComparison): EChartsOption {
  const taskMetrics = comparison.task === "binary_classification"
    ? ["accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc", "brier", "ece", "calibrated_brier", "calibrated_ece"]
    : ["mae", "mse", "rmse", "r2"];
  const metricKeys = taskMetrics.filter((key) =>
    comparison.metric_rows.every((row) => typeof row[key] === "number"),
  );
  return {
    tooltip: { trigger: "axis" },
    legend: { data: metricKeys },
    grid: { left: 50, right: 22, top: 36, bottom: 36 },
    xAxis: { type: "category", name: "subject", data: comparison.metric_rows.map((row) => `${String(row.model_kind)} · ${String(row.seed ?? "manual")}`) },
    yAxis: { type: "value", name: "validation metric", scale: true },
    series: metricKeys.map((key) => ({ name: key, type: "line", symbolSize: 8, data: comparison.metric_rows.map((row) => Number(row[key])) })),
  };
}

type Props = {
  project: ProjectSummary;
  dataset: DatasetState | null;
  fis: FISSpec | null;
  run: TrainingRun | null;
  runs: TrainingRun[];
  study: TrainingStudy | null;
  evaluation: AnalysisEvaluation | null;
  calibrationTransform: CalibrationTransform | null;
  decisionThreshold: DecisionThresholdPolicy | null;
  finalTestEvaluation: FinalTestEvaluation | null;
  comparison: AnalysisComparison | null;
  sliceAnalysis: SliceAnalysis | null;
  selectivePolicy: SelectivePredictionPolicy | null;
  theme: StudioTheme;
  onEvaluation: (evaluation: AnalysisEvaluation) => void;
  onCalibration: (calibration: CalibrationTransform | null) => void;
  onThreshold: (threshold: DecisionThresholdPolicy | null) => void;
  onFinalTest: (evaluation: FinalTestEvaluation | null) => void;
  onComparison: (comparison: AnalysisComparison) => void;
  onSliceAnalysis: (analysis: SliceAnalysis) => void;
  onSelectivePolicy: (policy: SelectivePredictionPolicy | null) => void;
};

export function EvaluationWorkspace({
  project,
  dataset,
  fis,
  run,
  runs,
  study,
  evaluation,
  calibrationTransform,
  decisionThreshold,
  finalTestEvaluation,
  comparison,
  sliceAnalysis,
  selectivePolicy,
  theme,
  onEvaluation,
  onCalibration,
  onThreshold,
  onFinalTest,
  onComparison,
  onSliceAnalysis,
  onSelectivePolicy,
}: Props) {
  const [saving, setSaving] = useState(false);
  const [calibrating, setCalibrating] = useState(false);
  const [thresholding, setThresholding] = useState(false);
  const [selectiveCutoff, setSelectiveCutoff] = useState("0.80");
  const [selectingReview, setSelectingReview] = useState(false);
  const [finalTesting, setFinalTesting] = useState(false);
  const [finalTestConfirmed, setFinalTestConfirmed] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [includeManualFis, setIncludeManualFis] = useState(false);
  const [sliceRunning, setSliceRunning] = useState(false);
  const [sliceName, setSliceName] = useState("Validation slice");
  const [sliceKind, setSliceKind] = useState<SliceDefinition["kind"]>("numeric_range");
  const [sliceField, setSliceField] = useState("");
  const [sliceValues, setSliceValues] = useState("");
  const [sliceMinimum, setSliceMinimum] = useState("");
  const [sliceMaximum, setSliceMaximum] = useState("");
  const [sliceStart, setSliceStart] = useState("");
  const [sliceEnd, setSliceEnd] = useState("");
  const [sliceRows, setSliceRows] = useState("");
  const [sliceMetric, setSliceMetric] = useState("");
  const [error, setError] = useState<string | null>(null);

  const runId = run?.run_id ?? null;
  const activeEvaluation = evaluation && runId && evaluation.run_id === runId ? evaluation : null;
  const activeCalibration = calibrationTransform && activeEvaluation
    && calibrationTransform.evaluation_id === activeEvaluation.evaluation_id
    ? calibrationTransform
    : null;
  const activeThreshold = decisionThreshold && activeEvaluation
    && decisionThreshold.evaluation_id === activeEvaluation.evaluation_id
    ? decisionThreshold
    : null;
  const activeFinalTest = finalTestEvaluation && finalTestEvaluation.run_id === runId
    ? finalTestEvaluation
    : null;

  const option = useMemo(() => {
    if (!run) return null;
    return run.task === "binary_classification"
      ? calibrationOption(run, activeEvaluation, activeCalibration)
      : regressionOption(run);
  }, [run, activeEvaluation, activeCalibration]);

  if (!run || !option || !runId) {
    return <section className="feature-workspace"><EmptyState title="No trained run">Train a model in Experiment before evaluating it.</EmptyState></section>;
  }

  async function ensureEvaluation(): Promise<AnalysisEvaluation> {
    if (activeEvaluation) return activeEvaluation;
    const created = await studioApi.createAnalysisEvaluation(project.session_id, runId!);
    onEvaluation(created);
    onCalibration(null);
    onThreshold(null);
    return created;
  }

  async function saveEvaluation() {
    setSaving(true);
    setError(null);
    try {
      const created = await studioApi.createAnalysisEvaluation(project.session_id, runId!);
      onEvaluation(created);
      onCalibration(null);
      onThreshold(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save validation evaluation");
    } finally {
      setSaving(false);
    }
  }

  async function fitCalibration() {
    setCalibrating(true);
    setError(null);
    try {
      const current = await ensureEvaluation();
      const fitted = await studioApi.fitAnalysisCalibration(project.session_id, current.evaluation_id);
      onCalibration(fitted);
      onThreshold(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not fit validation calibration");
    } finally {
      setCalibrating(false);
    }
  }

  async function selectThreshold() {
    setThresholding(true);
    setError(null);
    try {
      const current = await ensureEvaluation();
      const selected = await studioApi.selectAnalysisThreshold(
        project.session_id,
        current.evaluation_id,
        activeCalibration?.calibration_id ?? null,
      );
      onThreshold(selected);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not select validation decision threshold");
    } finally {
      setThresholding(false);
    }
  }

  async function selectReviewPolicy() {
    setSelectingReview(true);
    setError(null);
    try {
      const current = await ensureEvaluation();
      if (!activeThreshold) throw new Error("Select a validation DecisionThreshold before creating a selective policy.");
      onSelectivePolicy(await studioApi.createSelectivePolicy(project.session_id, current.evaluation_id, Number(selectiveCutoff), activeCalibration?.calibration_id ?? null, activeThreshold.threshold_id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not select validation review policy");
    } finally {
      setSelectingReview(false);
    }
  }

  async function evaluateFinalTest() {
    if (!activeEvaluation) {
      setError("Save the validation Evaluation before opening the final test.");
      return;
    }
    if (!finalTestConfirmed) {
      setError("Confirm that model selection, calibration and threshold policy are frozen before final-test access.");
      return;
    }
    if (run!.task === "binary_classification" && !activeThreshold) {
      setError("Select and persist the validation decision threshold before final-test evaluation.");
      return;
    }
    setFinalTesting(true);
    setError(null);
    try {
      const result = await studioApi.evaluateFinalTest(
        project.session_id,
        activeEvaluation.evaluation_id,
        activeThreshold?.probability_source === "calibrated" ? activeCalibration?.calibration_id ?? null : null,
        activeThreshold?.threshold_id ?? null,
        selectivePolicy?.policy_id ?? null,
      );
      onFinalTest(result);
      setFinalTestConfirmed(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not evaluate frozen final-test split");
    } finally {
      setFinalTesting(false);
    }
  }

  async function saveStudyComparison() {
    if (!study) return;
    setComparing(true);
    setError(null);
    try {
      onComparison(await studioApi.createAnalysisComparison(project.session_id, study.seed_runs.map((seedRun) => seedRun.run_id)));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save validation comparison");
    } finally {
      setComparing(false);
    }
  }

  async function saveSelectedComparison() {
    if (selectedRunIds.length < 2) {
      setError("Select at least two compatible completed runs.");
      return;
    }
    setComparing(true);
    setError(null);
    try {
      onComparison(await studioApi.createAnalysisComparison(project.session_id, selectedRunIds, includeManualFis));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save validation comparison");
    } finally {
      setComparing(false);
    }
  }

  async function runSliceAnalysis() {
    if (!dataset) {
      setError("Dataset state is required for Slice Lab.");
      return;
    }
    setSliceRunning(true);
    setError(null);
    try {
      const current = await ensureEvaluation();
      const field = sliceField || dataset.contract.feature_columns[0] || dataset.profile.columns[0]?.name || "";
      const definition: SliceDefinition = { name: sliceName.trim() || "Validation slice", kind: sliceKind };
      if (sliceKind === "manual") {
        definition.source_rows = sliceRows.split(",").map((value) => Number(value.trim())).filter(Number.isInteger);
      } else {
        definition.field = field;
      }
      if (sliceKind === "categorical" || sliceKind === "group") {
        definition.values = sliceValues.split(",").map((value) => value.trim()).filter(Boolean);
      } else if (sliceKind === "numeric_range") {
        definition.minimum = sliceMinimum.trim() === "" ? null : Number(sliceMinimum);
        definition.maximum = sliceMaximum.trim() === "" ? null : Number(sliceMaximum);
      } else if (sliceKind === "temporal") {
        definition.start = sliceStart.trim() || null;
        definition.end = sliceEnd.trim() || null;
      }
      const metric = sliceMetric || (run!.task === "binary_classification" ? "f1" : "rmse");
      onSliceAnalysis(await studioApi.createSliceAnalysis(project.session_id, current.evaluation_id, metric, [definition]));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create Slice Analysis");
    } finally {
      setSliceRunning(false);
    }
  }

  const metrics = Object.entries(activeEvaluation?.metrics ?? run.validation_metrics);
  const calibratedByRow = new Map(activeCalibration?.predictions.map((item) => [item.row, item.calibrated_probability]) ?? []);
  const decisionByRow = new Map(activeThreshold?.decisions.map((item) => [item.row, item.predicted_label]) ?? []);
  const matrix = activeThreshold?.confusion_matrix ?? activeEvaluation?.confusion_matrix ?? run.confusion_matrix;
  const displayRows = activeEvaluation?.prediction_preview ?? run.prediction_preview;

  return <section className="feature-workspace evaluation-workspace">
    <div className="feature-toolbar">
      <div>
        <span className="eyebrow">VALIDATION EVIDENCE</span>
        <h2>Evaluate trained model</h2>
        <p>{activeEvaluation?.scientific_note ?? run.scientific_note}</p>
      </div>
      <div className="toolbar-actions">
        <StatusBadge tone={activeFinalTest ? "danger" : "warning"}>{activeFinalTest ? "final test evaluated" : "final test locked"}</StatusBadge>
        {study && <Button view="outlined" disabled={comparing || project.read_only} onClick={saveStudyComparison}>{comparing ? "Comparing…" : "Compare study seeds"}</Button>}
        <Button view="outlined" disabled={saving || project.read_only} onClick={saveEvaluation}>{saving ? "Saving…" : activeEvaluation ? "Save evaluation revision" : "Save validation evidence"}</Button>
        {run.task === "binary_classification" && <Button view="outlined" disabled={calibrating || project.read_only || Boolean(finalTestEvaluation)} onClick={fitCalibration}>{calibrating ? "Fitting…" : activeCalibration ? "Refit calibration" : "Fit validation calibration"}</Button>}
        {run.task === "binary_classification" && <Button view="action" disabled={thresholding || project.read_only || Boolean(finalTestEvaluation)} onClick={selectThreshold}>{thresholding ? "Selecting…" : activeThreshold ? "Reselect threshold" : `Select F1 threshold (${activeCalibration ? "calibrated" : "raw"})`}</Button>}
      </div>
    </div>

    <div className="metric-grid">
      {metrics.map(([name, value]) => <div className="metric-card" key={name}><span>{name}</span><strong>{Number(value).toFixed(4)}</strong><small>validation · raw model</small></div>)}
      {activeCalibration && <>
        <div className="metric-card"><span>Brier calibrated</span><strong>{activeCalibration.brier_after.toFixed(4)}</strong><small>{activeCalibration.brier_before.toFixed(4)} before</small></div>
        <div className="metric-card"><span>ECE calibrated</span><strong>{activeCalibration.ece_after.toFixed(4)}</strong><small>{activeCalibration.ece_before.toFixed(4)} before</small></div>
      </>}
      {activeThreshold && <div className="metric-card"><span>Decision threshold</span><strong>{activeThreshold.selected_threshold.toFixed(2)}</strong><small>validation F1 {activeThreshold.selection_result.toFixed(4)}</small></div>}
    </div>

    <div className="evaluation-grid">
      <ChartSurface title={run.task === "binary_classification" ? "Validation reliability" : "Validation predictions"} option={option} theme={theme} />
      {matrix ? <section className="confusion-card">
        <div><span className="eyebrow">CONFUSION MATRIX · VALIDATION</span><h3>Threshold {activeThreshold?.selected_threshold.toFixed(2) ?? "0.50"}</h3></div>
        <div className="confusion-grid">
          <div><span>TN</span><strong>{matrix.true_negative}</strong></div>
          <div><span>FP</span><strong>{matrix.false_positive}</strong></div>
          <div><span>FN</span><strong>{matrix.false_negative}</strong></div>
          <div><span>TP</span><strong>{matrix.true_positive}</strong></div>
        </div>
      </section> : <section className="confusion-card"><span className="eyebrow">REGRESSION</span><h3>Residual evidence</h3><p>Complete validation predictions are persisted; the table below shows the first rows.</p></section>}
    </div>

    {run.task === "binary_classification" && <section className="comparison-card">
      <span className="eyebrow">DECISION PROVENANCE · VALIDATION ONLY</span>
      <h3>Probability → calibration → threshold → class</h3>
      <p>
        Raw model probability {activeCalibration ? `→ Platt transform ${activeCalibration.calibration_id.slice(0, 8)}` : "→ calibration not fitted"}
        {activeThreshold ? ` → threshold ${activeThreshold.selected_threshold.toFixed(2)} (${activeThreshold.probability_source})` : " → threshold not selected"}.
        Final-test data remain locked throughout this chain.
      </p>
      {activeCalibration && <small className="mono">fit evidence {activeCalibration.fit_sample_identity.slice(0, 36)}… · n={activeCalibration.fit_sample_count}</small>}
      {activeThreshold && <small className="mono">threshold {activeThreshold.threshold_id.slice(0, 12)} · objective {activeThreshold.objective} · source {activeThreshold.source_split}</small>}
    </section>}

    {run.task === "binary_classification" && <section className="comparison-card">
      <span className="eyebrow">SELECTIVE PREDICTION · VALIDATION ONLY</span><h3>Accept confident cases; route the rest to review</h3>
      <p>This confidence cutoff is independent of the class threshold. It tunes ACCEPT / REVIEW coverage on validation evidence and never opens the final test.</p>
      <label className="field-label">Confidence cutoff<input aria-label="Selective confidence cutoff" type="number" min="0.5" max="1" step="0.05" value={selectiveCutoff} onChange={(event) => setSelectiveCutoff(event.target.value)} /></label>
      <Button view="action" disabled={selectingReview || project.read_only || Boolean(finalTestEvaluation) || !activeThreshold} onClick={selectReviewPolicy}>{selectingReview ? "Selecting…" : "Save ACCEPT / REVIEW policy"}</Button>
      {!activeThreshold && <small>Select the validation class threshold first; accepted risk uses that exact threshold, never an implicit 0.50.</small>}
      {selectivePolicy && <><p><StatusBadge tone="warning">REVIEW BELOW {selectivePolicy.confidence_cutoff.toFixed(2)}</StatusBadge> ACCEPT at or above cutoff · class threshold {selectivePolicy.class_threshold.toFixed(2)} · {selectivePolicy.probability_source} probability.</p><small className="mono">threshold {selectivePolicy.class_threshold_id.slice(0, 12)} · validation cases {selectivePolicy.fit_sample_identity.slice(0, 24)}…</small><div className="data-table-wrap"><table className="data-table"><thead><tr><th>confidence</th><th>coverage</th><th>accepted risk</th><th>accepted</th></tr></thead><tbody>{selectivePolicy.risk_coverage.map((point) => <tr key={point.confidence_cutoff}><td>{point.confidence_cutoff.toFixed(2)}</td><td>{(point.coverage * 100).toFixed(1)}%</td><td>{point.accepted_risk === null ? "—" : `${(point.accepted_risk * 100).toFixed(1)}%`}</td><td>{point.accepted_count}</td></tr>)}</tbody></table></div><small>{selectivePolicy.scientific_note}</small></>}
    </section>}

    <section>
      <h3>Validation prediction evidence</h3>
      <div className="data-table-wrap"><table className="data-table"><thead><tr><th>row</th><th>target</th><th>{run.task === "binary_classification" ? "logit" : "prediction"}</th>{run.task === "binary_classification" ? <><th>raw probability</th><th>calibrated probability</th><th>final class</th></> : <th>residual</th>}</tr></thead><tbody>
        {displayRows.slice(0, 20).map((row) => <tr key={row.row}><td>{row.row}</td><td>{row.target.toFixed(5)}</td><td>{row.prediction.toFixed(5)}</td>{run.task === "binary_classification" ? <><td>{row.probability?.toFixed(5) ?? "—"}</td><td>{calibratedByRow.get(row.row)?.toFixed(5) ?? "not fitted"}</td><td>{decisionByRow.get(row.row) ?? row.predicted_label ?? "—"}</td></> : <td>{row.residual?.toFixed(5) ?? "—"}</td>}</tr>)}
      </tbody></table></div>
      <small>{activeEvaluation ? `${activeEvaluation.validation_row_count} validation rows persisted; first ${Math.min(20, displayRows.length)} displayed.` : "Save validation evidence to persist the complete evaluation object."}</small>
    </section>

    <div className="evaluation-footer"><StatusBadge tone="success">validation evaluated</StatusBadge><span>{activeEvaluation ? `Evaluation ${activeEvaluation.evaluation_id.slice(0, 12)} · ` : "Unsaved analysis · "}Run {run.run_id.slice(0, 12)} · model {run.model_artifact_sha256.slice(0, 12)} · {activeFinalTest ? `${activeFinalTest.test_row_count} final-test rows evaluated with frozen policy` : `${run.split.test_count} final-test rows remain locked`}</span></div>

    <section className="comparison-card final-test-gate">
      <span className="eyebrow">FINAL TEST · EXPLICIT FROZEN-POLICY EVALUATION</span>
      <h3>{activeFinalTest ? "Final-test evidence persisted separately" : "Final test remains closed"}</h3>
      {activeFinalTest ? <>
        <div className="comparison-protocol-line"><StatusBadge tone="danger">FINAL TEST EVALUATED</StatusBadge><span className="mono">{activeFinalTest.final_test_id.slice(0, 12)} · n={activeFinalTest.test_row_count}</span></div>
        <div className="metric-grid">{Object.entries(activeFinalTest.metrics).map(([name, value]) => <div className="metric-card" key={`final-${name}`}><span>{name}</span><strong>{Number(value).toFixed(4)}</strong><small>FINAL TEST · frozen policy</small></div>)}</div>
        <p>{activeFinalTest.scientific_note}</p>
        <small className="mono">policy {activeFinalTest.policy_identity.slice(0, 36)}… · cases {(activeFinalTest.test_case_identity ?? activeFinalTest.test_sample_identity).slice(0, 36)}…</small>
        {activeFinalTest.dataset_test_unlock_at && <small className="mono">dataset test gate opened {new Date(activeFinalTest.dataset_test_unlock_at).toLocaleString()} · only policies frozen before this boundary and using the same holdout cases remain eligible</small>}
      </> : <>
        <p>Validation remains the only evidence used for model selection, probability calibration and threshold selection. The first final-test access freezes the dataset-level eligibility boundary. Additional pre-specified policies may be evaluated only if they were already frozen and reconstruct the same holdout rows.</p>
        <label className="final-test-confirm"><input type="checkbox" checked={finalTestConfirmed} onChange={(event) => setFinalTestConfirmed(event.target.checked)} />I confirm this policy was frozen before final-test access; final-test results will not be used to retune or create another eligible policy.</label>
        <Button view="action" disabled={project.read_only || finalTesting || !activeEvaluation || !finalTestConfirmed || (run.task === "binary_classification" && !activeThreshold)} onClick={evaluateFinalTest}>{finalTesting ? "Evaluating final test…" : "Evaluate frozen final test"}</Button>
        {run.task === "binary_classification" && !activeThreshold && <small>Select a validation-derived decision threshold first. Calibration is optional; a calibrated threshold automatically requires its persisted calibration transform.</small>}
      </>}
    </section>

    {comparison && <section className="comparison-card"><span className="eyebrow">SAVED MODEL COMPARISON · VALIDATION ONLY</span><h3>{comparison.metric_rows.length} compatible trained runs</h3><div className="comparison-protocol-line"><StatusBadge tone={comparison.validation_alignment === "same_cases" ? "success" : comparison.validation_alignment === "mixed_cases" ? "warning" : "info"}>{comparison.validation_alignment === "same_cases" ? "same validation cases" : comparison.validation_alignment === "mixed_cases" ? "mixed validation cases" : "validation alignment unknown"}</StatusBadge>{comparison.dataset_fingerprint && <span className="mono">dataset {comparison.dataset_fingerprint.slice(0, 12)}</span>}</div><div className="data-table-wrap"><table className="data-table"><thead><tr>{[...new Set(comparison.metric_rows.flatMap((row) => Object.keys(row)))].map((key) => <th key={key}>{key}</th>)}</tr></thead><tbody>{comparison.metric_rows.map((row) => <tr key={String(row.subject_id ?? row.run_id)}>{[...new Set(comparison.metric_rows.flatMap((candidate) => Object.keys(candidate)))].map((key) => <td key={key}>{typeof row[key] === "number" ? Number(row[key]).toFixed(4) : row[key] === undefined ? "—" : String(row[key])}</td>)}</tr>)}</tbody></table></div><p>{comparison.scientific_note}</p></section>}
    {comparison && comparison.metric_rows.length > 0 && <ChartSurface title="Shared validation metrics by run" option={comparisonOption(comparison)} theme={theme} />}
    {(runs.length > 1 || (runs.length > 0 && fis)) && <section className="comparison-card"><span className="eyebrow">MODEL COMPARISON · VALIDATION ONLY</span><h3>Compare compatible models on declared validation evidence</h3>{fis && <label className="comparison-choice"><input type="checkbox" checked={includeManualFis} onChange={(event) => setIncludeManualFis(event.target.checked)} />Manual {fis.system_type} FIS · semantic {(fis.semantic_hash ?? "unsaved").slice(0, 12)} · {fis.rules.length} rules</label>}{runs.map((candidate) => <label className="comparison-choice" key={candidate.run_id}><input type="checkbox" checked={selectedRunIds.includes(candidate.run_id)} onChange={(event) => setSelectedRunIds((current) => event.target.checked ? [...current, candidate.run_id] : current.filter((id) => id !== candidate.run_id))} />{candidate.model_kind} · seed {candidate.seed} · {candidate.run_id.slice(0, 12)} · nodes {typeof candidate.model_spec.node_count === "number" ? candidate.model_spec.node_count : "—"}</label>)}<Button view="outlined" disabled={comparing || project.read_only || selectedRunIds.length + (includeManualFis ? 1 : 0) < 2 || (includeManualFis && selectedRunIds.length < 1)} onClick={saveSelectedComparison}>{comparing ? "Comparing…" : `Compare ${selectedRunIds.length + (includeManualFis ? 1 : 0)} selected models`}</Button><p>Manual FIS is evaluated on exactly the persisted validation cases of the selected trained run(s). If selected runs use different validation cases, RuFLEX blocks adding the FIS instead of pretending the comparison is paired. FIS scores are not labeled calibrated probabilities.</p></section>}

    <section className="comparison-card slice-lab">
      <span className="eyebrow">SLICE LAB · VALIDATION ONLY</span>
      <h3>Measure a declared subgroup without touching final test</h3>
      <div className="slice-form-grid">
        <label className="field-label">Name<input aria-label="Slice name" value={sliceName} onChange={(event) => setSliceName(event.target.value)} /></label>
        <label className="field-label">Type<select aria-label="Slice type" value={sliceKind} onChange={(event) => setSliceKind(event.target.value as SliceDefinition["kind"])}><option value="numeric_range">Numeric range</option><option value="categorical">Categorical</option><option value="group">Group</option><option value="temporal">Temporal</option><option value="manual">Manual source rows</option></select></label>
        {sliceKind !== "manual" && <label className="field-label">Field<select aria-label="Slice field" value={sliceField || dataset?.contract.feature_columns[0] || ""} onChange={(event) => setSliceField(event.target.value)}>{dataset?.profile.columns.map((column) => <option value={column.name} key={column.name}>{column.name}</option>)}</select></label>}
        {(sliceKind === "categorical" || sliceKind === "group") && <label className="field-label">Values<input aria-label="Slice values" placeholder="A, B" value={sliceValues} onChange={(event) => setSliceValues(event.target.value)} /></label>}
        {sliceKind === "numeric_range" && <><label className="field-label">Minimum<input aria-label="Slice minimum" type="number" value={sliceMinimum} onChange={(event) => setSliceMinimum(event.target.value)} /></label><label className="field-label">Maximum<input aria-label="Slice maximum" type="number" value={sliceMaximum} onChange={(event) => setSliceMaximum(event.target.value)} /></label></>}
        {sliceKind === "temporal" && <><label className="field-label">Start<input aria-label="Slice start" placeholder="2026-01-01" value={sliceStart} onChange={(event) => setSliceStart(event.target.value)} /></label><label className="field-label">End<input aria-label="Slice end" placeholder="2026-12-31" value={sliceEnd} onChange={(event) => setSliceEnd(event.target.value)} /></label></>}
        {sliceKind === "manual" && <label className="field-label">Original source rows<input aria-label="Slice source rows" placeholder="2, 7, 11" value={sliceRows} onChange={(event) => setSliceRows(event.target.value)} /></label>}
        <label className="field-label">Metric<select aria-label="Slice metric" value={sliceMetric || (run.task === "binary_classification" ? "f1" : "rmse")} onChange={(event) => setSliceMetric(event.target.value)}>{run.task === "binary_classification" ? <><option value="f1">F1</option><option value="accuracy">Accuracy</option><option value="precision">Precision</option><option value="recall">Recall</option><option value="brier">Brier</option></> : <><option value="rmse">RMSE</option><option value="mae">MAE</option><option value="mse">MSE</option><option value="r2">R²</option></>}</select></label>
      </div>
      <Button view="outlined" disabled={sliceRunning || project.read_only || !dataset} onClick={runSliceAnalysis}>{sliceRunning ? "Calculating…" : "Run and persist slice"}</Button>
      {sliceAnalysis && <div className="data-table-wrap"><table className="data-table"><thead><tr><th>slice</th><th>kind</th><th>N</th><th>metric</th><th>value</th><th>overall</th><th>delta</th><th>metric status</th><th>declared scope</th></tr></thead><tbody>{sliceAnalysis.results.map((result) => <tr key={`${sliceAnalysis.analysis_id}-${result.name}`}><td>{result.name}</td><td>{result.kind}</td><td>{result.n}</td><td>{result.metric}</td><td>{result.value === null ? "—" : result.value.toFixed(4)}</td><td>{result.overall_value.toFixed(4)}</td><td>{result.delta_vs_overall === null ? "—" : result.delta_vs_overall.toFixed(4)}</td><td>{result.status}{result.warning ? ` · ${result.warning}` : ""}</td><td><StatusBadge tone={result.scope_disposition === "ALLOW" ? "success" : result.scope_disposition === "BLOCK" ? "danger" : "warning"}>{result.scope_disposition}</StatusBadge>{result.scope_reasons.length > 0 && <small className="slice-scope-reason">{result.scope_reasons.join(" ")}</small>}</td></tr>)}</tbody></table><p>{sliceAnalysis.generalization_contract_id ? `Scope classifications use GeneralizationContract ${sliceAnalysis.generalization_contract_id.slice(0, 12)}. ` : "No GeneralizationContract was linked; scope remains undeclared. "}{sliceAnalysis.scientific_note}</p></div>}
    </section>
    {error && <div className="error" role="alert">{error}</div>}
  </section>;
}
