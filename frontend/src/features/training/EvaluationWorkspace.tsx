import { EChartsOption } from "echarts";
import { PredictionDistribution } from "./PredictionDistribution";
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
import { ui, uiLanguage, uiStatus } from "../../design/language";
import { formatEvidenceNumber } from "./formatEvidenceNumber";

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.entries(value as Record<string, unknown>).sort(([left], [right]) => left.localeCompare(right)).map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`).join(",")}}`;
  }
  return JSON.stringify(value) ?? "undefined";
}

function isDefinitiveValidationWriteRejection(reason: unknown): boolean {
  return reason instanceof ProductApiError && [403, 404, 409, 422].includes(reason.status);
}

function parseManualSourceRows(draft: string): number[] {
  const tokens = draft.split(",").map((value) => value.trim());
  if (tokens.some((value) => !/^(0|[1-9]\d*)$/.test(value))) {
    throw new Error("Enter one or more comma-separated original source row IDs as non-negative whole numbers; no entry may be blank or ignored.");
  }
  const rows = tokens.map(Number);
  if (rows.some((value) => !Number.isSafeInteger(value)) || new Set(rows).size !== rows.length) {
    throw new Error("Original source row IDs must be unique safe integers; correct the list before saving the slice.");
  }
  return rows;
}

function parseSliceValues(draft: string): string[] {
  const values = draft.split(",").map((value) => value.trim());
  if (values.some((value) => !value)) {
    throw new Error("Enter one or more comma-separated slice values; no entry may be blank or ignored.");
  }
  return values;
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
  onSelectSuggestedRun?: (runId: string) => Promise<void>;
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
  onSelectSuggestedRun,
  onSliceAnalysis,
  onSelectivePolicy,
}: Props) {
  const [suggestionOpenBusy, setSuggestionOpenBusy] = useState(false);
  const [suggestionOpenError, setSuggestionOpenError] = useState<string | null>(null);
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
  useEffect(() => {
    setFinalTestConfirmed(false);
    setFinalTestRecovery(null);
  }, [project.session_id]);
  const [comparing, setComparing] = useState(false);
  const [comparisonRecovery, setComparisonRecovery] = useState<ComparisonRecovery | null>(null);
  const [recoveringComparison, setRecoveringComparison] = useState(false);
  const workspaceSessionRef = useRef(project.session_id);
  workspaceSessionRef.current = project.session_id;
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
  const [sliceName, setSliceName] = useState(ui("Validation slice", "Группа проверочных данных"));
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
  useEffect(() => {
    setSliceRecoveryRequest(null);
    setSliceRecoveryError(null);
    setSliceRecoveryNotFound(false);
    setSliceName("Validation slice");
    setSliceKind("numeric_range");
    setSliceField("");
    setSliceValues("");
    setSliceMinimum("");
    setSliceMaximum("");
    setSliceStart("");
    setSliceEnd("");
    setSliceRows("");
    setSliceMetric("");
  }, [project.session_id]);

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
        <strong>{ui("Could not restore saved training runs", "Не удалось загрузить сохранённые модели")}</strong>
        <p>{runListError ?? "The saved run list is temporarily unavailable. No empty state is inferred from this failure."}</p>
        <Button view="outlined" onClick={onRetryRunList}>{ui("Retry loading saved runs", "Повторить загрузку моделей")}</Button>
      </div> : runListStatus === "loading" || runListStatus === "idle" ? <div role="status">{ui("Loading saved training runs…", "Загрузка моделей…")}</div> : runs.length > 0 ? <div className="info-message" role="status">{ui("Saved runs are available. Restoring the most recent run…", "Открытие последней сохранённой модели…")}</div> : <EmptyState title="No trained run">{ui("Train a model in Experiment before evaluating it.", "Сначала обучите модель в разделе «Обучение».")}</EmptyState>}
    </section>;
  }

  async function createEvaluationForRun(targetRunId: string): Promise<AnalysisEvaluation> {
    try {
      const created = await studioApi.createAnalysisEvaluation(project.session_id, targetRunId);
      onEvaluation(created); onCalibration(null); onThreshold(null);
      setEvaluationRecoveryRunId(null); setEvaluationRecoveryError(null); setEvaluationRecoveryNotFound(false);
      return created;
    } catch (reason) {
      if (isDefinitiveValidationWriteRejection(reason)) throw reason;
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
        if (isDefinitiveValidationWriteRejection(reason)) throw reason;
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
        if (isDefinitiveValidationWriteRejection(reason)) throw reason;
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
    if (policyRecovery) return;
    const cutoffText = selectiveCutoff.trim();
    const confidenceCutoff = Number(cutoffText);
    if (!cutoffText || !Number.isFinite(confidenceCutoff) || confidenceCutoff < 0.5 || confidenceCutoff > 1.0) {
      setError("The confidence cutoff must be a finite number between 0.5 and 1.0; no policy request was sent.");
      return;
    }
    if (!beginValidationMutation()) return;
    setSelectingReview(true);
    setError(null);
    try {
      const current = await ensureEvaluation();
      if (!activeThreshold) throw new Error("Select a validation DecisionThreshold before creating a selective policy.");
      const calibrationId = activeCalibration?.calibration_id ?? null;
      try { onSelectivePolicy(await studioApi.createSelectivePolicy(project.session_id, current.evaluation_id, confidenceCutoff, calibrationId, activeThreshold.threshold_id)); }
      catch (reason) {
        if (isDefinitiveValidationWriteRejection(reason)) throw reason;
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
    const requestSessionId = project.session_id;
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
        requestSessionId,
        request.evaluationId,
        request.calibrationId,
        request.thresholdId,
        request.selectivePolicyId,
        request.stabilityGatePolicyId,
      );
      if (workspaceSessionRef.current !== requestSessionId) return;
      onFinalTest(result);
      setFinalTestConfirmed(false);
      setFinalTestRecovery(null);
    } catch (reason) {
      if (workspaceSessionRef.current !== requestSessionId) return;
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
    const requestSessionId = project.session_id;
    setRecoveringFinalTest(true); setError(null);
    try {
      const latest = await studioApi.getLatestFinalTestEvaluation(requestSessionId);
      if (workspaceSessionRef.current !== requestSessionId) return;
      if (latest.evaluation_id !== pending.evaluationId || latest.calibration_id !== pending.calibrationId || latest.threshold_id !== pending.thresholdId || latest.selective_policy_id !== pending.selectivePolicyId || latest.stability_gate_policy_id !== pending.stabilityGatePolicyId) {
        setFinalTestRecovery({ ...pending, error: "The latest FinalTestEvaluation has different frozen policy identities. No new final-test evaluation was submitted; inspect persisted lineage before proceeding." });
        return;
      }
      onFinalTest(latest); setFinalTestRecovery(null); setFinalTestConfirmed(false);
    } catch (reason) {
      if (workspaceSessionRef.current !== requestSessionId) return;
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
      if (workspaceSessionRef.current !== requestSessionId) return;
      if (created.fis_id !== request.fisId || created.fis_semantic_hash !== request.fisSemanticHash) throw new Error("Saved comparison does not match the exact requested FIS revision.");
      onComparison(created);
      setComparisonRecovery(null);
    } catch (reason) {
      if (workspaceSessionRef.current !== requestSessionId) return;
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
      if (workspaceSessionRef.current !== requestSessionId) return;
      if (canonicalJson(latest.run_ids) !== canonicalJson(pending.runIds) || latest.fis_id !== pending.fisId || latest.fis_semantic_hash !== pending.fisSemanticHash) {
        setComparisonRecovery({ ...pending, notFound: true, error: "The latest comparison has different run/FIS identities; no replacement was created." });
        return;
      }
      onComparison(latest); setComparisonRecovery(null);
    } catch (reason) {
      if (workspaceSessionRef.current !== requestSessionId) return;
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
    const requestSessionId = project.session_id;
    if (!dataset) {
      setError("Dataset state is required for Slice Lab.");
      return;
    }
    setSliceRunning(true);
    setError(null);
    try {
      const manualRows = sliceKind === "manual" ? parseManualSourceRows(sliceRows) : null;
      const selectedValues = sliceKind === "categorical" || sliceKind === "group" ? parseSliceValues(sliceValues) : null;
      if (sliceKind === "numeric_range" && !sliceMinimum.trim() && !sliceMaximum.trim()) {
        throw new Error(ui("Enter a minimum or maximum before saving a numeric-range slice.", "Укажите хотя бы одну границу диапазона: «От» или «До». Например, от 10 до 20."));
      }
      if (sliceKind === "temporal" && !sliceStart.trim() && !sliceEnd.trim()) {
        throw new Error(ui("Enter a start or end before saving a temporal slice.", "Укажите начало или конец периода."));
      }
      const current = await ensureEvaluation();
      if (workspaceSessionRef.current !== requestSessionId) return;
      const field = sliceField || dataset.contract.feature_columns[0] || dataset.profile.columns[0]?.name || "";
      const definition: SliceDefinition = { name: sliceName.trim() || "Validation slice", kind: sliceKind };
      if (sliceKind === "manual") {
        definition.source_rows = manualRows!;
      } else {
        definition.field = field;
      }
      if (sliceKind === "categorical" || sliceKind === "group") {
        definition.values = selectedValues!;
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
        const result = await studioApi.createSliceAnalysis(requestSessionId, request.evaluationId, request.metric, request.definitions);
        if (workspaceSessionRef.current !== requestSessionId) return;
        onSliceAnalysis(result); setSliceRecoveryRequest(null); setSliceRecoveryError(null); setSliceRecoveryNotFound(false);
      } catch (reason) {
        if (workspaceSessionRef.current !== requestSessionId) return;
        setSliceRecoveryRequest(request); setSliceRecoveryError(reason instanceof Error ? reason.message : "The saved SliceAnalysis could not be confirmed."); setSliceRecoveryNotFound(false);
        throw reason;
      }
    } catch (reason) {
      if (workspaceSessionRef.current !== requestSessionId) return;
      setError(reason instanceof Error ? reason.message : "Could not create Slice Analysis");
    } finally {
      setSliceRunning(false);
    }
  }

  async function recoverSliceAnalysis() {
    const request = sliceRecoveryRequest;
    if (!request) return;
    const requestSessionId = project.session_id;
    setSliceRunning(true); setError(null);
    try {
      let latest: SliceAnalysis;
      try { latest = await studioApi.getLatestSliceAnalysis(requestSessionId); }
      catch (reason) {
        if (workspaceSessionRef.current !== requestSessionId) return;
        if (reason instanceof ProductApiError && reason.status === 404) {
          setSliceRecoveryNotFound(true); setSliceRecoveryError("No saved SliceAnalysis is visible yet. Retry lookup later, or explicitly rerun this exact validation slice if the original request did not finish."); return;
        }
        throw reason;
      }
      if (workspaceSessionRef.current !== requestSessionId) return;
      if (latest.evaluation_id !== request.evaluationId || latest.metric !== request.metric || canonicalJson(latest.definitions) !== canonicalJson(request.definitions)) {
        setSliceRecoveryNotFound(true); setSliceRecoveryError("The latest saved SliceAnalysis belongs to another definition; no replacement was created."); return;
      }
      onSliceAnalysis(latest); setSliceRecoveryRequest(null); setSliceRecoveryError(null); setSliceRecoveryNotFound(false);
    } catch (reason) {
      if (workspaceSessionRef.current !== requestSessionId) return;
      setSliceRecoveryError(reason instanceof Error ? reason.message : "Could not recover the exact SliceAnalysis."); setSliceRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setSliceRunning(false); }
  }

  async function explicitlyRerunSliceAnalysis() {
    if (!sliceRecoveryRequest || !sliceRecoveryNotFound) return;
    const requestSessionId = project.session_id;
    setSliceRunning(true); setError(null);
    try {
      const request = sliceRecoveryRequest;
      const repeated = await studioApi.createSliceAnalysis(requestSessionId, request.evaluationId, request.metric, request.definitions);
      if (workspaceSessionRef.current !== requestSessionId) return;
      onSliceAnalysis(repeated);
      setSliceRecoveryRequest(null); setSliceRecoveryError(null); setSliceRecoveryNotFound(false);
    } catch (reason) {
      if (workspaceSessionRef.current !== requestSessionId) return;
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
    {project.read_only && <div className="info-message" role="status">{ui("Read-only project: saved validation evidence is available to inspect, but new evaluations, policies and final-test access cannot be saved from this session.", "Проект открыт только для чтения. Можно просматривать результаты, но нельзя сохранять новые оценки и настройки или открывать тест.")}</div>}
    {runListStatus === "error" && <div className="error" role="alert">
      <strong>{ui("Saved run history could not be loaded", "Не удалось загрузить историю моделей")}</strong>
      <p>{runListError ?? "Model comparison may be incomplete until the run list is available."}</p>
      <Button view="outlined" onClick={onRetryRunList}>{ui("Retry loading saved runs", "Повторить загрузку моделей")}</Button>
    </div>}
    <div className="feature-toolbar">
      <div>
        <span className="eyebrow">{ui("VALIDATION EVIDENCE", "ВАЛИДАЦИЯ")}</span>
        <h2>{ui("Evaluate trained model", "Оценить модель")}</h2>
        <p>{ui(activeEvaluation?.scientific_note ?? run.scientific_note, "Результаты валидации и зафиксированные политики. Финальный тест открывается отдельно.")}</p>
      </div>
      <div className="toolbar-actions">
        <StatusBadge tone={activeFinalTest || datasetTestBoundaryOpened ? "danger" : "warning"}>{activeFinalTest ? ui("final test evaluated", "Финальный тест выполнен") : datasetTestBoundaryOpened ? ui("dataset final-test boundary opened", "Финальный тест открыт") : finalTestBoundaryKnown ? ui("final test locked", "Финальный тест закрыт") : ui("final-test status unverified", "Статус теста не проверен")}</StatusBadge>
        {study && <Button view="outlined" disabled={comparing || !!comparisonRecovery || project.read_only || !["none", "available"].includes(comparisonHydrationStatus)} onClick={saveStudyComparison} data-ruflex-action="comparison.study.create">{comparing ? ui("Comparing…", "Сравнение…") : ui("Compare study seeds", "Сравнить запуски")}</Button>}
        <Button view="outlined" disabled={validationMutationBusy || !!finalTestRecovery || !!evaluationRecoveryRunId || project.read_only || !evaluationStateKnown} onClick={saveEvaluation} data-ruflex-action="evaluation.save">{saving ? ui("Saving…", "Сохранение…") : activeEvaluation ? ui("Save evaluation revision", "Сохранить новую оценку") : ui("Save validation evidence", "Сохранить оценку")}</Button>
        {run.task === "binary_classification" && <Button view="outlined" disabled={validationMutationBusy || !!finalTestRecovery || !!policyRecovery || !!evaluationRecoveryRunId || project.read_only || datasetTestBoundaryOpened || !datasetIdentityKnown || !finalTestBoundaryKnown || !evaluationStateKnown || !validationPoliciesKnown} onClick={fitCalibration} data-ruflex-action="calibration.fit">{calibrating ? ui("Fitting…", "Калибровка…") : activeCalibration ? ui("Refit calibration", "Повторить калибровку") : ui("Fit validation calibration", "Калибровать на валидации")}</Button>}
        {run.task === "binary_classification" && <Button view="action" disabled={validationMutationBusy || !!finalTestRecovery || !!policyRecovery || !!evaluationRecoveryRunId || project.read_only || datasetTestBoundaryOpened || !datasetIdentityKnown || !finalTestBoundaryKnown || !evaluationStateKnown || !validationPoliciesKnown} onClick={selectThreshold} data-ruflex-action="threshold.select">{thresholding ? ui("Selecting…", "Подбор…") : activeThreshold ? ui("Reselect threshold", "Выбрать порог заново") : ui(`Select F1 threshold (${activeCalibration ? "calibrated" : "raw"})`, `Выбрать порог F1 (${activeCalibration ? "после калибровки" : "без калибровки"})`)}</Button>}
      </div>
    </div>

    {evaluationStatus === "loading" && <div role="status">{ui("Checking saved validation Evaluation before offering a new save or policy action…", "Загрузка сохранённой оценки…")}</div>}
    {evaluationStatus === "idle" && <div role="status">{ui("Saved validation Evaluation status has not been checked; policy actions remain paused.", "Состояние оценки ещё не проверено. Настройки пока недоступны.")}</div>}
    {evaluationRecoveryRunId && <div className="error" role="alert" data-testid="evaluation-recovery"><strong>{ui("Evaluation request outcome is uncertain; resolve the exact run before creating dependent evidence.", "Не удалось подтвердить сохранение оценки. Сначала проверьте её состояние.")}</strong><p>{evaluationRecoveryError}</p><Button view="outlined" disabled={saving} onClick={recoverEvaluation}>{ui("Retry saved Evaluation lookup", "Найти сохранённую оценку")}</Button>{evaluationRecoveryNotFound && <Button view="outlined" disabled={saving} onClick={explicitlyCreateEvaluation}>{ui("Create Evaluation for this run explicitly", "Повторить сохранение этой оценки")}</Button>}</div>}
    {evaluationStatus === "error" && <div className="error" role="alert"><strong>{ui("Could not verify saved validation Evaluation", "Не удалось проверить сохранённую оценку")}</strong><p>{evaluationError ?? "Saved evaluation state is unavailable; no empty state is inferred."}</p><Button view="outlined" onClick={onRetryEvaluation}>{ui("Retry validation evidence check", "Повторить проверку оценки")}</Button></div>}
    {datasetHydrationStatus === "loading" && <div role="status">{ui("Verifying the persisted DatasetContract before enabling validation policy changes or final-test access…", "Проверка сохранённого набора данных…")}</div>}
    {datasetHydrationStatus === "idle" && <div role="status">{ui("Dataset identity has not been checked; dataset-dependent policy actions remain paused.", "Набор данных ещё не проверен. Действия временно недоступны.")}</div>}
    {datasetHydrationStatus === "error" && <div className="error" role="alert"><strong>{ui("Could not verify the persisted DatasetContract.", "Не удалось проверить сохранённый набор данных.")}</strong><p>{datasetHydrationError ?? "Dataset compatibility is unresolved; no empty-dataset state is inferred."}</p><Button view="outlined" onClick={onRetryDatasetHydration}>{ui("Retry dataset check", "Повторить проверку данных")}</Button>{run && <small>Saved run {run.run_id.slice(0, 12)} and its validation metrics remain available.</small>}</div>}
    {validationPolicyEvidenceStatus === "loading" && <div role="status">{ui("Checking persisted calibration, threshold and review policies before enabling validation changes or final-test evaluation…", "Загрузка сохранённых порогов и настроек проверки…")}</div>}
    {validationPolicyEvidenceStatus === "idle" && <div role="status">{ui("Saved validation policy status has not been checked; policy changes and final-test evaluation remain paused.", "Сохранённые настройки ещё не проверены. Изменения и итоговый тест пока недоступны.")}</div>}
    {validationPolicyEvidenceStatus === "error" && <div className="error" role="alert"><strong>{ui("Could not verify saved validation policies", "Не удалось проверить сохранённые настройки")}</strong><p>{validationPolicyEvidenceError ?? "Persisted policy evidence is unavailable; no absent-policy state is inferred."}</p><Button view="outlined" onClick={onRetryValidationPolicyEvidence}>{ui("Retry saved policy check", "Проверить настройки повторно")}</Button></div>}
    {policyRecovery && <div className="error" role="alert" data-testid="validation-policy-recovery"><strong>{policyRecovery.kind} save outcome is uncertain; dependent actions are paused.</strong><p>{policyRecovery.error}</p><Button view="outlined" disabled={recoveringPolicy} onClick={recoverValidationPolicyWrite}>{ui("Retry exact saved policy lookup", "Найти сохранённые настройки")}</Button>{policyRecovery.notFound && <Button view="outlined" disabled={recoveringPolicy || project.read_only || datasetTestBoundaryOpened} onClick={explicitlyRepeatValidationPolicyWrite}>{ui("Explicitly repeat this exact policy request", "Повторить этот запрос")}</Button>}</div>}

    <div className="metric-grid">
      {metrics.map(([name, value]) => <div className="metric-card" key={name}><span>{name}</span><strong>{formatEvidenceNumber(Number(value))}</strong><small>{ui("validation · raw model", "проверочные данные · исходная модель")}</small></div>)}
      {activeCalibration && <>
        <div className="metric-card"><span>Brier calibrated</span><strong>{activeCalibration.brier_after.toFixed(4)}</strong><small>{activeCalibration.brier_before.toFixed(4)} before</small></div>
        <div className="metric-card"><span>ECE calibrated</span><strong>{activeCalibration.ece_after.toFixed(4)}</strong><small>{activeCalibration.ece_before.toFixed(4)} before</small></div>
      </>}
      {activeThreshold && <div className="metric-card"><span>{ui("Decision threshold", "Порог решения")}</span><strong>{activeThreshold.selected_threshold.toFixed(2)}</strong><small>{ui("validation F1", "F1 на валидации")} {activeThreshold.selection_result.toFixed(4)}</small></div>}
    </div>

    <div className="evaluation-grid">
      {run.task === "binary_classification" ? <ChartSurface title={ui("Validation reliability", "Надёжность на валидации")} option={option} theme={theme} /> : <PredictionDistribution run={run} evaluation={activeEvaluation} theme={theme} />}
      {matrix ? <section className="confusion-card">
        <div><span className="eyebrow">{ui("CONFUSION MATRIX · VALIDATION", "МАТРИЦА ОШИБОК · ВАЛИДАЦИЯ")}</span><h3>{activeThreshold ? ui(`Frozen policy threshold ${activeThreshold.selected_threshold.toFixed(2)}`, `Зафиксированный порог ${activeThreshold.selected_threshold.toFixed(2)}`) : ui("Preview at default cutoff 0.50 · no frozen threshold policy", "Предпросмотр с порогом 0,50 · политика ещё не сохранена")}</h3></div>
        <div className="confusion-grid">
          <div><span>TN</span><strong>{matrix.true_negative}</strong></div>
          <div><span>FP</span><strong>{matrix.false_positive}</strong></div>
          <div><span>FN</span><strong>{matrix.false_negative}</strong></div>
          <div><span>TP</span><strong>{matrix.true_positive}</strong></div>
        </div>
      </section> : <section className="confusion-card"><span className="eyebrow">{ui("REGRESSION", "РЕГРЕССИЯ")}</span><h3>{ui("Residual evidence", "Ошибки прогноза")}</h3><p>{ui("Complete validation predictions are persisted; the table below shows the first rows.", "Все прогнозы сохранены. Ниже показаны первые строки.")}</p></section>}
    </div>

    {run.task === "binary_classification" && activeEvaluation && <div className="evaluation-grid">
      <ChartSurface title="Validation ROC curve · raw model" option={operatingCurveOption(activeEvaluation.roc_curve, "false positive rate", "true positive rate", true)} theme={theme} />
      <ChartSurface title="Validation precision–recall curve · raw model" option={operatingCurveOption(activeEvaluation.precision_recall_curve, "recall", "precision", false)} theme={theme} />
    </div>}

    {run.task === "binary_classification" && <section className="comparison-card">
      <span className="eyebrow">{ui("DECISION PROVENANCE · VALIDATION ONLY", "ПРОИСХОЖДЕНИЕ РЕШЕНИЯ · ВАЛИДАЦИЯ")}</span>
      <h3>{ui("Probability → calibration → threshold → class", "Вероятность → калибровка → порог → класс")}</h3>
      <p>
        Raw model probability {activeCalibration ? `→ Platt transform ${activeCalibration.calibration_id.slice(0, 8)}` : "→ calibration not fitted"}
        {activeThreshold ? ` → threshold ${activeThreshold.selected_threshold.toFixed(2)} (${activeThreshold.probability_source})` : " → threshold not selected"}.
        Final-test data remain locked throughout this chain.
      </p>
      {activeCalibration && <details><summary>{ui("Calibration details", "Сведения о калибровке")}</summary><small className="mono">fit evidence {activeCalibration.fit_sample_identity.slice(0, 36)}… · n={activeCalibration.fit_sample_count}</small></details>}
      {activeThreshold && <details><summary>{ui("Threshold details", "Сведения о пороге")}</summary><small className="mono">threshold {activeThreshold.threshold_id.slice(0, 12)} · objective {activeThreshold.objective} · source {activeThreshold.source_split}</small></details>}
    </section>}

    {run.task === "binary_classification" && <section className="comparison-card">
      <span className="eyebrow">{ui("SELECTIVE PREDICTION · VALIDATION ONLY", "ВЫБОРОЧНАЯ ПРОВЕРКА · ВАЛИДАЦИЯ")}</span><h3>{ui("Accept confident cases; route the rest to review", "Уверенные прогнозы принять, остальные проверить")}</h3>
      <p>{ui("This confidence cutoff is independent of the class threshold. It tunes ACCEPT / REVIEW coverage on validation evidence and never opens the final test.", "Порог уверенности не зависит от порога класса и выбирается только на валидации.")}</p>
      <label className="field-label">{ui("Confidence cutoff", "Порог уверенности")}<input aria-label={ui("Selective confidence cutoff", "Порог уверенности для проверки")} type="number" min="0.5" max="1" step="0.05" value={selectiveCutoff} onChange={(event) => setSelectiveCutoff(event.target.value)} /></label>
      <Button view="action" disabled={validationMutationBusy || !!finalTestRecovery || !!policyRecovery || !!evaluationRecoveryRunId || project.read_only || datasetTestBoundaryOpened || !datasetIdentityKnown || !finalTestBoundaryKnown || !evaluationStateKnown || !validationPoliciesKnown || !activeThreshold} onClick={selectReviewPolicy} data-ruflex-action="selective_policy.create">{selectingReview ? ui("Selecting…", "Сохранение…") : ui("Save ACCEPT / REVIEW policy", "Сохранить политику проверки")}</Button>
      {!activeThreshold && <small>{ui("Select the validation class threshold first; accepted risk uses that exact threshold, never an implicit 0.50.", "Сначала сохраните порог решения. Ошибки считаются с этим порогом, а не с произвольным 0,5.")}</small>}
      {selectivePolicy && !activeSelectivePolicy && <p className="property-description" role="status">{ui("A saved selective policy belongs to a different run, Evaluation or threshold and is not shown or applied here.", "Сохранённое правило относится к другой модели или оценке и здесь не применяется.")}</p>}
      {activeSelectivePolicy && <><p><StatusBadge tone="warning">REVIEW BELOW {activeSelectivePolicy.confidence_cutoff.toFixed(2)}</StatusBadge> ACCEPT at or above cutoff · class threshold {activeSelectivePolicy.class_threshold.toFixed(2)} · {activeSelectivePolicy.probability_source} probability.</p><small className="mono">threshold {activeSelectivePolicy.class_threshold_id.slice(0, 12)} · validation cases {activeSelectivePolicy.fit_sample_identity.slice(0, 24)}…</small><div className="data-table-wrap"><table className="data-table"><thead><tr><th>{ui("confidence", "Уверенность")}</th><th>{ui("coverage", "Доля принятых")}</th><th>{ui("accepted risk", "Доля ошибок среди принятых")}</th><th>{ui("accepted", "Принято")}</th></tr></thead><tbody>{activeSelectivePolicy.risk_coverage.map((point) => <tr key={point.confidence_cutoff}><td>{point.confidence_cutoff.toFixed(2)}</td><td>{(point.coverage * 100).toFixed(1)}%</td><td>{point.accepted_risk === null ? "—" : `${(point.accepted_risk * 100).toFixed(1)}%`}</td><td>{point.accepted_count}</td></tr>)}</tbody></table></div><small>{activeSelectivePolicy.scientific_note}</small></>}
    </section>}

    {run.task === "binary_classification" && <PredictionDistribution run={run} evaluation={activeEvaluation} theme={theme} />}
    <section>
      <h3>{ui("Validation prediction evidence", "Прогнозы на валидации")}</h3>
      <div className="data-table-wrap"><table className="data-table"><thead><tr><th>{ui("row", "Строка")}</th><th>{ui("target", "Ответ")}</th><th>{run.task === "binary_classification" ? "logit" : "prediction"}</th>{run.task === "binary_classification" ? <><th>{ui("raw probability", "Вероятность модели")}</th><th>{ui("calibrated probability", "После калибровки")}</th><th>{ui("final class", "Класс")}</th></> : <th>{ui("residual", "Ошибка")}</th>}</tr></thead><tbody>
        {displayRows.slice(0, 20).map((row) => <tr key={row.row}><td>{row.row}</td><td>{formatEvidenceNumber(row.target, 5)}</td><td>{formatEvidenceNumber(row.prediction, 5)}</td>{run.task === "binary_classification" ? <><td>{row.probability === null || row.probability === undefined ? "—" : formatEvidenceNumber(row.probability, 5)}</td><td>{calibratedByRow.get(row.row) === undefined ? ui("not fitted", "не настроена") : formatEvidenceNumber(calibratedByRow.get(row.row)!, 5)}</td><td>{decisionByRow.get(row.row) ?? row.predicted_label ?? "—"}</td></> : <td>{row.residual === null || row.residual === undefined ? "—" : formatEvidenceNumber(row.residual, 5)}</td>}</tr>)}
      </tbody></table></div>
      <small>{activeEvaluation ? `${activeEvaluation.validation_row_count} validation rows persisted; first ${Math.min(20, displayRows.length)} displayed.` : ui("Save validation evidence to persist the complete evaluation object.", "Сохраните оценку на проверочных данных, чтобы продолжить.")}</small>
    </section>

      <details open={uiLanguage === "en"}><summary>{ui("Evaluation provenance", "Сведения о сохранённой оценке")}</summary>      <div className="evaluation-footer"><StatusBadge tone="success">{ui("validation evaluated", "Проверочная оценка готова")}</StatusBadge><span>{activeEvaluation ? `Evaluation ${activeEvaluation.evaluation_id.slice(0, 12)} · ` : "Unsaved analysis · "}Run {run.run_id.slice(0, 12)} · model {run.model_artifact_sha256.slice(0, 12)} · {activeFinalTest ? `${activeFinalTest.test_row_count} final-test rows evaluated with frozen policy` : datasetTestBoundaryOpened ? "this run has no final-test result; dataset test access already opened" : !finalTestBoundaryKnown ? "final-test boundary status is being verified; new policies are temporarily blocked" : `${run.split.test_count} final-test rows remain locked`}</span></div></details>

    <section className="comparison-card final-test-gate">
      <span className="eyebrow">{ui("FINAL TEST · EXPLICIT FROZEN-POLICY EVALUATION", "ИТОГОВАЯ ПРОВЕРКА МОДЕЛИ")}</span>
      <h3>{activeFinalTest ? ui("Final-test evidence persisted separately", "Результат финального теста сохранён отдельно") : datasetTestBoundaryOpened ? ui("Dataset final-test boundary already opened", "Финальный тест уже открыт") : !finalTestBoundaryKnown ? ui("Final-test state unavailable", "Статус финального теста недоступен") : ui("Final test remains closed", "Финальный тест закрыт")}</h3>
      {finalTestEvidenceStatus === "loading" && <div role="status">{ui("Checking persisted final-test access before enabling policy actions…", "Проверка состояния итогового теста…")}</div>}
      {finalTestEvidenceStatus === "idle" && <div role="status">{ui("Final-test access status has not been checked; validation policies remain disabled.", "Состояние теста неизвестно. Изменение настроек пока недоступно.")}</div>}
      {finalTestEvidenceStatus === "error" && <div className="error" role="alert"><strong>{ui("Could not verify whether final-test access already occurred.", "Не удалось проверить, открывали ли итоговый тест.")}</strong><p>{finalTestEvidenceError ?? "The persisted final-test boundary is unavailable."}</p><Button view="outlined" onClick={onRetryFinalTestEvidence}>{ui("Retry final-test status check", "Повторить проверку")}</Button></div>}
      {finalTestRecovery && <div className="error" role="alert" data-testid="final-test-recovery"><strong>{ui("Final-test request outcome is uncertain. Do not submit it again.", "Ответ на запрос теста потерян. Не запускайте его повторно; сначала найдите сохранённый результат.")}</strong><p>{finalTestRecovery.error}</p><Button view="outlined" disabled={recoveringFinalTest} onClick={recoverFinalTest}>{ui("Retry exact FinalTestEvaluation lookup", "Найти результат теста")}</Button></div>}
      {activeFinalTest ? <>
        <div className="comparison-protocol-line"><StatusBadge tone="danger">{ui("FINAL TEST EVALUATED", "Итоговый тест выполнен")}</StatusBadge><span className="mono">{activeFinalTest.final_test_id.slice(0, 12)} · n={activeFinalTest.test_row_count}</span></div>
        <div className="metric-grid">{Object.entries(activeFinalTest.metrics).map(([name, value]) => <div className="metric-card" key={`final-${name}`}><span>{name}</span><strong>{formatEvidenceNumber(Number(value))}</strong><small>{ui("FINAL TEST · frozen policy", "Итоговая проверка · сохранённые настройки")}</small></div>)}</div>
        <details open={uiLanguage === "en"}><summary>{ui("Technical provenance", "Технические сведения о тесте")}</summary><p>{activeFinalTest.scientific_note}</p>
        <small className="mono">policy {activeFinalTest.policy_identity.slice(0, 36)}… · cases {(activeFinalTest.test_case_identity ?? activeFinalTest.test_sample_identity).slice(0, 36)}…</small>
        {activeFinalTest.dataset_test_unlock_at && <small className="mono">dataset test gate opened {new Date(activeFinalTest.dataset_test_unlock_at).toLocaleString()} · only policies frozen before this boundary and using the same holdout cases remain eligible</small>}</details>
      </> : <>
        {datasetTestBoundaryOpened ? <><p>{ui("The first test access for this dataset has already occurred. This run has no persisted FinalTestEvaluation. Only policies frozen before the recorded boundary and reconstructing the same holdout rows remain eligible.", "Итоговый тест для этого набора уже открывали. Можно проверить только ранее сохранённые правила на том же отложенном наборе; новые настройки недопустимы.")}</p><small className="mono">Dataset test gate opened {new Date(datasetTestBoundaryAt!).toLocaleString()}</small></> : <p>{ui("Validation remains the only evidence used for model selection, probability calibration and threshold selection. The first final-test access freezes the dataset-level eligibility boundary. Additional pre-specified policies may be evaluated only if they were already frozen and reconstruct the same holdout rows.", "Это итоговая проверка на данных, которые не участвовали в настройке. Сначала завершите выбор модели и порога. После открытия теста подбирать их заново для этого набора нельзя.")}</p>}{stabilityGatePolicy && !activeStabilityGatePolicy && <small role="status">{ui("The saved Stability Gate is bound to a different run, Evaluation, threshold or dataset and will not be applied here.", "Правило устойчивости относится к другой модели или данным и здесь не применяется.")}</small>}{activeStabilityGatePolicy && <small>Stability Gate {activeStabilityGatePolicy.policy_id.slice(0, 12)} is validation-derived and will be bound to this final-test evidence; it is not fitted on final-test data.</small>}
        <label className="final-test-confirm"><input type="checkbox" checked={finalTestConfirmed} onChange={(event) => setFinalTestConfirmed(event.target.checked)} />{datasetTestBoundaryOpened ? ui("I confirm this policy was frozen before the recorded dataset-level test boundary; final-test results will not be used for retuning.", "Проверю ранее сохранённые настройки. По результатам теста менять их не буду.") : ui("I confirm this policy was frozen before final-test access; final-test results will not be used to retune or create another eligible policy.", "Настройка завершена. По результатам этого теста я не буду менять модель и порог.")}</label>
      <Button view="action" disabled={project.read_only || finalTesting || validationMutationBusy || !!finalTestRecovery || !!policyRecovery || !!evaluationRecoveryRunId || !datasetIdentityKnown || !finalTestBoundaryKnown || !activeEvaluation || !finalTestConfirmed || !validationPoliciesKnown || (run.task === "binary_classification" && !activeThreshold)} onClick={evaluateFinalTest} data-ruflex-action="final_test.execute">{finalTesting ? ui("Evaluating final test…", "Оценка финального теста…") : ui("Evaluate frozen final test", "Открыть финальный тест")}</Button>
        {run.task === "binary_classification" && !activeThreshold && <small>{ui("Select a validation-derived decision threshold first. Calibration is optional; a calibrated threshold automatically requires its persisted calibration transform.", "Сначала сохраните порог решения на проверочных данных — кнопка выше. После этого станет доступен итоговый тест.")}</small>}
      </>}
    </section>

    {comparisonHydrationStatus === "loading" && <p role="status" data-testid="comparison-hydration-loading">{ui("Loading saved validation comparison…", "Загрузка сравнения моделей…")}</p>}
    {comparisonHydrationStatus === "none" && <p className="property-description" data-testid="comparison-hydration-empty">{ui("No saved validation comparison is available for this project.", "Сравнение моделей ещё не сохраняли.")}</p>}
    {comparisonHydrationStatus === "error" && <div className="error" role="alert" data-testid="comparison-hydration-error"><strong>{ui("Saved validation comparison could not be verified.", "Не удалось проверить сравнение моделей.")}</strong><p>{comparisonHydrationError}</p>{onRetryComparison && <Button view="outlined" onClick={onRetryComparison}>{ui("Retry validation comparison", "Повторить сравнение")}</Button>}</div>}
    {comparisonRecovery && <div className="error" role="alert" data-testid="comparison-recovery"><strong>{ui("Validation comparison save is uncertain; no duplicate was submitted.", "Сохранение сравнения не подтверждено. Повторная запись не создавалась.")}</strong><p>{comparisonRecovery.error}</p><Button view="outlined" disabled={recoveringComparison} onClick={recoverComparison}>{ui("Retry exact comparison lookup", "Найти сохранённое сравнение")}</Button>{comparisonRecovery.notFound && <Button view="outlined" disabled={recoveringComparison || project.read_only} onClick={explicitlyRepeatComparison}>{ui("Explicitly repeat this exact comparison", "Повторить это сравнение")}</Button>}</div>}
    {comparison && <section className="comparison-card"><span className="eyebrow">{ui("SAVED MODEL COMPARISON · VALIDATION ONLY", "СРАВНЕНИЕ НА ПРОВЕРОЧНЫХ ДАННЫХ")}</span><h3>{comparison.metric_rows.length} compatible model subjects</h3><div className="comparison-protocol-line"><StatusBadge tone={comparison.validation_alignment === "same_cases" ? "success" : comparison.validation_alignment === "mixed_cases" ? "warning" : "info"}>{comparison.validation_alignment === "same_cases" ? "same validation cases" : comparison.validation_alignment === "mixed_cases" ? "mixed validation cases" : "validation alignment unknown"}</StatusBadge>{comparison.dataset_fingerprint && <span className="mono">dataset {comparison.dataset_fingerprint.slice(0, 12)}</span>}</div><div className="data-table-wrap"><table className="data-table"><thead><tr>{[...new Set(comparison.metric_rows.flatMap((row) => Object.keys(row)))].map((key) => <th key={key}>{key}</th>)}</tr></thead><tbody>{comparison.metric_rows.map((row) => <tr key={String(row.subject_id ?? row.run_id)}>{[...new Set(comparison.metric_rows.flatMap((candidate) => Object.keys(candidate)))].map((key) => <td key={key}>{typeof row[key] === "number" ? Number(row[key]).toFixed(4) : row[key] === undefined ? "—" : String(row[key])}</td>)}</tr>)}</tbody></table></div><p>{comparison.scientific_note}</p></section>}
    {comparison && comparison.metric_rows.length > 0 && <ChartSurface title="Shared validation metrics by model subject" option={comparisonOption(comparison)} theme={theme} />}
    {comparison && <section className="comparison-card" data-testid="validation-candidate-suggestion">
      <span className="eyebrow">{ui("GUIDED MODEL CHOICE · VALIDATION ONLY", "ВЫБОР СРЕДИ ОБУЧЕННЫХ МОДЕЛЕЙ")}</span>
      {comparison.candidate_suggestion ? <>
        <h3>Best observed candidate among {comparison.candidate_suggestion.candidate_count} selected trained runs</h3>
        <p><strong>{comparison.candidate_suggestion.model_kind}</strong> · {comparison.candidate_suggestion.metric.toUpperCase()} {comparison.candidate_suggestion.value.toFixed(4)} · run <code>{comparison.candidate_suggestion.run_id.slice(0, 12)}</code></p>
        <p>{ui("Compared on the same saved validation cases. Exact metric ties use the lowest run ID. This is a shortlist suggestion, not hyperparameter search, final-test evidence, or approval for deployment.", "Модели сравниваются на одних проверочных примерах. Это подсказка для выбора, не автоматический поиск параметров и не разрешение на внедрение.")}</p>
        {onSelectSuggestedRun && <Button view="outlined" disabled={suggestionOpenBusy || runListStatus !== "loaded" || !runs.some((candidate) => candidate.run_id === comparison.candidate_suggestion?.run_id)} onClick={async () => {
          setSuggestionOpenBusy(true); setSuggestionOpenError(null);
          try { await onSelectSuggestedRun(comparison.candidate_suggestion!.run_id); }
          catch (reason) { setSuggestionOpenError(reason instanceof Error ? reason.message : "Suggested run could not be reopened."); }
          finally { setSuggestionOpenBusy(false); }
        }}>{suggestionOpenBusy ? "Opening saved run…" : "Inspect suggested run"}</Button>}
        {suggestionOpenError && <div role="alert" className="error">Could not open suggested run: {suggestionOpenError}</div>}
      </> : <>
        <h3>{ui("No automatic candidate suggestion", "Нет рекомендации по выбору")}</h3>
        <p>{comparison.validation_alignment === "mixed_cases" ? "These runs used different validation cases; ranking them as one matched comparison would be misleading." : comparison.validation_alignment === "unknown" ? "Exact validation case alignment is unavailable." : comparison.schema_version < 3 ? "This older saved comparison has no frozen candidate suggestion. Create a new comparison to record one without changing the original evidence." : "At least two trained runs with the task metric are required; a manual FIS is shown separately and is not ranked as a calibrated model."}</p>
      </>}
    </section>}
    {(modelContextStatus === "idle" || modelContextStatus === "loading") && <p role="status" data-testid="comparison-model-context-loading">{ui("Checking saved FIS availability before enabling manual-FIS comparison…", "Проверка доступности нечёткой модели…")}</p>}
    {modelContextStatus === "error" && <div className="error" role="alert" data-testid="comparison-model-context-error"><strong>{ui("Manual FIS availability could not be verified.", "Не удалось проверить доступность нечёткой модели.")}</strong><p>{modelContextError ?? "No empty-FIS state is inferred from this failed read."}</p>{onRetryModelContext && <Button view="outlined" onClick={onRetryModelContext}>{ui("Retry saved model context", "Повторить загрузку модели")}</Button>}</div>}
    {(runs.length > 1 || (runs.length > 0 && fis)) && <section className="comparison-card"><span className="eyebrow">{ui("MODEL COMPARISON · VALIDATION ONLY", "СРАВНЕНИЕ МОДЕЛЕЙ")}</span><h3>{ui("Compare compatible models on declared validation evidence", "Сравните модели на проверочных данных")}</h3>{fis && <label className="comparison-choice"><input type="checkbox" disabled={!!comparisonRecovery || modelContextStatus !== "loaded" || !fis.semantic_hash} checked={includeManualFis} onChange={(event) => setIncludeManualFis(event.target.checked)} />Manual {fis.system_type} FIS · semantic {(fis.semantic_hash ?? "unsaved").slice(0, 12)} · {fis.rules.length} rules</label>}{runs.map((candidate) => <label className="comparison-choice" key={candidate.run_id}><input type="checkbox" disabled={!!comparisonRecovery} checked={selectedRunIds.includes(candidate.run_id)} onChange={(event) => setSelectedRunIds((current) => event.target.checked ? [...current, candidate.run_id] : current.filter((id) => id !== candidate.run_id))} />{candidate.model_kind} · seed {candidate.seed} · {candidate.run_id.slice(0, 12)} · nodes {typeof candidate.model_spec.node_count === "number" ? candidate.model_spec.node_count : "—"}</label>)}<Button view="outlined" disabled={comparing || !!comparisonRecovery || project.read_only || !["none", "available"].includes(comparisonHydrationStatus) || selectedRunIds.length + (includeManualFis ? 1 : 0) < 2 || (includeManualFis && (selectedRunIds.length < 1 || modelContextStatus !== "loaded" || !fis?.semantic_hash))} onClick={saveSelectedComparison} data-ruflex-action="comparison.selected.create">{comparing ? "Comparing…" : `Compare ${selectedRunIds.length + (includeManualFis ? 1 : 0)} selected models`}</Button><p>{ui("Manual FIS is evaluated on exactly the persisted validation cases of the selected trained run(s). If selected runs use different validation cases, RuFLEX blocks adding the FIS instead of pretending the comparison is paired. FIS scores are not labeled calibrated probabilities.", "Нечёткая модель проверяется на тех же примерах, что и обученные модели. Если выборки различаются, совместное сравнение блокируется.")}</p></section>}

    <section className="comparison-card slice-lab">
      <span className="eyebrow">{ui("SLICE LAB · VALIDATION ONLY", "ПРОВЕРКА ГРУПП ДАННЫХ")}</span>
      <h3>{ui("Measure a declared subgroup without touching final test", "Посмотрите качество на выбранной группе")}</h3>
      <div className="slice-form-grid">
        <label className="field-label">{ui("Name", "Название")}<input aria-label={ui("Slice name", "Название группы")} value={sliceName} onChange={(event) => setSliceName(event.target.value)} /></label>
        <label className="field-label">{ui("Type", "Тип")}<select aria-label={ui("Slice type", "Тип группы")} value={sliceKind} onChange={(event) => setSliceKind(event.target.value as SliceDefinition["kind"])}><option value="numeric_range">{ui("Numeric range", "Диапазон значений")}</option><option value="categorical">{ui("Categorical", "Категории")}</option><option value="group">{ui("Group", "Группа")}</option><option value="temporal">{ui("Temporal", "Период времени")}</option><option value="manual">{ui("Manual source rows", "Выбранные строки")}</option></select></label>
        {sliceKind !== "manual" && <label className="field-label">{ui("Field", "Столбец")}<select aria-label={ui("Slice field", "Столбец группы")} value={sliceField || dataset?.contract.feature_columns[0] || ""} onChange={(event) => setSliceField(event.target.value)}>{dataset?.profile.columns.map((column) => <option value={column.name} key={column.name}>{column.name}</option>)}</select></label>}
        {(sliceKind === "categorical" || sliceKind === "group") && <label className="field-label">{ui("Values", "Значения")}<input aria-label={ui("Slice values", "Значения группы")} placeholder="A, B" value={sliceValues} onChange={(event) => setSliceValues(event.target.value)} /></label>}
        {sliceKind === "numeric_range" && <><label className="field-label">{ui("Minimum", "От")}<input aria-label={ui("Slice minimum", "Нижняя граница")} type="number" value={sliceMinimum} onChange={(event) => setSliceMinimum(event.target.value)} /></label><label className="field-label">{ui("Maximum", "До")}<input aria-label={ui("Slice maximum", "Верхняя граница")} type="number" value={sliceMaximum} onChange={(event) => setSliceMaximum(event.target.value)} /></label></>}
        {sliceKind === "temporal" && <><label className="field-label">{ui("Start", "Начало")}<input aria-label={ui("Slice start", "Начало периода")} placeholder="2026-01-01" value={sliceStart} onChange={(event) => setSliceStart(event.target.value)} /></label><label className="field-label">{ui("End", "Конец")}<input aria-label={ui("Slice end", "Конец периода")} placeholder="2026-12-31" value={sliceEnd} onChange={(event) => setSliceEnd(event.target.value)} /></label></>}
        {sliceKind === "manual" && <label className="field-label">{ui("Original source rows", "Номера строк")}<input aria-label={ui("Slice source rows", "Номера строк группы")} placeholder="2, 7, 11" value={sliceRows} onChange={(event) => setSliceRows(event.target.value)} /></label>}
        <label className="field-label">{ui("Metric", "Метрика")}<select aria-label={ui("Slice metric", "Метрика группы")} value={sliceMetric || (run.task === "binary_classification" ? "f1" : "rmse")} onChange={(event) => setSliceMetric(event.target.value)}>{run.task === "binary_classification" ? <><option value="f1">F1</option><option value="accuracy">{ui("Accuracy", "Доля верных ответов")}</option><option value="precision">{ui("Precision", "Точность положительных ответов")}</option><option value="recall">{ui("Recall", "Полнота")}</option><option value="brier">Brier</option></> : <><option value="rmse">RMSE</option><option value="mae">MAE</option><option value="mse">MSE</option><option value="r2">R²</option></>}</select></label>
      </div>
      {sliceAnalysisHydrationStatus === "loading" && <p role="status" data-testid="slice-hydration-loading">{ui("Loading saved slice evidence…", "Загрузка проверки группы…")}</p>}
      {sliceAnalysisHydrationStatus === "none" && <p className="property-description" data-testid="slice-hydration-empty">{ui("No saved SliceAnalysis is available for this project.", "Проверка отдельных групп ещё не сохранялась.")}</p>}
      {sliceAnalysisHydrationStatus === "error" && <div className="error" role="alert" data-testid="slice-hydration-error"><strong>{ui("Saved SliceAnalysis could not be verified.", "Не удалось проверить результат группы.")}</strong><p>{sliceAnalysisHydrationError}</p>{onRetrySliceAnalysis && <Button view="outlined" onClick={onRetrySliceAnalysis}>{ui("Retry slice evidence", "Повторить загрузку результата")}</Button>}</div>}
      {sliceRecoveryRequest && <div className="error" role="alert" data-testid="slice-analysis-recovery"><strong>{ui("Slice analysis save is uncertain; no duplicate was submitted.", "Сохранение результата не подтверждено. Повторная запись не создавалась.")}</strong><p>{sliceRecoveryError}</p><Button view="outlined" disabled={sliceRunning} onClick={recoverSliceAnalysis}>{ui("Retry saved SliceAnalysis lookup", "Найти сохранённый результат")}</Button>{sliceRecoveryNotFound && <Button view="outlined" disabled={sliceRunning || project.read_only} onClick={explicitlyRerunSliceAnalysis}>{ui("Explicitly rerun this exact slice", "Повторить проверку этой группы")}</Button>}</div>}
      <Button view="outlined" disabled={sliceRunning || !!sliceRecoveryRequest || !!evaluationRecoveryRunId || project.read_only || !dataset || !evaluationStateKnown || !["none", "available"].includes(sliceAnalysisHydrationStatus)} onClick={runSliceAnalysis} data-ruflex-action="slice.create">{sliceRunning ? ui("Calculating…", "Расчёт…") : ui("Run and persist slice", "Проверить группу данных")}</Button>
      {sliceAnalysis && <div className="data-table-wrap"><table className="data-table"><thead><tr><th>{ui("slice", "Группа")}</th><th>{ui("kind", "Тип")}</th><th>N</th><th>{ui("metric", "Метрика")}</th><th>{ui("value", "Значение")}</th><th>{ui("overall", "По всем данным")}</th><th>{ui("delta", "Разница")}</th><th>{ui("metric status", "Состояние")}</th><th>{ui("declared scope", "Область применения")}</th></tr></thead><tbody>{sliceAnalysis.results.map((result) => <tr key={`${sliceAnalysis.analysis_id}-${result.name}`}><td>{result.name}</td><td>{ui(result.kind, ({ numeric_range: "Диапазон", categorical: "Категории", group: "Группа", temporal: "Период", manual: "Выбранные строки" } as Record<string, string>)[result.kind] ?? result.kind)}</td><td>{result.n}</td><td>{result.metric}</td><td>{result.value === null ? "—" : result.value.toFixed(4)}</td><td>{result.overall_value.toFixed(4)}</td><td>{result.delta_vs_overall === null ? "—" : result.delta_vs_overall.toFixed(4)}</td><td>{uiStatus(result.status)}{result.warning ? ` · ${result.warning}` : ""}</td><td><StatusBadge tone={result.scope_disposition === "ALLOW" ? "success" : result.scope_disposition === "BLOCK" ? "danger" : "warning"}>{uiStatus(result.scope_disposition)}</StatusBadge>{result.scope_reasons.length > 0 && <small className="slice-scope-reason">{result.scope_reasons.join(" ")}</small>}</td></tr>)}</tbody></table><details open={uiLanguage === "en"}><summary>{ui("Calculation details", "Сведения о расчёте")}</summary><p>{sliceAnalysis.generalization_contract_id ? `Scope classifications use GeneralizationContract ${sliceAnalysis.generalization_contract_id.slice(0, 12)}. ` : "No GeneralizationContract was linked; scope remains undeclared. "}{sliceAnalysis.scientific_note}</p></details></div>}
    </section>
    {error && <div className="error" role="alert">{error}</div>}
  </section>;
}
