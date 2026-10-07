import { EChartsOption } from "echarts";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  AnalysisComparison,
  AnalysisEvaluation,
  CalibrationTransform,
  DecisionThresholdPolicy,
  FinalTestEvaluation,
  DatasetState,
  FISSpec,
  ProjectSummary,
  ProductApiError,
  SliceAnalysis,
  SelectivePredictionPolicy,
  StabilityGatePolicy,
  SliceDefinition,
  TrainingRun,
  TrainingStudy,
  studioApi,
} from "../../api";
import { ChartSurface } from "../../charts/ChartSurface";
import { Button, EmptyState, StatusBadge } from "../../components/StudioPrimitives";
import { StudioTheme } from "../../design/tokens";

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.entries(value as Record<string, unknown>).sort(([left], [right]) => left.localeCompare(right)).map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`).join(",")}}`;
  }
  return JSON.stringify(value) ?? "undefined";
}

type ValidationPolicyRecovery =
  | { kind: "calibration"; evaluationId: string; error: string; notFound: boolean }
  | { kind: "threshold"; evaluationId: string; calibrationId: string | null; error: string; notFound: boolean }
  | { kind: "selective"; evaluationId: string; confidenceCutoff: number; calibrationId: string | null; thresholdId: string; error: string; notFound: boolean };
type ComparisonRecovery = { runIds: string[]; fisId: string | null; fisSemanticHash: string | null; error: string; notFound: boolean };
type FinalTestRecovery = { evaluationId: string; calibrationId: string | null; thresholdId: string | null; selectivePolicyId: string | null; stabilityGatePolicyId: string | null; error: string };

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

function operatingCurveOption(
  points: Array<{ x: number; y: number; threshold: number | null }>,
  xName: string,
  yName: string,
  ideal: boolean,
): EChartsOption {
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 58, right: 20, top: 24, bottom: 42 },
    xAxis: { type: "value", min: 0, max: 1, name: xName },
    yAxis: { type: "value", min: 0, max: 1, name: yName },
    series: [
      { name: "persisted evidence", type: "line", showSymbol: false, data: points.map((point) => [point.x, point.y]) },
      ...(ideal ? [{ name: "chance", type: "line" as const, showSymbol: false, lineStyle: { type: "dashed" as const }, data: [[0, 0], [1, 1]] }] : []),
    ],
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
  datasetHydrationStatus?: "idle" | "loading" | "none" | "available" | "error";
  datasetHydrationError?: string | null;
  onRetryDatasetHydration?: () => void;
  fis: FISSpec | null;
  modelContextStatus?: "idle" | "loading" | "loaded" | "error";
  modelContextError?: string | null;
  onRetryModelContext?: () => void;
  run: TrainingRun | null;
  runs: TrainingRun[];
  runListStatus: "idle" | "loading" | "loaded" | "error";
  runListError: string | null;
  onRetryRunList: () => void;
  study: TrainingStudy | null;
  evaluation: AnalysisEvaluation | null;
  evaluationStatus: "idle" | "loading" | "none" | "available" | "error";
  evaluationError: string | null;
  onRetryEvaluation: () => void;
  validationPolicyEvidenceStatus: "idle" | "loading" | "available" | "error";
  validationPolicyEvidenceError: string | null;
  onRetryValidationPolicyEvidence: () => void;
  calibrationTransform: CalibrationTransform | null;
  decisionThreshold: DecisionThresholdPolicy | null;
  finalTestEvaluation: FinalTestEvaluation | null;
  finalTestEvidenceStatus: "idle" | "loading" | "none" | "available" | "error";
  finalTestEvidenceError: string | null;
  onRetryFinalTestEvidence: () => void;
  comparison: AnalysisComparison | null;
  comparisonHydrationStatus?: "idle" | "loading" | "none" | "available" | "error";
  comparisonHydrationError?: string | null;
  onRetryComparison?: () => void;
  sliceAnalysis: SliceAnalysis | null;
  sliceAnalysisHydrationStatus?: "idle" | "loading" | "none" | "available" | "error";
  sliceAnalysisHydrationError?: string | null;
  onRetrySliceAnalysis?: () => void;
  selectivePolicy: SelectivePredictionPolicy | null;
  stabilityGatePolicy: StabilityGatePolicy | null;
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
  datasetHydrationStatus = "available",
  datasetHydrationError = null,
  onRetryDatasetHydration = () => undefined,
  fis,
  modelContextStatus = "loaded",
  modelContextError = null,
  onRetryModelContext,
  run,
  runs,
  runListStatus,
  runListError,
  onRetryRunList,
  study,
  evaluation,
  evaluationStatus,
  evaluationError,
  onRetryEvaluation,
  validationPolicyEvidenceStatus,
  validationPolicyEvidenceError,
  onRetryValidationPolicyEvidence,
  calibrationTransform,
  decisionThreshold,
  finalTestEvaluation,
  finalTestEvidenceStatus,
  finalTestEvidenceError,
  onRetryFinalTestEvidence,
  comparison,
  comparisonHydrationStatus = "available",
  comparisonHydrationError = null,
  onRetryComparison,
  sliceAnalysis,
  sliceAnalysisHydrationStatus = "available",
  sliceAnalysisHydrationError = null,
  onRetrySliceAnalysis,
  selectivePolicy,
  stabilityGatePolicy,
  theme,
  onEvaluation,
  onCalibration,
  onThreshold,
  onFinalTest,
  onComparison,
  onSliceAnalysis,
  onSelectivePolicy,
}: Props) {
  const validationMutationInFlightRef = useRef(false);
  const [saving, setSaving] = useState(false);
  const [evaluationRecoveryRunId, setEvaluationRecoveryRunId] = useState<string | null>(null);
  const [evaluationRecoveryError, setEvaluationRecoveryError] = useState<string | null>(null);
  const [evaluationRecoveryNotFound, setEvaluationRecoveryNotFound] = useState(false);
  const [calibrating, setCalibrating] = useState(false);
  const [thresholding, setThresholding] = useState(false);
  const [selectiveCutoff, setSelectiveCutoff] = useState("0.80");
  const [selectingReview, setSelectingReview] = useState(false);
  const [policyRecovery, setPolicyRecovery] = useState<ValidationPolicyRecovery | null>(null);
  const [recoveringPolicy, setRecoveringPolicy] = useState(false);
  const [finalTesting, setFinalTesting] = useState(false);
  const [finalTestRecovery, setFinalTestRecovery] = useState<FinalTestRecovery | null>(null);
  const [recoveringFinalTest, setRecoveringFinalTest] = useState(false);
  const [finalTestConfirmed, setFinalTestConfirmed] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [comparisonRecovery, setComparisonRecovery] = useState<ComparisonRecovery | null>(null);
  const [recoveringComparison, setRecoveringComparison] = useState(false);
  const comparisonSessionRef = useRef(project.session_id);
  comparisonSessionRef.current = project.session_id;
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [includeManualFis, setIncludeManualFis] = useState(false);
  useEffect(() => {
    setSelectedRunIds([]);
    setIncludeManualFis(false);
    setComparisonRecovery(null);
    setError(null);
  }, [project.session_id]);
  useEffect(() => {
    if (modelContextStatus !== "loaded" || !fis?.semantic_hash) setIncludeManualFis(false);
  }, [modelContextStatus, fis?.fis_id, fis?.semantic_hash]);
  const [sliceRunning, setSliceRunning] = useState(false);
  const [sliceRecoveryRequest, setSliceRecoveryRequest] = useState<{ evaluationId: string; metric: string; definitions: SliceDefinition[] } | null>(null);
  const [sliceRecoveryError, setSliceRecoveryError] = useState<string | null>(null);
  const [sliceRecoveryNotFound, setSliceRecoveryNotFound] = useState(false);
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

  function beginValidationMutation(): boolean {
    if (validationMutationInFlightRef.current) return false;
    validationMutationInFlightRef.current = true;
    return true;
  }

  function endValidationMutation(): void {
    validationMutationInFlightRef.current = false;
  }

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
  const activeSelectivePolicy = selectivePolicy && activeEvaluation && activeThreshold
    && selectivePolicy.run_id === runId
    && selectivePolicy.evaluation_id === activeEvaluation.evaluation_id
    && selectivePolicy.class_threshold_id === activeThreshold.threshold_id
    && selectivePolicy.class_threshold === activeThreshold.selected_threshold
    && selectivePolicy.calibration_id === activeThreshold.calibration_id
    ? selectivePolicy
    : null;
  const activeStabilityGatePolicy = stabilityGatePolicy && activeEvaluation && activeThreshold && dataset
    && stabilityGatePolicy.selected_run_id === runId
    && stabilityGatePolicy.evaluation_id === activeEvaluation.evaluation_id
    && stabilityGatePolicy.class_threshold_id === activeThreshold.threshold_id
    && stabilityGatePolicy.calibration_id === activeThreshold.calibration_id
    && stabilityGatePolicy.dataset_fingerprint === dataset.contract.dataset_fingerprint
    && stabilityGatePolicy.dataset_artifact_sha256 === dataset.contract.source_artifact_sha256
    ? stabilityGatePolicy
    : null;
  const activeFinalTest = finalTestEvaluation && finalTestEvaluation.run_id === runId
    ? finalTestEvaluation
    : null;
  const datasetTestBoundaryAt = dataset && finalTestEvaluation?.dataset_fingerprint === dataset.contract.dataset_fingerprint
    ? finalTestEvaluation.dataset_test_unlock_at
    : null;
  const datasetTestBoundaryOpened = Boolean(datasetTestBoundaryAt);
  const finalTestBoundaryKnown = finalTestEvidenceStatus === "none" || finalTestEvidenceStatus === "available";
  const evaluationStateKnown = evaluationStatus === "none" || evaluationStatus === "available";
  const validationPoliciesKnown = validationPolicyEvidenceStatus === "available";
  const datasetIdentityKnown = datasetHydrationStatus === "available" && dataset !== null;
  const validationMutationBusy = saving || calibrating || thresholding || selectingReview;

  const option = useMemo(() => {
    if (!run) return null;
    return run.task === "binary_classification"
      ? calibrationOption(run, activeEvaluation, activeCalibration)
      : regressionOption(run);
  }, [run, activeEvaluation, activeCalibration]);

  if (!run || !option || !runId) {
    return <section className="feature-workspace">
      {runListStatus === "error" ? <div className="error" role="alert">
        <strong>Could not restore saved training runs</strong>
        <p>{runListError ?? "The saved run list is temporarily unavailable. No empty state is inferred from this failure."}</p>
        <Button view="outlined" onClick={onRetryRunList}>Retry loading saved runs</Button>
      </div> : runListStatus === "loading" || runListStatus === "idle" ? <div role="status">Loading saved training runs…</div> : runs.length > 0 ? <div className="info-message" role="status">Saved runs are available. Restoring the most recent run…</div> : <EmptyState title="No trained run">Train a model in Experiment before evaluating it.</EmptyState>}
    </section>;
  }

  async function createEvaluationForRun(targetRunId: string): Promise<AnalysisEvaluation> {
    try {
      const created = await studioApi.createAnalysisEvaluation(project.session_id, targetRunId);
      onEvaluation(created); onCalibration(null); onThreshold(null);
      setEvaluationRecoveryRunId(null); setEvaluationRecoveryError(null); setEvaluationRecoveryNotFound(false);
      return created;
    } catch (reason) {
      setEvaluationRecoveryRunId(targetRunId);
      setEvaluationRecoveryError(reason instanceof Error ? reason.message : "The persisted validation evaluation could not be confirmed.");
      setEvaluationRecoveryNotFound(false);
      throw reason;
    }
  }

  async function ensureEvaluation(): Promise<AnalysisEvaluation> {
    if (activeEvaluation) return activeEvaluation;
    return createEvaluationForRun(runId!);
  }

  async function saveEvaluation() {
    if (policyRecovery || !beginValidationMutation()) return;
    setSaving(true);
    setError(null);
    try {
      await createEvaluationForRun(runId!);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save validation evaluation");
    } finally {
      endValidationMutation();
      setSaving(false);
    }
  }

  async function recoverEvaluation() {
    const targetRunId = evaluationRecoveryRunId;
    if (!targetRunId) return;
    setSaving(true); setError(null);
    try {
      let latest: AnalysisEvaluation;
      try { latest = await studioApi.getLatestAnalysisEvaluationForRun(project.session_id, targetRunId); }
      catch (reason) {
        if (reason instanceof ProductApiError && reason.status === 404) {
          setEvaluationRecoveryNotFound(true);
          setEvaluationRecoveryError("No saved Evaluation is visible yet. Retry lookup later, or explicitly create one for this same run if the original request did not finish.");
          return;
        }
        throw reason;
      }
      if (latest.run_id !== targetRunId) throw new Error("The run-bound Evaluation lookup returned evidence for another TrainingRun.");
      onEvaluation(latest); onCalibration(null); onThreshold(null);
      setEvaluationRecoveryRunId(null); setEvaluationRecoveryError(null); setEvaluationRecoveryNotFound(false);
    } catch (reason) {
      setEvaluationRecoveryError(reason instanceof Error ? reason.message : "Could not recover the saved validation Evaluation.");
      setEvaluationRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setSaving(false); }
  }

  async function explicitlyCreateEvaluation() {
    if (!evaluationRecoveryRunId || !evaluationRecoveryNotFound || !beginValidationMutation()) return;
    setSaving(true); setError(null);
    try { await createEvaluationForRun(evaluationRecoveryRunId); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not create the explicitly requested validation Evaluation."); }
    finally { endValidationMutation(); setSaving(false); }
  }

  async function recoverValidationPolicyWrite() {
    const pending = policyRecovery;
    if (!pending) return;
    setRecoveringPolicy(true); setError(null);
    try {
      try {
        if (pending.kind === "calibration") {
          const latest = await studioApi.getLatestAnalysisCalibrationForEvaluation(project.session_id, pending.evaluationId);
          if (latest.evaluation_id !== pending.evaluationId) throw new Error("Recovered calibration belongs to another Evaluation; no replacement was created.");
          onCalibration(latest); onThreshold(null);
        } else if (pending.kind === "threshold") {
          const latest = await studioApi.getLatestAnalysisThresholdForEvaluation(project.session_id, pending.evaluationId, pending.calibrationId);
          if (latest.evaluation_id !== pending.evaluationId || latest.calibration_id !== pending.calibrationId) throw new Error("The latest threshold belongs to another Evaluation or calibration; no replacement was created.");
          onThreshold(latest);
        } else {
          const latest = await studioApi.getLatestSelectivePolicyForBinding(project.session_id, pending.evaluationId, pending.confidenceCutoff, pending.calibrationId, pending.thresholdId);
          if (latest.evaluation_id !== pending.evaluationId || latest.confidence_cutoff !== pending.confidenceCutoff || latest.calibration_id !== pending.calibrationId || latest.class_threshold_id !== pending.thresholdId) throw new Error("Recovered selective policy does not match the exact Evaluation, cutoff, calibration and threshold; no replacement was created.");
          onSelectivePolicy(latest);
        }
        setPolicyRecovery(null);
      } catch (reason) {
        if (reason instanceof ProductApiError && reason.status === 404) {
          setPolicyRecovery({ ...pending, notFound: true, error: "No matching saved policy is visible yet. Retry lookup later, or explicitly repeat this exact validation request if the original did not finish." });
          return;
        }
        throw reason;
      }
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Could not recover the exact validation policy.";
      setPolicyRecovery({ ...pending, notFound: false, error: message }); setError(message);
    } finally { setRecoveringPolicy(false); }
  }

  async function explicitlyRepeatValidationPolicyWrite() {
    const pending = policyRecovery;
    if (!pending?.notFound || !beginValidationMutation()) return;
    setRecoveringPolicy(true); setError(null);
    try {
      if (pending.kind === "calibration") {
        const created = await studioApi.fitAnalysisCalibration(project.session_id, pending.evaluationId);
        onCalibration(created); onThreshold(null);
      } else if (pending.kind === "threshold") {
        onThreshold(await studioApi.selectAnalysisThreshold(project.session_id, pending.evaluationId, pending.calibrationId));
      } else {
        onSelectivePolicy(await studioApi.createSelectivePolicy(project.session_id, pending.evaluationId, pending.confidenceCutoff, pending.calibrationId, pending.thresholdId));
      }
      setPolicyRecovery(null);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "The explicitly repeated validation policy could not be confirmed.";
      setPolicyRecovery({ ...pending, notFound: false, error: message }); setError(message);
    } finally { endValidationMutation(); setRecoveringPolicy(false); }
  }

  async function fitCalibration() {
    if (policyRecovery || !beginValidationMutation()) return;
    setCalibrating(true);
    setError(null);
    try {
      const current = await ensureEvaluation();
      let fitted: CalibrationTransform;
      try { fitted = await studioApi.fitAnalysisCalibration(project.session_id, current.evaluation_id); }
      catch (reason) {
        setPolicyRecovery({ kind: "calibration", evaluationId: current.evaluation_id, error: reason instanceof Error ? reason.message : "Calibration response was uncertain.", notFound: false });
        throw reason;
      }
      onCalibration(fitted);
      onThreshold(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not fit validation calibration");
    } finally {
      endValidationMutation();
      setCalibrating(false);
    }
  }

  async function selectThreshold() {
    if (policyRecovery || !beginValidationMutation()) return;
    setThresholding(true);
    setError(null);
    try {
      const current = await ensureEvaluation();
      const calibrationId = activeCalibration?.calibration_id ?? null;
      let selected: DecisionThresholdPolicy;
      try { selected = await studioApi.selectAnalysisThreshold(
        project.session_id,
        current.evaluation_id,
        calibrationId,
      ); } catch (reason) {
        setPolicyRecovery({ kind: "threshold", evaluationId: current.evaluation_id, calibrationId, error: reason instanceof Error ? reason.message : "Threshold response was uncertain.", notFound: false });
        throw reason;
      }
      onThreshold(selected);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not select validation decision threshold");
    } finally {
      endValidationMutation();
      setThresholding(false);
    }
  }

  async function selectReviewPolicy() {
    if (policyRecovery || !beginValidationMutation()) return;
    setSelectingReview(true);
    setError(null);
    try {
      const current = await ensureEvaluation();
      if (!activeThreshold) throw new Error("Select a validation DecisionThreshold before creating a selective policy.");
      const confidenceCutoff = Number(selectiveCutoff);
      const calibrationId = activeCalibration?.calibration_id ?? null;
      try { onSelectivePolicy(await studioApi.createSelectivePolicy(project.session_id, current.evaluation_id, confidenceCutoff, calibrationId, activeThreshold.threshold_id)); }
      catch (reason) {
        setPolicyRecovery({ kind: "selective", evaluationId: current.evaluation_id, confidenceCutoff, calibrationId, thresholdId: activeThreshold.threshold_id, error: reason instanceof Error ? reason.message : "Selective policy response was uncertain.", notFound: false });
        throw reason;
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not select validation review policy");
    } finally {
      endValidationMutation();
      setSelectingReview(false);
    }
  }

  async function evaluateFinalTest() {
    if (finalTestRecovery) return;
    if (policyRecovery) {
      setError("Resolve the pending validation policy save before any final-test access.");
      return;
    }
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
    if (!beginValidationMutation()) {
      setError("Wait for the current validation evidence or policy write to finish before opening the final test.");
      return;
    }
    setFinalTesting(true);
    setError(null);
    const request: FinalTestRecovery = {
      evaluationId: activeEvaluation.evaluation_id,
      calibrationId: activeThreshold?.probability_source === "calibrated" ? activeCalibration?.calibration_id ?? null : null,
      thresholdId: activeThreshold?.threshold_id ?? null,
      selectivePolicyId: activeSelectivePolicy?.policy_id ?? null,
      stabilityGatePolicyId: activeStabilityGatePolicy?.policy_id ?? null,
      error: "",
    };
    try {
      const result = await studioApi.evaluateFinalTest(
        project.session_id,
        request.evaluationId,
        request.calibrationId,
        request.thresholdId,
        request.selectivePolicyId,
        request.stabilityGatePolicyId,
      );
      onFinalTest(result);
      setFinalTestConfirmed(false);
      setFinalTestRecovery(null);
    } catch (reason) {
      setFinalTestRecovery({ ...request, error: reason instanceof Error ? reason.message : "Final-test response was uncertain. Do not resubmit this request." });
      setError(reason instanceof Error ? reason.message : "Could not evaluate frozen final-test split");
    } finally {
      endValidationMutation();
      setFinalTesting(false);
    }
  }

  async function recoverFinalTest() {
    const pending = finalTestRecovery;
    if (!pending) return;
    setRecoveringFinalTest(true); setError(null);
    try {
      const latest = await studioApi.getLatestFinalTestEvaluation(project.session_id);
      if (latest.evaluation_id !== pending.evaluationId || latest.calibration_id !== pending.calibrationId || latest.threshold_id !== pending.thresholdId || latest.selective_policy_id !== pending.selectivePolicyId || latest.stability_gate_policy_id !== pending.stabilityGatePolicyId) {
        setFinalTestRecovery({ ...pending, error: "The latest FinalTestEvaluation has different frozen policy identities. No new final-test evaluation was submitted; inspect persisted lineage before proceeding." });
        return;
      }
      onFinalTest(latest); setFinalTestRecovery(null); setFinalTestConfirmed(false);
    } catch (reason) {
      const message = reason instanceof ProductApiError && reason.status === 404
        ? "No matching FinalTestEvaluation is visible yet. The dataset boundary may still have opened; do not submit another test request. Retry this lookup or reopen and inspect persisted evidence."
        : reason instanceof Error ? reason.message : "Could not recover FinalTestEvaluation; do not resubmit.";
      setFinalTestRecovery({ ...pending, error: message }); setError(message);
    } finally { setRecoveringFinalTest(false); }
  }

  async function createComparisonForExactRequest(request: ComparisonRecovery) {
    const requestSessionId = project.session_id;
    const includeFis = request.fisId !== null;
    if (includeFis && (modelContextStatus !== "loaded" || fis?.fis_id !== request.fisId || fis.semantic_hash !== request.fisSemanticHash)) throw new Error("The saved FIS revision is unverified or changed; the original comparison request cannot be repeated safely.");
    try {
      const created = await studioApi.createAnalysisComparison(requestSessionId, request.runIds, includeFis, request.fisId, request.fisSemanticHash);
      if (comparisonSessionRef.current !== requestSessionId) return;
      if (created.fis_id !== request.fisId || created.fis_semantic_hash !== request.fisSemanticHash) throw new Error("Saved comparison does not match the exact requested FIS revision.");
      onComparison(created);
      setComparisonRecovery(null);
    } catch (reason) {
      if (comparisonSessionRef.current !== requestSessionId) return;
      const pending = { ...request, error: reason instanceof Error ? reason.message : "Comparison response was uncertain.", notFound: false };
      setComparisonRecovery(pending);
      throw reason;
    }
  }

  async function saveStudyComparison() {
    if (!study || comparisonRecovery) return;
    setComparing(true); setError(null);
    try { await createComparisonForExactRequest({ runIds: study.seed_runs.map((seedRun) => seedRun.run_id), fisId: null, fisSemanticHash: null, error: "", notFound: false }); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save validation comparison"); }
    finally { setComparing(false); }
  }

  async function saveSelectedComparison() {
    if (comparisonRecovery) return;
    if (selectedRunIds.length + Number(includeManualFis) < 2 || selectedRunIds.length < 1) { setError("Select two compatible runs, or one run and a saved manual FIS."); return; }
    if (includeManualFis && (modelContextStatus !== "loaded" || !fis?.semantic_hash)) { setError("Verify and save the exact manual FIS revision before comparing it with a run."); return; }
    setComparing(true); setError(null);
    try { await createComparisonForExactRequest({ runIds: selectedRunIds, fisId: includeManualFis ? fis!.fis_id : null, fisSemanticHash: includeManualFis ? fis!.semantic_hash : null, error: "", notFound: false }); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save validation comparison"); }
    finally { setComparing(false); }
  }

  async function recoverComparison() {
    const pending = comparisonRecovery;
    if (!pending) return;
    const requestSessionId = project.session_id;
    setRecoveringComparison(true); setError(null);
    try {
      const latest = await studioApi.getLatestAnalysisComparison(requestSessionId);
      if (comparisonSessionRef.current !== requestSessionId) return;
      if (canonicalJson(latest.run_ids) !== canonicalJson(pending.runIds) || latest.fis_id !== pending.fisId || latest.fis_semantic_hash !== pending.fisSemanticHash) {
        setComparisonRecovery({ ...pending, notFound: true, error: "The latest comparison has different run/FIS identities; no replacement was created." });
        return;
      }
      onComparison(latest); setComparisonRecovery(null);
    } catch (reason) {
      if (comparisonSessionRef.current !== requestSessionId) return;
      if (reason instanceof ProductApiError && reason.status === 404) {
        setComparisonRecovery({ ...pending, notFound: true, error: "No matching saved comparison is visible yet. Retry lookup later, or explicitly repeat this exact validation comparison." });
      } else {
        const message = reason instanceof Error ? reason.message : "Could not recover the exact validation comparison.";
        setComparisonRecovery({ ...pending, notFound: false, error: message }); setError(message);
      }
    } finally { setRecoveringComparison(false); }
  }

  async function explicitlyRepeatComparison() {
    const pending = comparisonRecovery;
    if (!pending?.notFound) return;
    setRecoveringComparison(true); setError(null);
    try { await createComparisonForExactRequest(pending); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "The explicitly repeated comparison could not be confirmed."); }
    finally { setRecoveringComparison(false); }
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
      const persistedDefinition: SliceDefinition = {
        ...definition,
        field: definition.field ?? null,
        values: definition.values ?? [],
        minimum: definition.minimum ?? null,
        maximum: definition.maximum ?? null,
        start: definition.start ?? null,
        end: definition.end ?? null,
        source_rows: definition.source_rows ?? [],
      };
      const request = { evaluationId: current.evaluation_id, metric, definitions: [persistedDefinition] };
      try {
        const result = await studioApi.createSliceAnalysis(project.session_id, request.evaluationId, request.metric, request.definitions);
        onSliceAnalysis(result); setSliceRecoveryRequest(null); setSliceRecoveryError(null); setSliceRecoveryNotFound(false);
      } catch (reason) {
        setSliceRecoveryRequest(request); setSliceRecoveryError(reason instanceof Error ? reason.message : "The saved SliceAnalysis could not be confirmed."); setSliceRecoveryNotFound(false);
        throw reason;
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create Slice Analysis");
    } finally {
      setSliceRunning(false);
    }
  }

  async function recoverSliceAnalysis() {
    const request = sliceRecoveryRequest;
    if (!request) return;
    setSliceRunning(true); setError(null);
    try {
      let latest: SliceAnalysis;
      try { latest = await studioApi.getLatestSliceAnalysis(project.session_id); }
      catch (reason) {
        if (reason instanceof ProductApiError && reason.status === 404) {
          setSliceRecoveryNotFound(true); setSliceRecoveryError("No saved SliceAnalysis is visible yet. Retry lookup later, or explicitly rerun this exact validation slice if the original request did not finish."); return;
        }
        throw reason;
      }
      if (latest.evaluation_id !== request.evaluationId || latest.metric !== request.metric || canonicalJson(latest.definitions) !== canonicalJson(request.definitions)) {
        setSliceRecoveryNotFound(true); setSliceRecoveryError("The latest saved SliceAnalysis belongs to another definition; no replacement was created."); return;
      }
      onSliceAnalysis(latest); setSliceRecoveryRequest(null); setSliceRecoveryError(null); setSliceRecoveryNotFound(false);
    } catch (reason) {
      setSliceRecoveryError(reason instanceof Error ? reason.message : "Could not recover the exact SliceAnalysis."); setSliceRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setSliceRunning(false); }
  }

  async function explicitlyRerunSliceAnalysis() {
    if (!sliceRecoveryRequest || !sliceRecoveryNotFound) return;
    setSliceRunning(true); setError(null);
    try {
      const request = sliceRecoveryRequest;
      onSliceAnalysis(await studioApi.createSliceAnalysis(project.session_id, request.evaluationId, request.metric, request.definitions));
      setSliceRecoveryRequest(null); setSliceRecoveryError(null); setSliceRecoveryNotFound(false);
    } catch (reason) {
      setSliceRecoveryError(reason instanceof Error ? reason.message : "The explicitly repeated SliceAnalysis could not be confirmed."); setSliceRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setSliceRunning(false); }
  }

  const metrics = Object.entries(activeEvaluation?.metrics ?? run.validation_metrics);
  const calibratedByRow = new Map(activeCalibration?.predictions.map((item) => [item.row, item.calibrated_probability]) ?? []);
  const decisionByRow = new Map(activeThreshold?.decisions.map((item) => [item.row, item.predicted_label]) ?? []);
  const matrix = activeThreshold?.confusion_matrix ?? activeEvaluation?.confusion_matrix ?? run.confusion_matrix;
  const displayRows = activeEvaluation?.prediction_preview ?? run.prediction_preview;

  return <section className="feature-workspace evaluation-workspace">
    {project.read_only && <div className="info-message" role="status">Read-only project: saved validation evidence is available to inspect, but new evaluations, policies and final-test access cannot be saved from this session.</div>}
    {runListStatus === "error" && <div className="error" role="alert">
      <strong>Saved run history could not be loaded</strong>
      <p>{runListError ?? "Model comparison may be incomplete until the run list is available."}</p>
      <Button view="outlined" onClick={onRetryRunList}>Retry loading saved runs</Button>
    </div>}
    <div className="feature-toolbar">
      <div>
        <span className="eyebrow">VALIDATION EVIDENCE</span>
        <h2>Evaluate trained model</h2>
        <p>{activeEvaluation?.scientific_note ?? run.scientific_note}</p>
      </div>
      <div className="toolbar-actions">
        <StatusBadge tone={activeFinalTest || datasetTestBoundaryOpened ? "danger" : "warning"}>{activeFinalTest ? "final test evaluated" : datasetTestBoundaryOpened ? "dataset final-test boundary opened" : finalTestBoundaryKnown ? "final test locked" : "final-test status unverified"}</StatusBadge>
        {study && <Button view="outlined" disabled={comparing || !!comparisonRecovery || project.read_only || !["none", "available"].includes(comparisonHydrationStatus)} onClick={saveStudyComparison} data-ruflex-action="comparison.study.create">{comparing ? "Comparing…" : "Compare study seeds"}</Button>}
        <Button view="outlined" disabled={validationMutationBusy || !!finalTestRecovery || !!evaluationRecoveryRunId || project.read_only || !evaluationStateKnown} onClick={saveEvaluation} data-ruflex-action="evaluation.save">{saving ? "Saving…" : activeEvaluation ? "Save evaluation revision" : "Save validation evidence"}</Button>
        {run.task === "binary_classification" && <Button view="outlined" disabled={validationMutationBusy || !!finalTestRecovery || !!policyRecovery || !!evaluationRecoveryRunId || project.read_only || datasetTestBoundaryOpened || !datasetIdentityKnown || !finalTestBoundaryKnown || !evaluationStateKnown || !validationPoliciesKnown} onClick={fitCalibration} data-ruflex-action="calibration.fit">{calibrating ? "Fitting…" : activeCalibration ? "Refit calibration" : "Fit validation calibration"}</Button>}
        {run.task === "binary_classification" && <Button view="action" disabled={validationMutationBusy || !!finalTestRecovery || !!policyRecovery || !!evaluationRecoveryRunId || project.read_only || datasetTestBoundaryOpened || !datasetIdentityKnown || !finalTestBoundaryKnown || !evaluationStateKnown || !validationPoliciesKnown} onClick={selectThreshold} data-ruflex-action="threshold.select">{thresholding ? "Selecting…" : activeThreshold ? "Reselect threshold" : `Select F1 threshold (${activeCalibration ? "calibrated" : "raw"})`}</Button>}
      </div>
    </div>

    {evaluationStatus === "loading" && <div role="status">Checking saved validation Evaluation before offering a new save or policy action…</div>}
    {evaluationStatus === "idle" && <div role="status">Saved validation Evaluation status has not been checked; policy actions remain paused.</div>}
    {evaluationRecoveryRunId && <div className="error" role="alert" data-testid="evaluation-recovery"><strong>Evaluation request outcome is uncertain; resolve the exact run before creating dependent evidence.</strong><p>{evaluationRecoveryError}</p><Button view="outlined" disabled={saving} onClick={recoverEvaluation}>Retry saved Evaluation lookup</Button>{evaluationRecoveryNotFound && <Button view="outlined" disabled={saving} onClick={explicitlyCreateEvaluation}>Create Evaluation for this run explicitly</Button>}</div>}
    {evaluationStatus === "error" && <div className="error" role="alert"><strong>Could not verify saved validation Evaluation</strong><p>{evaluationError ?? "Saved evaluation state is unavailable; no empty state is inferred."}</p><Button view="outlined" onClick={onRetryEvaluation}>Retry validation evidence check</Button></div>}
    {datasetHydrationStatus === "loading" && <div role="status">Verifying the persisted DatasetContract before enabling validation policy changes or final-test access…</div>}
    {datasetHydrationStatus === "idle" && <div role="status">Dataset identity has not been checked; dataset-dependent policy actions remain paused.</div>}
    {datasetHydrationStatus === "error" && <div className="error" role="alert"><strong>Could not verify the persisted DatasetContract.</strong><p>{datasetHydrationError ?? "Dataset compatibility is unresolved; no empty-dataset state is inferred."}</p><Button view="outlined" onClick={onRetryDatasetHydration}>Retry dataset check</Button>{run && <small>Saved run {run.run_id.slice(0, 12)} and its validation metrics remain available.</small>}</div>}
    {validationPolicyEvidenceStatus === "loading" && <div role="status">Checking persisted calibration, threshold and review policies before enabling validation changes or final-test evaluation…</div>}
    {validationPolicyEvidenceStatus === "idle" && <div role="status">Saved validation policy status has not been checked; policy changes and final-test evaluation remain paused.</div>}
    {validationPolicyEvidenceStatus === "error" && <div className="error" role="alert"><strong>Could not verify saved validation policies</strong><p>{validationPolicyEvidenceError ?? "Persisted policy evidence is unavailable; no absent-policy state is inferred."}</p><Button view="outlined" onClick={onRetryValidationPolicyEvidence}>Retry saved policy check</Button></div>}
    {policyRecovery && <div className="error" role="alert" data-testid="validation-policy-recovery"><strong>{policyRecovery.kind} save outcome is uncertain; dependent actions are paused.</strong><p>{policyRecovery.error}</p><Button view="outlined" disabled={recoveringPolicy} onClick={recoverValidationPolicyWrite}>Retry exact saved policy lookup</Button>{policyRecovery.notFound && <Button view="outlined" disabled={recoveringPolicy || project.read_only || datasetTestBoundaryOpened} onClick={explicitlyRepeatValidationPolicyWrite}>Explicitly repeat this exact policy request</Button>}</div>}

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
        <div><span className="eyebrow">CONFUSION MATRIX · VALIDATION</span><h3>{activeThreshold ? `Frozen policy threshold ${activeThreshold.selected_threshold.toFixed(2)}` : "Preview at default cutoff 0.50 · no frozen threshold policy"}</h3></div>
        <div className="confusion-grid">
          <div><span>TN</span><strong>{matrix.true_negative}</strong></div>
          <div><span>FP</span><strong>{matrix.false_positive}</strong></div>
          <div><span>FN</span><strong>{matrix.false_negative}</strong></div>
          <div><span>TP</span><strong>{matrix.true_positive}</strong></div>
        </div>
      </section> : <section className="confusion-card"><span className="eyebrow">REGRESSION</span><h3>Residual evidence</h3><p>Complete validation predictions are persisted; the table below shows the first rows.</p></section>}
    </div>

    {run.task === "binary_classification" && activeEvaluation && <div className="evaluation-grid">
      <ChartSurface title="Validation ROC curve · raw model" option={operatingCurveOption(activeEvaluation.roc_curve, "false positive rate", "true positive rate", true)} theme={theme} />
      <ChartSurface title="Validation precision–recall curve · raw model" option={operatingCurveOption(activeEvaluation.precision_recall_curve, "recall", "precision", false)} theme={theme} />
    </div>}

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
      <Button view="action" disabled={validationMutationBusy || !!finalTestRecovery || !!policyRecovery || !!evaluationRecoveryRunId || project.read_only || datasetTestBoundaryOpened || !datasetIdentityKnown || !finalTestBoundaryKnown || !evaluationStateKnown || !validationPoliciesKnown || !activeThreshold} onClick={selectReviewPolicy} data-ruflex-action="selective_policy.create">{selectingReview ? "Selecting…" : "Save ACCEPT / REVIEW policy"}</Button>
      {!activeThreshold && <small>Select the validation class threshold first; accepted risk uses that exact threshold, never an implicit 0.50.</small>}
      {selectivePolicy && !activeSelectivePolicy && <p className="property-description" role="status">A saved selective policy belongs to a different run, Evaluation or threshold and is not shown or applied here.</p>}
      {activeSelectivePolicy && <><p><StatusBadge tone="warning">REVIEW BELOW {activeSelectivePolicy.confidence_cutoff.toFixed(2)}</StatusBadge> ACCEPT at or above cutoff · class threshold {activeSelectivePolicy.class_threshold.toFixed(2)} · {activeSelectivePolicy.probability_source} probability.</p><small className="mono">threshold {activeSelectivePolicy.class_threshold_id.slice(0, 12)} · validation cases {activeSelectivePolicy.fit_sample_identity.slice(0, 24)}…</small><div className="data-table-wrap"><table className="data-table"><thead><tr><th>confidence</th><th>coverage</th><th>accepted risk</th><th>accepted</th></tr></thead><tbody>{activeSelectivePolicy.risk_coverage.map((point) => <tr key={point.confidence_cutoff}><td>{point.confidence_cutoff.toFixed(2)}</td><td>{(point.coverage * 100).toFixed(1)}%</td><td>{point.accepted_risk === null ? "—" : `${(point.accepted_risk * 100).toFixed(1)}%`}</td><td>{point.accepted_count}</td></tr>)}</tbody></table></div><small>{activeSelectivePolicy.scientific_note}</small></>}
    </section>}

    <section>
      <h3>Validation prediction evidence</h3>
      <div className="data-table-wrap"><table className="data-table"><thead><tr><th>row</th><th>target</th><th>{run.task === "binary_classification" ? "logit" : "prediction"}</th>{run.task === "binary_classification" ? <><th>raw probability</th><th>calibrated probability</th><th>final class</th></> : <th>residual</th>}</tr></thead><tbody>
        {displayRows.slice(0, 20).map((row) => <tr key={row.row}><td>{row.row}</td><td>{row.target.toFixed(5)}</td><td>{row.prediction.toFixed(5)}</td>{run.task === "binary_classification" ? <><td>{row.probability?.toFixed(5) ?? "—"}</td><td>{calibratedByRow.get(row.row)?.toFixed(5) ?? "not fitted"}</td><td>{decisionByRow.get(row.row) ?? row.predicted_label ?? "—"}</td></> : <td>{row.residual?.toFixed(5) ?? "—"}</td>}</tr>)}
      </tbody></table></div>
      <small>{activeEvaluation ? `${activeEvaluation.validation_row_count} validation rows persisted; first ${Math.min(20, displayRows.length)} displayed.` : "Save validation evidence to persist the complete evaluation object."}</small>
    </section>

      <div className="evaluation-footer"><StatusBadge tone="success">validation evaluated</StatusBadge><span>{activeEvaluation ? `Evaluation ${activeEvaluation.evaluation_id.slice(0, 12)} · ` : "Unsaved analysis · "}Run {run.run_id.slice(0, 12)} · model {run.model_artifact_sha256.slice(0, 12)} · {activeFinalTest ? `${activeFinalTest.test_row_count} final-test rows evaluated with frozen policy` : datasetTestBoundaryOpened ? "this run has no final-test result; dataset test access already opened" : !finalTestBoundaryKnown ? "final-test boundary status is being verified; new policies are temporarily blocked" : `${run.split.test_count} final-test rows remain locked`}</span></div>

    <section className="comparison-card final-test-gate">
      <span className="eyebrow">FINAL TEST · EXPLICIT FROZEN-POLICY EVALUATION</span>
      <h3>{activeFinalTest ? "Final-test evidence persisted separately" : datasetTestBoundaryOpened ? "Dataset final-test boundary already opened" : !finalTestBoundaryKnown ? "Final-test state unavailable" : "Final test remains closed"}</h3>
      {finalTestEvidenceStatus === "loading" && <div role="status">Checking persisted final-test access before enabling policy actions…</div>}
      {finalTestEvidenceStatus === "idle" && <div role="status">Final-test access status has not been checked; validation policies remain disabled.</div>}
      {finalTestEvidenceStatus === "error" && <div className="error" role="alert"><strong>Could not verify whether final-test access already occurred.</strong><p>{finalTestEvidenceError ?? "The persisted final-test boundary is unavailable."}</p><Button view="outlined" onClick={onRetryFinalTestEvidence}>Retry final-test status check</Button></div>}
      {finalTestRecovery && <div className="error" role="alert" data-testid="final-test-recovery"><strong>Final-test request outcome is uncertain. Do not submit it again.</strong><p>{finalTestRecovery.error}</p><Button view="outlined" disabled={recoveringFinalTest} onClick={recoverFinalTest}>Retry exact FinalTestEvaluation lookup</Button></div>}
      {activeFinalTest ? <>
        <div className="comparison-protocol-line"><StatusBadge tone="danger">FINAL TEST EVALUATED</StatusBadge><span className="mono">{activeFinalTest.final_test_id.slice(0, 12)} · n={activeFinalTest.test_row_count}</span></div>
        <div className="metric-grid">{Object.entries(activeFinalTest.metrics).map(([name, value]) => <div className="metric-card" key={`final-${name}`}><span>{name}</span><strong>{Number(value).toFixed(4)}</strong><small>FINAL TEST · frozen policy</small></div>)}</div>
        <p>{activeFinalTest.scientific_note}</p>
        <small className="mono">policy {activeFinalTest.policy_identity.slice(0, 36)}… · cases {(activeFinalTest.test_case_identity ?? activeFinalTest.test_sample_identity).slice(0, 36)}…</small>
        {activeFinalTest.dataset_test_unlock_at && <small className="mono">dataset test gate opened {new Date(activeFinalTest.dataset_test_unlock_at).toLocaleString()} · only policies frozen before this boundary and using the same holdout cases remain eligible</small>}
      </> : <>
        {datasetTestBoundaryOpened ? <><p>The first test access for this dataset has already occurred. This run has no persisted FinalTestEvaluation. Only policies frozen before the recorded boundary and reconstructing the same holdout rows remain eligible.</p><small className="mono">Dataset test gate opened {new Date(datasetTestBoundaryAt!).toLocaleString()}</small></> : <p>Validation remains the only evidence used for model selection, probability calibration and threshold selection. The first final-test access freezes the dataset-level eligibility boundary. Additional pre-specified policies may be evaluated only if they were already frozen and reconstruct the same holdout rows.</p>}{stabilityGatePolicy && !activeStabilityGatePolicy && <small role="status">The saved Stability Gate is bound to a different run, Evaluation, threshold or dataset and will not be applied here.</small>}{activeStabilityGatePolicy && <small>Stability Gate {activeStabilityGatePolicy.policy_id.slice(0, 12)} is validation-derived and will be bound to this final-test evidence; it is not fitted on final-test data.</small>}
        <label className="final-test-confirm"><input type="checkbox" checked={finalTestConfirmed} onChange={(event) => setFinalTestConfirmed(event.target.checked)} />{datasetTestBoundaryOpened ? "I confirm this policy was frozen before the recorded dataset-level test boundary; final-test results will not be used for retuning." : "I confirm this policy was frozen before final-test access; final-test results will not be used to retune or create another eligible policy."}</label>
      <Button view="action" disabled={project.read_only || finalTesting || validationMutationBusy || !!finalTestRecovery || !!policyRecovery || !!evaluationRecoveryRunId || !datasetIdentityKnown || !finalTestBoundaryKnown || !activeEvaluation || !finalTestConfirmed || !validationPoliciesKnown || (run.task === "binary_classification" && !activeThreshold)} onClick={evaluateFinalTest} data-ruflex-action="final_test.execute">{finalTesting ? "Evaluating final test…" : "Evaluate frozen final test"}</Button>
        {run.task === "binary_classification" && !activeThreshold && <small>Select a validation-derived decision threshold first. Calibration is optional; a calibrated threshold automatically requires its persisted calibration transform.</small>}
      </>}
    </section>

    {comparisonHydrationStatus === "loading" && <p role="status" data-testid="comparison-hydration-loading">Loading saved validation comparison…</p>}
    {comparisonHydrationStatus === "none" && <p className="property-description" data-testid="comparison-hydration-empty">No saved validation comparison is available for this project.</p>}
    {comparisonHydrationStatus === "error" && <div className="error" role="alert" data-testid="comparison-hydration-error"><strong>Saved validation comparison could not be verified.</strong><p>{comparisonHydrationError}</p>{onRetryComparison && <Button view="outlined" onClick={onRetryComparison}>Retry validation comparison</Button>}</div>}
    {comparisonRecovery && <div className="error" role="alert" data-testid="comparison-recovery"><strong>Validation comparison save is uncertain; no duplicate was submitted.</strong><p>{comparisonRecovery.error}</p><Button view="outlined" disabled={recoveringComparison} onClick={recoverComparison}>Retry exact comparison lookup</Button>{comparisonRecovery.notFound && <Button view="outlined" disabled={recoveringComparison || project.read_only} onClick={explicitlyRepeatComparison}>Explicitly repeat this exact comparison</Button>}</div>}
    {comparison && <section className="comparison-card"><span className="eyebrow">SAVED MODEL COMPARISON · VALIDATION ONLY</span><h3>{comparison.metric_rows.length} compatible model subjects</h3><div className="comparison-protocol-line"><StatusBadge tone={comparison.validation_alignment === "same_cases" ? "success" : comparison.validation_alignment === "mixed_cases" ? "warning" : "info"}>{comparison.validation_alignment === "same_cases" ? "same validation cases" : comparison.validation_alignment === "mixed_cases" ? "mixed validation cases" : "validation alignment unknown"}</StatusBadge>{comparison.dataset_fingerprint && <span className="mono">dataset {comparison.dataset_fingerprint.slice(0, 12)}</span>}</div><div className="data-table-wrap"><table className="data-table"><thead><tr>{[...new Set(comparison.metric_rows.flatMap((row) => Object.keys(row)))].map((key) => <th key={key}>{key}</th>)}</tr></thead><tbody>{comparison.metric_rows.map((row) => <tr key={String(row.subject_id ?? row.run_id)}>{[...new Set(comparison.metric_rows.flatMap((candidate) => Object.keys(candidate)))].map((key) => <td key={key}>{typeof row[key] === "number" ? Number(row[key]).toFixed(4) : row[key] === undefined ? "—" : String(row[key])}</td>)}</tr>)}</tbody></table></div><p>{comparison.scientific_note}</p></section>}
    {comparison && comparison.metric_rows.length > 0 && <ChartSurface title="Shared validation metrics by model subject" option={comparisonOption(comparison)} theme={theme} />}
    {(modelContextStatus === "idle" || modelContextStatus === "loading") && <p role="status" data-testid="comparison-model-context-loading">Checking saved FIS availability before enabling manual-FIS comparison…</p>}
    {modelContextStatus === "error" && <div className="error" role="alert" data-testid="comparison-model-context-error"><strong>Manual FIS availability could not be verified.</strong><p>{modelContextError ?? "No empty-FIS state is inferred from this failed read."}</p>{onRetryModelContext && <Button view="outlined" onClick={onRetryModelContext}>Retry saved model context</Button>}</div>}
    {(runs.length > 1 || (runs.length > 0 && fis)) && <section className="comparison-card"><span className="eyebrow">MODEL COMPARISON · VALIDATION ONLY</span><h3>Compare compatible models on declared validation evidence</h3>{fis && <label className="comparison-choice"><input type="checkbox" disabled={!!comparisonRecovery || modelContextStatus !== "loaded" || !fis.semantic_hash} checked={includeManualFis} onChange={(event) => setIncludeManualFis(event.target.checked)} />Manual {fis.system_type} FIS · semantic {(fis.semantic_hash ?? "unsaved").slice(0, 12)} · {fis.rules.length} rules</label>}{runs.map((candidate) => <label className="comparison-choice" key={candidate.run_id}><input type="checkbox" disabled={!!comparisonRecovery} checked={selectedRunIds.includes(candidate.run_id)} onChange={(event) => setSelectedRunIds((current) => event.target.checked ? [...current, candidate.run_id] : current.filter((id) => id !== candidate.run_id))} />{candidate.model_kind} · seed {candidate.seed} · {candidate.run_id.slice(0, 12)} · nodes {typeof candidate.model_spec.node_count === "number" ? candidate.model_spec.node_count : "—"}</label>)}<Button view="outlined" disabled={comparing || !!comparisonRecovery || project.read_only || !["none", "available"].includes(comparisonHydrationStatus) || selectedRunIds.length + (includeManualFis ? 1 : 0) < 2 || (includeManualFis && (selectedRunIds.length < 1 || modelContextStatus !== "loaded" || !fis?.semantic_hash))} onClick={saveSelectedComparison} data-ruflex-action="comparison.selected.create">{comparing ? "Comparing…" : `Compare ${selectedRunIds.length + (includeManualFis ? 1 : 0)} selected models`}</Button><p>Manual FIS is evaluated on exactly the persisted validation cases of the selected trained run(s). If selected runs use different validation cases, RuFLEX blocks adding the FIS instead of pretending the comparison is paired. FIS scores are not labeled calibrated probabilities.</p></section>}

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
      {sliceAnalysisHydrationStatus === "loading" && <p role="status" data-testid="slice-hydration-loading">Loading saved slice evidence…</p>}
      {sliceAnalysisHydrationStatus === "none" && <p className="property-description" data-testid="slice-hydration-empty">No saved SliceAnalysis is available for this project.</p>}
      {sliceAnalysisHydrationStatus === "error" && <div className="error" role="alert" data-testid="slice-hydration-error"><strong>Saved SliceAnalysis could not be verified.</strong><p>{sliceAnalysisHydrationError}</p>{onRetrySliceAnalysis && <Button view="outlined" onClick={onRetrySliceAnalysis}>Retry slice evidence</Button>}</div>}
      {sliceRecoveryRequest && <div className="error" role="alert" data-testid="slice-analysis-recovery"><strong>Slice analysis save is uncertain; no duplicate was submitted.</strong><p>{sliceRecoveryError}</p><Button view="outlined" disabled={sliceRunning} onClick={recoverSliceAnalysis}>Retry saved SliceAnalysis lookup</Button>{sliceRecoveryNotFound && <Button view="outlined" disabled={sliceRunning || project.read_only} onClick={explicitlyRerunSliceAnalysis}>Explicitly rerun this exact slice</Button>}</div>}
      <Button view="outlined" disabled={sliceRunning || !!sliceRecoveryRequest || !!evaluationRecoveryRunId || project.read_only || !dataset || !evaluationStateKnown || !["none", "available"].includes(sliceAnalysisHydrationStatus)} onClick={runSliceAnalysis} data-ruflex-action="slice.create">{sliceRunning ? "Calculating…" : "Run and persist slice"}</Button>
      {sliceAnalysis && <div className="data-table-wrap"><table className="data-table"><thead><tr><th>slice</th><th>kind</th><th>N</th><th>metric</th><th>value</th><th>overall</th><th>delta</th><th>metric status</th><th>declared scope</th></tr></thead><tbody>{sliceAnalysis.results.map((result) => <tr key={`${sliceAnalysis.analysis_id}-${result.name}`}><td>{result.name}</td><td>{result.kind}</td><td>{result.n}</td><td>{result.metric}</td><td>{result.value === null ? "—" : result.value.toFixed(4)}</td><td>{result.overall_value.toFixed(4)}</td><td>{result.delta_vs_overall === null ? "—" : result.delta_vs_overall.toFixed(4)}</td><td>{result.status}{result.warning ? ` · ${result.warning}` : ""}</td><td><StatusBadge tone={result.scope_disposition === "ALLOW" ? "success" : result.scope_disposition === "BLOCK" ? "danger" : "warning"}>{result.scope_disposition}</StatusBadge>{result.scope_reasons.length > 0 && <small className="slice-scope-reason">{result.scope_reasons.join(" ")}</small>}</td></tr>)}</tbody></table><p>{sliceAnalysis.generalization_contract_id ? `Scope classifications use GeneralizationContract ${sliceAnalysis.generalization_contract_id.slice(0, 12)}. ` : "No GeneralizationContract was linked; scope remains undeclared. "}{sliceAnalysis.scientific_note}</p></div>}
    </section>
    {error && <div className="error" role="alert">{error}</div>}
  </section>;
}
